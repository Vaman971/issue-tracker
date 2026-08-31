"""Evaluate retrieval against the ground-truth dataset, layer by layer.

Three layers are measured separately so a regression can be attributed:

    RRF @5            what fusion alone produces
      |
    Reranker @5       what actually reaches the answer LLM
      |
    Answer sources    what the LLM actually cited

Retrieval runs once per case; every RRF variant is fused from the same cached
ranked lists, so a K sweep costs no extra API calls.

Usage:
    python -m scripts.rag_eval.runner
    python -m scripts.rag_eval.runner --k 60 30 20 10
    python -m scripts.rag_eval.runner --answer
    python -m scripts.rag_eval.runner --json results.json
"""

import argparse
import asyncio
import json
import re
import statistics

from app.api.helpers import rag_helper
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.rag.context.context_builder import ContextBuilder
from app.rag.filtering.filter_extractor import OpenAIFilterExtractor
from app.rag.filtering.schemas import SearchFilters
from app.rag.llm.openai_llm import OpenAILLM
from app.rag.multi_query.openai_multi_query import OpenAIQueryExpander
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.query_pipeline.schemas import ProcessedQuery, QueryRequest
from app.rag.query_pipeline.stages.filter import FilterStage
from app.rag.query_pipeline.stages.entity_consolidation import consolidate_entities
from app.rag.query_pipeline.stages.multi_query import MultiQueryStage
from app.rag.repositories.rag_document_repository import RagDocumentRepository
from app.rag.reranking.reranker import OpenAiReranker
from app.rag.reranking.schemas import RerankResponse, RerankResult
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever
from app.rag.retrievers.rrf import fuse
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import QueryTrace

from scripts.rag_eval.dataset import EVAL_CASES, EvalCase
from scripts.rag_eval.metrics import (
    hit_at_k,
    precision_at_k,
    rank_of_first_hit,
    recall_at_k,
)

# Imported, not restated. These drifted once already — the harness was
# retrieving 30 candidates and fusing at k=60 long after production moved to
# 15 and 30 — which meant every number it printed described a pipeline that
# no longer existed. Importing them makes the harness follow production by
# construction.
SEARCH_TOP_K = rag_helper.SEARCH_TOP_K
RERANK_TOP_K = rag_helper.RERANK_TOP_K
EVAL_K = rag_helper.CONTEXT_TOP_K

PRODUCTION_RRF_K = settings.DAMPING_CONSTANT

# what ConfidenceGateStage would do with each case
MIN_RELEVANCE = settings.RAG_MIN_RELEVANCE_SCORE

SOURCE_PATTERN = re.compile(r"issue:(\d+)")


def consolidate(results: list[SearchResult], top_n: int) -> list[int]:
    """Entity ids after applying the production consolidation rule."""

    return [
        result.entity_id
        for result in consolidate_entities(results, top_n)
    ]


def print_retrieval_diagnostics(
    query: str,
    search_queries: list[str],
    results: list[SearchResult],
    expected: set[int],
    k : int
) -> None:
    """Print RRF diagnostics for ground-truth multi-target cases."""

    if not expected:
        return

    result_by_entity: dict[int, list[SearchResult]] = {}

    for result in results:
        result_by_entity.setdefault(
            result.entity_id,
            [],
        ).append(result)

    print("\n" + "=" * 70)
    print("RETRIEVAL DIAGNOSTICS")
    print("=" * 70)

    print(f"Query    : {query}")
    print(f"RRF K    : {k}")
    print(f"Expected : {sorted(expected)}")
    print(f"Expanded : {search_queries}")

    print("\nRRF TOP 15")
    print("-" * 70)

    for rank, result in enumerate(results[:15], start=1):
        print(
            f"{rank:2d}  "
            f"issue:{result.entity_id:<5} "
            f"chunk:{result.chunk_index:<3} "
            f"score:{result.score:.6f}"
        )

    print("\nEXPECTED ISSUE LOCATIONS")
    print("-" * 70)

    for entity_id in sorted(expected):

        matches = result_by_entity.get(entity_id)

        if not matches:
            print(
                f"issue:{entity_id:<5} "
                "NOT IN RRF CANDIDATES"
            )
            continue

        ranks = [
            index + 1
            for index, result in enumerate(results)
            if result.entity_id == entity_id
        ]

        print(
            f"issue:{entity_id:<5} "
            f"RRF ranks:{ranks} "
            f"scores:{[round(m.score, 6) for m in matches]}"
        )

    print("=" * 70)


async def ranked_lists_for(
    search_queries: list[str],
    filters: SearchFilters,
) -> list[list[SearchResult]]:
    """One semantic list and one keyword list per search query."""

    lists: list[list[SearchResult]] = []

    for query in search_queries:

        async with AsyncSessionLocal() as session:

            semantic = await PGVectorRetriever(session).search(
                query=query,
                top_k=SEARCH_TOP_K,
                filters=filters,
            )

            rows = await RagDocumentRepository(session).keyword_search(
                query,
                limit=SEARCH_TOP_K,
                filters=filters,
            )

        keyword = [
            SearchResult(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                chunk_index=row.chunk_index,
                content=row.content,
                score=ts_rank,
                metadata=row.metadata_json,
            )
            for row, ts_rank in rows
        ]

        lists.append(semantic)
        lists.append(keyword)

    return lists

def score(retrieved: list[int], expected: set[int]) -> dict:
    return {
        "recall@5": round(recall_at_k(retrieved, expected, EVAL_K), 3),
        "precision@5": round(precision_at_k(retrieved, expected, EVAL_K), 3),
        "hit@5": hit_at_k(retrieved, expected, EVAL_K),
        "first_hit_rank": rank_of_first_hit(retrieved, expected),
    }


async def evaluate_case(
    case: EvalCase,
    filter_stage: FilterStage,
    multi_query_stage: MultiQueryStage,
    reranker: OpenAiReranker,
    rrf_ks: list[int],
    answer_layer: tuple[ContextBuilder, PromptTemplateLoader, OpenAILLM] | None,
) -> dict:

    expected = set(case.expected_entity_ids)

    trace = QueryTrace()

    processed = ProcessedQuery(
        original_query=case.query,
        rewritten_query=case.query,
        search_queries=[case.query],
        filters=SearchFilters(),
    )

    request = QueryRequest(question=case.query, history="")

    if await filter_stage.should_run(request=request, processed=processed):
        await filter_stage.process(request=request, processed=processed, trace=trace)

    if await multi_query_stage.should_run(request=request, processed=processed):
        await multi_query_stage.process(request=request, processed=processed, trace=trace)

    # retrieved once, re-fused per K
    lists = await ranked_lists_for(processed.search_queries, processed.filters)

    row: dict = {
        "id": case.id,
        "category": case.category,
        "query": case.query,
        "expected": sorted(expected),
        "search_queries": processed.search_queries,
    }

    fused_by_k: dict[int, list[SearchResult]] = {}

    for k in rrf_ks:

        fused = fuse(lists, top_k=SEARCH_TOP_K, k=k)
        fused_by_k[k] = fused

        if case.category == "multi":
            print_retrieval_diagnostics(
                query=case.query,
                search_queries=processed.search_queries,
                results=fused,
                expected=expected,
                k = k,
            )

        entities = consolidate(fused, EVAL_K)

        row[f"rrf_k{k}_top5"] = entities
        row[f"rrf_k{k}"] = score(entities, expected)

    # the reranker always sees the production fusion
    baseline = fused_by_k.get(PRODUCTION_RRF_K) or fused_by_k[rrf_ks[0]]

    # A rerank call can fail outright — the structured timeout is 10s with
    # two retries, so a sustained API stall exhausts it. One bad call must
    # not throw away the other 22 cases, so it is recorded and the case
    # carries on with the fused order the reranker would have refined.
    try:
        reranked = await reranker.rerank(
            query=case.query,
            results=baseline,
            top_k=RERANK_TOP_K,
        )
        rerank_error = None

    except Exception as exc:
        rerank_error = type(exc).__name__
        reranked = RerankResponse(
            results=[RerankResult(result=r, score=r.score) for r in baseline],
            model_scored=False,
        )

    consolidated = consolidate_entities(
        [item.result for item in reranked.results],
        EVAL_K,
    )

    rerank_entities = [result.entity_id for result in consolidated]

    row["rerank_top5"] = rerank_entities
    row["rerank"] = score(rerank_entities, expected)
    row["rerank_error"] = rerank_error

    # The gate now sits between reranking and the answer, so a case can score
    # perfectly and still be declined in production. Measured here so that
    # never goes unnoticed.
    top_score = (
        reranked.results[0].score
        if reranked.results and reranked.model_scored
        else None
    )

    row["gate"] = {
        "top_score": round(top_score, 3) if top_score is not None else None,
        # None means the reranker judged nothing, which the gate treats as
        # no evidence rather than bad evidence
        "declined": top_score is not None and top_score < MIN_RELEVANCE,
    }

    if answer_layer is not None:

        context_builder, prompt_loader, llm = answer_layer

        context = context_builder.build(consolidated)

        prompt = prompt_loader.render(
            "answer.j2",
            documents=context,
            question=case.query,
            history="",
        )

        response = await llm.generate(prompt)

        cited = []
        for match in SOURCE_PATTERN.findall(response.content):
            entity_id = int(match)
            if entity_id not in cited:
                cited.append(entity_id)

        row["answer_cited"] = cited
        row["answer"] = score(cited, expected)

    return row


def summarise(rows: list[dict], rrf_ks: list[int], answer_layer: bool) -> None:

    def mean(key: str, metric: str) -> float:
        values = [r[key][metric] for r in rows if key in r]
        return statistics.mean(values) if values else 0.0

    layers = [(f"RRF k={k}", f"rrf_k{k}") for k in rrf_ks]
    layers.append(("Reranker", "rerank"))
    if answer_layer:
        layers.append(("Answer", "answer"))

    print()
    print("=" * 62)
    print(f"{'layer':14} {'recall@5':>9} {'prec@5':>8} {'hit@5':>7} {'misses':>7}")
    print("=" * 62)

    for label, key in layers:
        misses = sum(1 for r in rows if key in r and not r[key]["hit@5"])
        print(
            f"{label:14} "
            f"{mean(key, 'recall@5'):>9.3f} "
            f"{mean(key, 'precision@5'):>8.3f} "
            f"{mean(key, 'hit@5'):>7.3f} "
            f"{misses:>7}"
        )

    failed = [r for r in rows if r.get("rerank_error")]

    if failed:
        print()
        print(f"RERANK FAILURES: {len(failed)}/{len(rows)} "
              f"— these cases fell back to fused order, so the reranker row understates it")
        for row in failed:
            print(f"  {row['id']:<26} {row['rerank_error']}")

    # ── confidence gate ──
    declined = [r for r in rows if r.get("gate", {}).get("declined")]
    unjudged = [r for r in rows if r.get("gate", {}).get("top_score") is None]

    scores = [
        r["gate"]["top_score"]
        for r in rows
        if r.get("gate", {}).get("top_score") is not None
    ]

    print()
    print(f"confidence gate (threshold {MIN_RELEVANCE}):")

    if scores:
        print(
            f"  top score  min={min(scores):.2f}  "
            f"median={statistics.median(scores):.2f}  max={max(scores):.2f}"
        )

    print(f"  declined   {len(declined)}/{len(rows)}")

    # A declined case that the reranker actually got right is the failure
    # that matters: the answer was there and the gate threw it away.
    for row in declined:
        verdict = "WOULD LOSE A CORRECT ANSWER" if row["rerank"]["hit@5"] else "no hit anyway"
        print(f"    {row['id']:<26} score={row['gate']['top_score']}  {verdict}")

    if unjudged:
        print(f"  unjudged   {len(unjudged)} (reranker output unparsed; gate stays out of the way)")

    print()
    print("cases where the reranker changed the outcome:")

    baseline_key = f"rrf_k{PRODUCTION_RRF_K}" if PRODUCTION_RRF_K in rrf_ks else f"rrf_k{rrf_ks[0]}"

    changed = False
    for row in rows:
        before = row[baseline_key]["recall@5"]
        after = row["rerank"]["recall@5"]
        if before != after:
            changed = True
            arrow = "RESCUED" if after > before else "LOST"
            print(f"  {arrow:8} {row['id']:24} {before:.2f} -> {after:.2f}")

    if not changed:
        print("  none")


async def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument("--k", nargs="*", type=int, default=[PRODUCTION_RRF_K])
    parser.add_argument("--answer", action="store_true")
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--limit", type=int, default=None)
    # Rerank is roughly 60% of a turn's cost, so "is a cheaper model good
    # enough?" is the question worth being able to answer here rather than
    # by editing settings and restarting.
    parser.add_argument("--rerank-model", dest="rerank_model", default=None)
    # Caching is OFF for evaluation. A benchmark that reads a cache measures
    # whatever wrote the entries, not the code under test — a filter or
    # expansion cached under an older prompt survives the prompt change and
    # quietly invalidates the comparison. It also stops eval queries writing
    # into the cache the application shares.
    parser.add_argument(
        "--cache",
        action="store_true",
        help="read and write the pipeline caches (off by default)",
    )
    args = parser.parse_args()

    settings.CACHE_ENABLED = args.cache

    if not args.cache:
        print("caches disabled: every stage runs fresh, and Redis is not touched")

    cases = EVAL_CASES[: args.limit] if args.limit else EVAL_CASES

    prompt_loader = PromptTemplateLoader()

    filter_stage = FilterStage(
        extractor=OpenAIFilterExtractor(prompt_loader=prompt_loader),
    )
    multi_query_stage = MultiQueryStage(
        expander=OpenAIQueryExpander(prompt_loader=prompt_loader),
    )
    reranker = OpenAiReranker(prompt_loader=prompt_loader)

    if args.rerank_model:
        reranker._model = args.rerank_model
        print(f"reranking with {args.rerank_model} (default {settings.OPENAI_CHAT_MODEL})")

    answer_layer = (
        (ContextBuilder(), prompt_loader, OpenAILLM())
        if args.answer
        else None
    )

    rows = await asyncio.gather(*[
        evaluate_case(
            case=case,
            filter_stage=filter_stage,
            multi_query_stage=multi_query_stage,
            reranker=reranker,
            rrf_ks=args.k,
            answer_layer=answer_layer,
        )
        for case in cases
    ])

    for row in rows:
        print(json.dumps(row))

    summarise(list(rows), args.k, args.answer)

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(list(rows), handle, indent=2)


if __name__ == "__main__":
    asyncio.run(main())

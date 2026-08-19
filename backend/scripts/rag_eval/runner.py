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

SEARCH_TOP_K = 30
RERANK_TOP_K = 10
EVAL_K = 5

PRODUCTION_RRF_K = 60

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

    reranked = await reranker.rerank(
        query=case.query,
        results=baseline,
        top_k=RERANK_TOP_K,
    )

    consolidated = consolidate_entities(
        [item.result for item in reranked.results],
        EVAL_K,
    )

    rerank_entities = [result.entity_id for result in consolidated]

    row["rerank_top5"] = rerank_entities
    row["rerank"] = score(rerank_entities, expected)

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
    args = parser.parse_args()

    cases = EVAL_CASES[: args.limit] if args.limit else EVAL_CASES

    prompt_loader = PromptTemplateLoader()

    filter_stage = FilterStage(
        extractor=OpenAIFilterExtractor(prompt_loader=prompt_loader),
    )
    multi_query_stage = MultiQueryStage(
        expander=OpenAIQueryExpander(prompt_loader=prompt_loader),
    )
    reranker = OpenAiReranker(prompt_loader=prompt_loader)

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

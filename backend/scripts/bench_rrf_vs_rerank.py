"""Benchmark RRF-only retrieval against reranked retrieval.

Answers one question: for which query shapes does the reranker actually
change WHICH entities come back, as opposed to only reordering them?

Ordering differences are ignored on purpose. If RRF and the reranker return
the same five entities in a different order, the reranker earned nothing that
the answer LLM could not have worked out for itself.

Usage:
    python -m scripts.bench_rrf_vs_rerank            # all queries
    python -m scripts.bench_rrf_vs_rerank 0 1 2 3    # a subset, by index
    python -m scripts.bench_rrf_vs_rerank --json out.json
"""

import argparse
import asyncio
import json
import sys

from app.db.session import AsyncSessionLocal
from app.rag.filtering.filter_extractor import OpenAIFilterExtractor
from app.rag.multi_query.openai_multi_query import OpenAIQueryExpander
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.query_pipeline.schemas import ProcessedQuery, QueryRequest
from app.rag.query_pipeline.stages.filter import FilterStage
from app.rag.query_pipeline.stages.multi_query import MultiQueryStage
from app.rag.query_pipeline.stages.search import SearchStage
from app.rag.reranking.reranker import OpenAiReranker
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.retrievers.schemas import SearchResult
from app.rag.filtering.schemas import SearchFilters
from app.rag.tracing.schema import QueryTrace
from app.rag.tracing.timer import Timer


QUERIES: list[tuple[str, str]] = [
    # (category, query)
    ("topical", "Which issues mention session token problems?"),
    ("topical", "Which issues deal with authentication problems?"),
    ("topical", "Which issues have OAuth problems?"),

    ("property", "Which issues have high priority?"),
    ("property", "Which high priority issues are in progress?"),
    ("property", "Which issues are critical?"),

    ("compound", "Which high priority authentication issues are still open?"),
    ("compound", "Which authentication issues are in progress?"),

    ("specific", "Which issue describes the authentication failure after the billing dashboard session expires?"),

    ("ambiguous", "Which issues have problems?"),
    ("ambiguous", "Which issues are related to security?"),
    ("ambiguous", "Which issues need attention?"),
]

SEARCH_TOP_K = 15
RERANK_TOP_K = 10
COMPARE_TOP_N = 5


def consolidate(
    results: list[SearchResult],
    top_n: int,
) -> list[int]:
    """Collapse chunks to unique entity ids, preserving rank order.

    Mirrors EntityConsolidationStage so both sides are compared the same way
    the pipeline would actually deliver them.
    """

    seen: set[int] = set()
    entities: list[int] = []

    for result in results:

        if result.entity_id in seen:
            continue

        seen.add(result.entity_id)
        entities.append(result.entity_id)

        if len(entities) >= top_n:
            break

    return entities


def score_shape(results: list[SearchResult]) -> dict:
    """Describe the RRF score distribution for threshold selection."""

    scores = [round(r.score, 6) for r in results]

    if len(scores) < 2:
        return {
            "top_score": scores[0] if scores else 0.0,
            "second_score": 0.0,
            "top_to_second_gap": 0.0,
            "largest_gap": 0.0,
            "largest_gap_position": 0,
            "scores": scores,
        }

    gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
    largest = max(gaps)

    return {
        "top_score": scores[0],
        "second_score": scores[1],
        "top_to_second_gap": round(scores[0] - scores[1], 6),
        "largest_gap": round(largest, 6),
        # 1-based: a gap at position N means a cut between rank N and N+1
        "largest_gap_position": gaps.index(largest) + 1,
        "scores": scores,
    }


async def run_query(
    category: str,
    query: str,
    retriever: HybridRetriever,
    filter_stage: FilterStage,
    multi_query_stage: MultiQueryStage,
    search_stage: SearchStage,
    reranker: OpenAiReranker,
) -> dict:

    trace = QueryTrace()

    processed = ProcessedQuery(
        original_query=query,
        rewritten_query=query,
        search_queries=[query],
        filters=SearchFilters(),
    )

    request = QueryRequest(question=query, history="")

    # filter and expansion run exactly as the live pipeline would
    if await filter_stage.should_run(request=request, processed=processed):
        await filter_stage.process(request=request, processed=processed, trace=trace)

    expanded = await multi_query_stage.should_run(request=request, processed=processed)
    if expanded:
        await multi_query_stage.process(request=request, processed=processed, trace=trace)

    await search_stage.process(request=request, processed=processed, trace=trace)

    # what each retriever found BEFORE fusion. The retriever extends these
    # once per search query, so they are the union across all phrasings.
    semantic_entities = {
        result.entity_id
        for result in trace.retrieval.semantic_results
    }

    keyword_entities = {
        result.entity_id
        for result in trace.retrieval.keyword_results
    }

    retrieval_overlap = semantic_entities & keyword_entities

    rrf_results = list(processed.results)

    timer = Timer()
    reranked = await reranker.rerank(
        query=query,
        results=rrf_results,
        top_k=RERANK_TOP_K,
    )
    rerank_ms = timer.elapsed_ms()

    rerank_results = [item.result for item in reranked.results]

    rrf_entities = consolidate(rrf_results, COMPARE_TOP_N)
    rerank_entities = consolidate(rerank_results, COMPARE_TOP_N)

    overlap = set(rrf_entities) & set(rerank_entities)

    # number of ranked lists fused = queries searched x 2 sources
    list_count = len(processed.search_queries) * 2

    return {
        "category": category,
        "query": query,
        "expanded": expanded,
        "search_queries": processed.search_queries,
        "list_count": list_count,
        "filters": {
            k: v for k, v in vars(processed.filters).items() if v
        } if hasattr(processed.filters, "__dict__") else {
            f: getattr(processed.filters, f)
            for f in processed.filters.__slots__
            if getattr(processed.filters, f)
        },
        "candidate_chunks": len(rrf_results),
        "unique_entities_in_candidates": len({r.entity_id for r in rrf_results}),
        "semantic_entities": len(semantic_entities),
        "keyword_entities": len(keyword_entities),
        "cross_retriever_entity_overlap": len(retrieval_overlap),
        **score_shape(rrf_results),
        "rrf_top5": rrf_entities,
        "rerank_top5": rerank_entities,
        "overlap_count": len(overlap),
        "same_set": set(rrf_entities) == set(rerank_entities),
        "same_order": rrf_entities == rerank_entities,
        "rerank_ms": round(rerank_ms),
        "rerank_input_tokens": reranked.input_tokens,
        "rerank_output_tokens": reranked.output_tokens,
    }


async def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument("indices", nargs="*", type=int)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args()

    selected = (
        [(i, *QUERIES[i]) for i in args.indices]
        if args.indices
        else [(i, *q) for i, q in enumerate(QUERIES)]
    )

    prompt_loader = PromptTemplateLoader()

    retriever = HybridRetriever(session_factory=AsyncSessionLocal)

    filter_stage = FilterStage(
        extractor=OpenAIFilterExtractor(prompt_loader=prompt_loader),
    )
    multi_query_stage = MultiQueryStage(
        expander=OpenAIQueryExpander(prompt_loader=prompt_loader),
    )
    search_stage = SearchStage(retriever=retriever, top_k=SEARCH_TOP_K)
    reranker = OpenAiReranker(prompt_loader=prompt_loader)

    rows = await asyncio.gather(*[
        run_query(
            category=category,
            query=query,
            retriever=retriever,
            filter_stage=filter_stage,
            multi_query_stage=multi_query_stage,
            search_stage=search_stage,
            reranker=reranker,
        )
        for _, category, query in selected
    ])

    for (index, _, _), row in zip(selected, rows):
        row["index"] = index

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)

    for row in rows:
        print(json.dumps(row), file=sys.stdout)


if __name__ == "__main__":
    asyncio.run(main())

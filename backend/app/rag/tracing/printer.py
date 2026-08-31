from dataclasses import asdict

from app.rag.tracing.schema import RAGTrace
from app.rag.tracing.timer import format_ms

WIDTH = 60
MAJOR = "=" * WIDTH
MINOR = "-" * WIDTH

LABEL_WIDTH = 16


def _row(label: str, value) -> str:
    return f"{label:<{LABEL_WIDTH}} : {value}"


def _executed(count: int, cache_hits: int) -> str:
    """Zero results with cache hits means the retriever never ran.

    Printing a bare 0 there reads as "found nothing" rather than
    "did not need to look".
    """
    if count == 0 and cache_hits:
        return "cached"
    return str(count)


def _heading(title: str, rule: str = MINOR) -> None:
    print(rule)
    print(title)
    print(rule)
    print()


def _total_cost(trace: RAGTrace) -> float:
    """Every stage that charged for this turn, summed.

    Cached and skipped stages hold zero, so this is what the turn actually
    spent rather than what it would have cost cold.
    """

    return (
        trace.query.route.cost_usd
        + trace.query.rewrite.cost_usd
        + trace.query.filter.cost_usd
        + trace.query.multi_query.cost_usd
        + trace.query.rerank.cost_usd
        + trace.llm.cost_usd
    )


class TracePrinter:

    @staticmethod
    def print(trace: RAGTrace) -> None:

        _heading("QUESTION", MAJOR)
        print(trace.question)
        print()

        _heading("ROUTE")
        print(_row("Intent", trace.query.route.intent))
        print(_row("Path", "deterministic" if trace.query.route.deterministic else "LLM"))
        if not trace.query.route.deterministic:
            print(_row("Cache Hit", bool(trace.query.route.cache_hit)))
            print(_row("Model", trace.query.route.model))
        print(_row("Cost", f"${trace.query.route.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.query.route.duration_ms)))
        print()

        _heading("REWRITE")
        if trace.query.rewrite.skipped:
            print(_row("Skipped", trace.query.rewrite.skip_reason))
            print()
        else:
            print(_row("Original Query", trace.query.rewrite.original_query))
            print(_row("Rewritten Query", trace.query.rewrite.rewritten_query))
            print(_row("History used", trace.query.rewrite.used_history))
            print()
            print(_row("Model", trace.query.rewrite.model))
            print(_row("Cost", f"${trace.query.rewrite.cost_usd:.4f}"))
            print(_row("Time", format_ms(trace.query.rewrite.duration_ms)))
            print()

        _heading("FILTER")
        print(_row("Search Query", trace.query.filter.query))
        applied = {
            name: value
            for name, value in asdict(trace.query.filter.filters).items()
            if value
        }
        print(_row("Filters", applied or "none"))
        print()
        print(_row("Path","deterministic"
        if trace.query.filter.deterministic
        else "LLM"))
        if not trace.query.filter.deterministic:
            print(_row("Cache Hit", bool(trace.query.filter.cache_hit)))
            print(_row("Model", trace.query.filter.model))
        # zero on the deterministic path and on a cache hit: no model ran
        print(_row("Cost", f"${trace.query.filter.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.query.filter.duration_ms)))
        print()

        _heading("MULTI QUERY")
        if trace.query.multi_query.skipped:
            print(_row("Skipped", trace.query.multi_query.skip_reason))
            print()
        else:
            for index, alternative in enumerate(trace.query.multi_query.alternatives, start=1):
                print(_row(f"Alternative {index}", alternative))
            if not trace.query.multi_query.alternatives:
                print(_row("Alternatives", "none"))
            print()
            print(_row("Cache Hit", bool(trace.query.multi_query.cache_hit)))
            print(_row("Model", trace.query.multi_query.model))
            print(_row("Cost", f"${trace.query.multi_query.cost_usd:.4f}"))
            print(_row("Time", format_ms(trace.query.multi_query.duration_ms)))
            print()

        _heading("RETRIEVAL")
        print(_row("Semantic Results", _executed(
            len(trace.query.retrieval.semantic_results),
            trace.query.retrieval.search_cache_hits,
        )))
        print(_row("Keyword Results", _executed(
            len(trace.query.retrieval.keyword_results),
            trace.query.retrieval.search_cache_hits,
        )))
        print(_row("Merged Results", len(trace.query.retrieval.final_results)))
        print(_row(
            "Search Cache",
            f"{trace.query.retrieval.search_cache_hits} hit / "
            f"{trace.query.retrieval.search_cache_misses} miss",
        ))
        print(_row(
            "Embedding Cache",
            f"{trace.query.retrieval.embedding_cache_hits} hit / "
            f"{trace.query.retrieval.embedding_cache_misses} miss",
        ))
        print()
        print(_row("Time", format_ms(trace.query.retrieval.duration_ms)))
        print()

        _heading("RERANK")
        print(_row("Candidate count", trace.query.rerank.candidate_count))
        print(_row("Final count", trace.query.rerank.final_count))
        print()
        print(_row("Model", trace.query.rerank.model))
        print(_row("Cache Hit", bool(trace.query.rerank.cache_hit)))
        print(_row("Input Tokens", trace.query.rerank.input_tokens))
        print(_row("Output Tokens", trace.query.rerank.output_tokens))
        print(_row("Reasoning Tokens", trace.query.rerank.reasoning_tokens))
        print(_row("Cost", f"${trace.query.rerank.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.query.rerank.duration_ms)))
        print()

        _heading("GATE")
        print(_row("Top score", f"{trace.query.gate.top_score:.2f}"))
        print(_row("Threshold", f"{trace.query.gate.threshold:.2f}"))
        print(_row("Passed", bool(trace.query.gate.passed)))
        print()

        _heading("LLM")
        print(_row("Model", trace.llm.model))
        print(_row("Input Tokens", trace.llm.input_tokens))
        print(_row("Output Tokens", trace.llm.output_tokens))
        print(_row("Cost", f"${trace.llm.cost_usd:.4f}"))
        print(_row("First Token", format_ms(trace.llm.ttft_ms)))
        print(_row("Last Token", format_ms(trace.llm.ttlt_ms)))
        print(_row("Reference Ids", trace.reference_ids))
        print(_row("Time", format_ms(trace.llm.duration_ms)))
        print()

        _heading("TOTAL")
        print(_row("Total Time",format_ms(trace.total_duration_ms)))
        print(_row("Total Cost", f"${_total_cost(trace):.4f}"))
        print()

        _heading("ANSWER")
        print(trace.llm.answer)
        print()

        _heading("SOURCES")
        seen: set[str] = set()
        for document in trace.context:
            if document.source not in seen:
                seen.add(document.source)
                print(document.source)

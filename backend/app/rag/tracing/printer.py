from dataclasses import asdict

from app.rag.tracing.schema import RAGTrace
from app.rag.tracing.timer import format_ms

WIDTH = 60
MAJOR = "=" * WIDTH
MINOR = "-" * WIDTH

LABEL_WIDTH = 16


def _row(label: str, value) -> str:
    return f"{label:<{LABEL_WIDTH}} : {value}"


def _heading(title: str, rule: str = MINOR) -> None:
    print(rule)
    print(title)
    print(rule)
    print()


class TracePrinter:

    @staticmethod
    def print(trace: RAGTrace) -> None:

        _heading("QUESTION", MAJOR)
        print(trace.question)
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
            print(_row("Time", format_ms(trace.query.multi_query.duration_ms)))
            print()

        _heading("RETRIEVAL")
        print(_row("Semantic Results", len(trace.query.retrieval.semantic_results)))
        print(_row("Keyword Results", len(trace.query.retrieval.keyword_results)))
        print(_row("Merged Results", len(trace.query.retrieval.final_results)))
        print()
        print(_row("Time", format_ms(trace.query.retrieval.duration_ms)))
        print()

        _heading("RERANK")
        print(_row("Candidate count", trace.query.rerank.candidate_count))
        print(_row("Final count", trace.query.rerank.final_count))
        print()
        print(_row("Model", trace.query.rerank.model))
        print(_row("Input Tokens", trace.query.rerank.input_tokens))
        print(_row("Output Tokens", trace.query.rerank.output_tokens))
        print(_row("Reasoning Tokens", trace.query.rerank.reasoning_tokens))
        print(_row("Cost", f"${trace.query.rerank.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.query.rerank.duration_ms)))
        print()

        _heading("LLM")
        print(_row("Model", trace.llm.model))
        print(_row("Input Tokens", trace.llm.input_tokens))
        print(_row("Output Tokens", trace.llm.output_tokens))
        print(_row("Cost", f"${trace.llm.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.llm.duration_ms)))
        print()

        _heading("TOTAL TIME")
        print(_row("Total Time",format_ms(trace.total_duration_ms)))
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

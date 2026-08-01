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

        _heading("RETRIEVAL")
        print(_row("Semantic Results", len(trace.retrieval.semantic_results)))
        print(_row("Keyword Results", len(trace.retrieval.keyword_results)))
        print(_row("Merged Results", len(trace.retrieval.final_results)))
        print()
        print(_row("Time", format_ms(trace.retrieval.duration_ms)))
        print()

        _heading("LLM")
        print(_row("Model", trace.llm.model))
        print(_row("Input Tokens", trace.llm.input_tokens))
        print(_row("Output Tokens", trace.llm.output_tokens))
        print(_row("Cost", f"${trace.llm.cost_usd:.4f}"))
        print(_row("Time", format_ms(trace.llm.duration_ms)))
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

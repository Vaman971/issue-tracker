from dataclasses import dataclass

from app.rag.context.schemas import ContextDocument


@dataclass(slots=True)
class RAGResponse:

    answer: str

    context: list[ContextDocument]

    model: str

    input_tokens: int

    output_tokens: int

    total_tokens: int

from dataclasses import dataclass

from app.rag.retrievers.schemas import SearchResult

@dataclass(slots=True)
class RerankResult:
    result: SearchResult

    score: float

@dataclass(slots=True)
class RerankResponse:

    results: list[RerankResult]

    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0

    total_tokens: int = 0

    # False when the model's output could not be parsed and the candidates
    # were passed through in retrieval order. The scores are then RRF values,
    # not relevance judgements, and nothing may draw conclusions from them.
    model_scored: bool = True

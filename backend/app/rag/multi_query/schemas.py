from dataclasses import dataclass, field

from app.rag.llm.schemas import LLMUsage


@dataclass(slots=True)
class ExpansionResult:

    original_query: str

    # alternative phrasings only; the original is not repeated here
    alternatives: list[str] = field(default_factory=list)

    # what the call consumed; left at zeros when the result came from a cache
    # or a deterministic path, so summing across a turn counts real work only
    usage: LLMUsage = field(default_factory=LLMUsage)


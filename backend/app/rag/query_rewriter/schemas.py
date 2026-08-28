from dataclasses import dataclass, field

from app.rag.llm.schemas import LLMUsage


@dataclass(slots=True)
class RewriteResult:

    original_query: str

    rewritten_query: str

    used_history: bool

    # what the call consumed; left at zeros when the result came from a cache
    # or a deterministic path, so summing across a turn counts real work only
    usage: LLMUsage = field(default_factory=LLMUsage)

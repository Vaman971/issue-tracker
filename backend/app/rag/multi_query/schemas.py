from dataclasses import dataclass, field


@dataclass(slots=True)
class ExpansionResult:

    original_query: str

    # alternative phrasings only; the original is not repeated here
    alternatives: list[str] = field(default_factory=list)

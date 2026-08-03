from dataclasses import dataclass


@dataclass(slots=True)
class RewriteResult:

    original_query: str

    rewritten_query: str

    used_history: bool
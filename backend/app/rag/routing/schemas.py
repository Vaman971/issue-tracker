from dataclasses import dataclass, field
from enum import Enum

from app.rag.llm.schemas import LLMUsage


class QueryIntent(str, Enum):
    """What the user is actually asking for.

    Deliberately a small closed set. Every label has to map onto a different
    thing the assistant does, otherwise the classifier is being asked to make
    a distinction nobody acts on.
    """

    # a question about the issue tracker: run the retrieval pipeline
    KNOWLEDGE = "knowledge"

    # a greeting, or a question about the assistant itself
    CAPABILITY = "capability"

    # thanks, "ok", "got it" — a turn that closes the previous exchange and
    # asks for nothing, so it earns a short reply rather than the full
    # capability description
    ACKNOWLEDGEMENT = "acknowledgement"

    # anything the assistant has no business answering
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(slots=True)
class RouteResult:

    intent: QueryIntent

    # what the classification call consumed; left at zeros when the intent
    # came from the deterministic path or from cache
    usage: LLMUsage = field(default_factory=LLMUsage)

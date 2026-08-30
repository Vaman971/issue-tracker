"""Recognises the obvious cases without spending an LLM call.

Mirrors `app/rag/filtering/deterministic.py`: it answers only when it is
certain and returns None otherwise, leaving the ambiguous majority to the
model. Being wrong here is worse than being slow, so every pattern is
anchored to the WHOLE message — "hi" is a greeting, but "hi, which issues are
blocked?" is a question and must reach retrieval.
"""

import re

from app.rag.memory.reference_resolver import CONTINUATION_PATTERN, REFERENCE_PATTERN
from app.rag.routing.schemas import QueryIntent

# An opening pleasantry and nothing else. Answered with the capability reply
# rather than a bare "hello", because someone who has just said hi is about to
# ask what this thing does. Trailing punctuation is allowed: "hi!" and "hi"
# are the same message.
GREETING_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        hi | hey | hello | yo
        | good\s+(?:morning|afternoon|evening)
    )
    [\s!.,]*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A message that closes the previous exchange and asks for nothing. Kept
# apart from GREETING_PATTERN so "thanks" gets a short acknowledgement
# instead of the full capability description, which reads as a non sequitur
# after the assistant has just answered something.
ACKNOWLEDGEMENT_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        thanks? | thank\s+you | thx | ty
        | ok(?:ay)? | k
        | cool | great | nice | perfect | awesome
        | got\s+it | understood | makes\s+sense
        | bye | goodbye | see\s+you
    )
    (?:\s+(?:a\s+lot|so\s+much|very\s+much|mate|man))?
    [\s!.,]*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A question about the assistant rather than about the issues. An optional
# greeting may lead, so "Hello how can you help me?" is recognised.
CAPABILITY_PATTERN = re.compile(
    r"""
    ^\s*
    (?:(?:hi|hey|hello)[\s,!]+)?
    (?:
        what\s+can\s+you\s+do(?:\s+for\s+me)?
        | what\s+do\s+you\s+do
        | how\s+can\s+you\s+help(?:\s+me)?
        | how\s+do\s+you\s+help(?:\s+me)?
        | can\s+you\s+help(?:\s+me)?
        | who\s+are\s+you
        | what\s+are\s+you
        | what\s+is\s+this
        | how\s+(?:do\s+you|does\s+this)\s+work
        | help
    )
    [\s?!.]*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def route_deterministic(
    question: str,
    history: str,
) -> QueryIntent | None:
    """Classify a message, or return None when the model should decide.

    Order matters twice over. The follow-up check comes first because a
    fragment like
    "and the critical ones?" carries almost no topic of its own — read alone
    a classifier can easily call it chitchat, which would silently break the
    reference resolution the conversation depends on. If there is history and
    the message reads as a continuation, it belongs to the conversation that
    came before it, and that conversation was about issues.

    Capability is checked before the two pleasantry patterns because "help"
    is a capability question while "hi" is not, and an unanchored ordering
    would let the shorter pattern win.
    """

    if history.strip() and _is_follow_up(question):
        return QueryIntent.KNOWLEDGE

    if CAPABILITY_PATTERN.fullmatch(question):
        return QueryIntent.CAPABILITY

    if GREETING_PATTERN.fullmatch(question):
        return QueryIntent.CAPABILITY

    if ACKNOWLEDGEMENT_PATTERN.fullmatch(question):
        return QueryIntent.ACKNOWLEDGEMENT

    # nothing certain to say; the caller falls back to the LLM router
    return None


def _is_follow_up(question: str) -> bool:
    """Whether the message continues the previous turn.

    Reuses the patterns the reference resolver already matches on, so the
    router and the resolver cannot disagree about what a follow-up is.
    """

    return bool(
        REFERENCE_PATTERN.search(question)
        or CONTINUATION_PATTERN.search(question)
    )

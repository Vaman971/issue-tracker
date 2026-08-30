"""The answers given without calling the answer model.

Written here, by hand, on purpose. "What can you do?" has a correct answer
that the product's author owns — letting the model improvise it invites a
confident description of features that do not exist. A fixed string also
costs nothing, cannot be prompt-injected, and reads the same every time.

Edit the copy here rather than in a prompt template.
"""

from app.rag.routing.schemas import QueryIntent

CAPABILITY_REPLY = (
    "I can help you find and understand issues in the projects you have "
    "access to.\n"
    "\n"
    "Try asking things like:\n"
    "- which issues involve failed webhook deliveries?\n"
    "- what critical bugs are still open?\n"
    "- show me issues about session tokens\n"
    "\n"
    "I only know about issues recorded in this tracker, and only the ones "
    "you are allowed to see."
)

ACKNOWLEDGEMENT_REPLY = (
    "You're welcome. Tell me what else you would like me to find — an issue, "
    "a status, or anything else in the projects you work on."
)

OUT_OF_SCOPE_REPLY = (
    "I can only help with questions about the issues and projects in this "
    "tracker.\n"
    "\n"
    "Try asking about a bug, a status, or a project you work on."
)

_REPLIES = {
    QueryIntent.CAPABILITY: CAPABILITY_REPLY,
    QueryIntent.ACKNOWLEDGEMENT: ACKNOWLEDGEMENT_REPLY,
    QueryIntent.OUT_OF_SCOPE: OUT_OF_SCOPE_REPLY,
}


def reply_for(intent: QueryIntent) -> str | None:
    """The fixed answer for an intent, or None when the pipeline should run.

    Returning None for KNOWLEDGE is what makes this safe to call
    unconditionally: a caller that forgets to check the intent still gets the
    normal retrieval path rather than a canned reply.
    """

    return _REPLIES.get(intent)

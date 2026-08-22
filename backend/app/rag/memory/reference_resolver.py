import re

from app.rag.memory.schemas import ConversationState

REFERENCE_WORDS = (
    "them",
    "those",
    "these",
    "they",
    "ones",
    "others",
    "the rest",
    "the others",
    "the same",
    "the first one",
    "the second one",
    "the third one",
    "the previous ones",
    "the previously listed",
    "the listed",
)

# Matched against the whole question, not a list of split words. Splitting on
# whitespace can never match a multi-word phrase such as "the first one", and
# it leaves punctuation attached, so "those?" fails to equal "those".
# The word boundaries stop "them" matching inside "theme".
REFERENCE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in REFERENCE_WORDS) + r")\b",
    re.IGNORECASE,
)

# A question that opens with a continuation is a follow-up even when it
# contains no pronoun at all: "and the low priority ones?", "what about
# authentication?". Anchored to the start so "issues tagged and closed"
# is not mistaken for one.
CONTINUATION_PATTERN = re.compile(
    r"^\s*(?:and|also|plus|what about|how about|ok(?:ay)?[,\s]+and)\b",
    re.IGNORECASE,
)


class ReferenceResolver:

    def _has_reference(self, question: str) -> bool:

        if REFERENCE_PATTERN.search(question):
            return True

        return bool(CONTINUATION_PATTERN.search(question))

    def resolve(
            self,
            question: str,
            state: ConversationState,
    ) -> list[int]:

        if not self._has_reference(question):
            return []

        return state.last_result_ids.copy()

import re

from app.rag.memory.schemas import ConversationState

REFERENCE_WORDS = (
    "them",
    "those",
    "these",
    "they",
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


class ReferenceResolver:

    def _has_reference(self, question: str) -> bool:

        return bool(REFERENCE_PATTERN.search(question))

    def resolve(
            self,
            question: str,
            state: ConversationState,
    ) -> list[int]:

        if not self._has_reference(question):
            return []

        return state.last_result_ids.copy()

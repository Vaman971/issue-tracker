from app.rag.memory.base import BaseMemory
from app.rag.memory.schemas import ChatMessage, ConversationState


class InMemoryMemory(BaseMemory):

    def __init__(self):

        self._messages: list[ChatMessage] = []
        self._state = ConversationState()

    def add(
        self,
        message: ChatMessage,
    ) -> None:

        self._messages.append(message)

    def messages(
        self,
    ) -> list[ChatMessage]:

        return self._messages.copy() # Never expose internal mutable state.

    def get_state(
        self,
    ) -> ConversationState:

        return ConversationState(
            last_question=self._state.last_question,
            last_rewritten_query=self._state.last_rewritten_query,
            last_result_ids=self._state.last_result_ids.copy(),
        )

    def update_state(
        self,
        state: ConversationState,
    ) -> None:

        self._state = ConversationState(
            last_question=state.last_question,
            last_rewritten_query=state.last_rewritten_query,
            last_result_ids=state.last_result_ids.copy(),
        )

    def clear(self):

        self._messages.clear()
        self._state = ConversationState()

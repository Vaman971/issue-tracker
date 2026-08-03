from app.rag.memory.base import BaseMemory
from app.rag.memory.schemas import ChatMessage


class InMemoryMemory(BaseMemory):

    def __init__(self):

        self._messages: list[ChatMessage] = []

    def add(
        self,
        message: ChatMessage,
    ) -> None:

        self._messages.append(message)

    def messages(
        self,
    ) -> list[ChatMessage]:

        return self._messages.copy() # Never expose internal mutable state.

    def clear(self):

        self._messages.clear()

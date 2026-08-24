from abc import ABC
from abc import abstractmethod

from app.rag.memory.schemas import ChatMessage, ConversationState


class BaseMemory(ABC):

    @abstractmethod
    async def add(
        self,
        message: ChatMessage,
    ) -> None:
        pass

    @abstractmethod
    async def messages(
        self,
    ) -> list[ChatMessage]:
        pass

    @abstractmethod
    async def get_state(
        self,
    ) -> ConversationState:
        pass

    @abstractmethod
    async def update_state(
        self,
        state: ConversationState,
    ) -> None:
        pass

    @abstractmethod
    async def clear(
        self,
    ) -> None:
        pass

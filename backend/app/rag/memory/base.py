from abc import ABC
from abc import abstractmethod

from app.rag.memory.schemas import ChatMessage, ConversationState


class BaseMemory(ABC):

    @abstractmethod
    def add(
        self,
        message: ChatMessage,
    ) -> None:
        pass

    @abstractmethod
    def messages(
        self,
    ) -> list[ChatMessage]:
        pass

    @abstractmethod
    def get_state(
        self,
    ) -> ConversationState:
        pass

    @abstractmethod
    def update_state(
        self,
        state: ConversationState,
    ) -> None:
        pass

    @abstractmethod
    def clear(
        self,
    ) -> None:
        pass

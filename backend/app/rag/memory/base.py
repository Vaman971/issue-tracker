from abc import ABC
from abc import abstractmethod

from app.rag.memory.schemas import ChatMessage


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
    def clear(
        self,
    ) -> None:
        pass

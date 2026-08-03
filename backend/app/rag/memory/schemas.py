from dataclasses import dataclass
from enum import Enum


class MessageRole(str, Enum):

    USER = "user"

    ASSISTANT = "assistant"


@dataclass(slots=True)
class ChatMessage:

    role: MessageRole

    content: str

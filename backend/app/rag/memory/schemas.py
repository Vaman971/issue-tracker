from dataclasses import dataclass, field
from enum import Enum


class MessageRole(str, Enum):

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(slots=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(slots=True)
class ConversationState:
    last_question: str = ""
    last_rewritten_query: str = ""
    last_result_ids: list[int] = field(default_factory=list)

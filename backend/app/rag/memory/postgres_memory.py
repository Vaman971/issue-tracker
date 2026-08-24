"""BaseMemory backed by the conversations tables.

Drops in wherever InMemoryMemory is used; RAGService sees no difference
beyond awaiting the calls it already made.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.helpers.conversation_helper import (
    append_message,
    list_messages,
    save_state,
    state_from_dict,
)
from app.models.conversation import Conversation, ConversationMessage
from app.rag.memory.base import BaseMemory
from app.rag.memory.schemas import ChatMessage, ConversationState


class PostgresMemory(BaseMemory):

    def __init__(
        self,
        conversation_id: uuid.UUID,
        session: AsyncSession,
    ) -> None:

        self.conversation_id = conversation_id
        self.session = session

    async def add(
        self,
        message: ChatMessage,
    ) -> None:

        await append_message(
            conversation_id=self.conversation_id,
            message=message,
            db=self.session,
        )

    async def messages(
        self,
    ) -> list[ChatMessage]:

        rows = await list_messages(
            conversation_id=self.conversation_id,
            db=self.session,
        )

        return [
            ChatMessage(role=row.role, content=row.content)
            for row in rows
        ]

    async def get_state(
        self,
    ) -> ConversationState:

        result = await self.session.execute(
            select(Conversation.state).where(
                Conversation.id == self.conversation_id
            )
        )

        return state_from_dict(result.scalar_one_or_none())

    async def update_state(
        self,
        state: ConversationState,
    ) -> None:

        await save_state(
            conversation_id=self.conversation_id,
            state=state,
            db=self.session,
        )

    async def clear(
        self,
    ) -> None:
        """Empty the conversation without deleting the conversation itself."""

        await self.session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id == self.conversation_id
            )
        )

        await save_state(
            conversation_id=self.conversation_id,
            state=ConversationState(),
            db=self.session,
        )

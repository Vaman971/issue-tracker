from app.rag.memory.schemas import ChatMessage


class MemoryFormatter:

    def format(
        self,
        history: list[ChatMessage],
    ) -> str:

        lines = []

        for message in history:

            lines.append(

                f"{message.role.value}: {message.content}"

            )

        return "\n".join(lines)

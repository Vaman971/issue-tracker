from app.rag.context.schemas import ContextDocument
from app.rag.retrievers.schemas import SearchResult
from app.rag.context.base import ContextBase

class ContextBuilder(ContextBase):
    
    def build(self, results: list[SearchResult]) -> list[ContextDocument]:
        
        context: list[ContextDocument] = []

        for result in results:
            if result is not None:
                context.append(
                    ContextDocument(
                        source=f"{result.entity_type}:{result.entity_id}",

                        content=result.content,
                        metadata=result.metadata,
                    )
                )

        return context

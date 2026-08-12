import asyncio

from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.reranking.reranker import OpenAiReranker
from app.rag.retrievers.schemas import SearchResult


async def main() -> None:

    reranker = OpenAiReranker(
        prompt_loader=PromptTemplateLoader(),
    )

    candidates = [
        SearchResult(
            entity_type="issue",
            entity_id=2720,
            chunk_index=1,
            content=(
                "Issue ID: 2720\n"
                "Project: React js project\n"
                "Status: in_progress\n"
                "Priority: critical\n"
                "Title: Session tokens are silently dropped "
                "after the billing dashboard idles\n"
                "Description: Users are logged out after idle "
                "periods because session tokens are silently "
                "dropped. Clock drift appears to contribute."
            ),
            score=0.91,
            metadata={
                "project": "React js project",
                "status": "in_progress",
                "priority": "critical",
            },
        ),
        SearchResult(
            entity_type="issue",
            entity_id=960,
            chunk_index=0,
            content=(
                "Issue ID: 960\n"
                "Project: React js project\n"
                "Status: todo\n"
                "Priority: high\n"
                "Title: Billing dashboard refresh problem\n"
                "Description: The billing dashboard occasionally "
                "fails to refresh after navigation."
            ),
            score=0.84,
            metadata={
                "project": "React js project",
                "status": "todo",
                "priority": "high",
            },
        ),
        SearchResult(
            entity_type="issue",
            entity_id=1201,
            chunk_index=0,
            content=(
                "Issue ID: 1201\n"
                "Project: React js project\n"
                "Status: done\n"
                "Priority: medium\n"
                "Title: Improve billing dashboard layout\n"
                "Description: Reorganize the dashboard navigation "
                "and improve report presentation."
            ),
            score=0.80,
            metadata={
                "project": "React js project",
                "status": "done",
                "priority": "medium",
            },
        ),
    ]

    query = "Which issues have problems caused by clock drift?"

    response = await reranker.rerank(
        query=query,
        results=candidates,
        top_k=3,
    )

    print("=" * 80)
    print("RERANKER TEST")
    print("=" * 80)

    print()
    print(f"Query: {query}")

    print()
    print(f"Model: {response.model}")
    print(f"Input tokens: {response.input_tokens}")
    print(f"Output tokens: {response.output_tokens}")
    print(f"Total tokens: {response.total_tokens}")

    print()
    print("RANKED RESULTS")
    print("-" * 80)

    for index, item in enumerate(response.results, start=1):

        print(
            f"{index}. "
            f"issue:{item.result.entity_id} "
            f"chunk:{item.result.chunk_index} "
            f"score:{item.score:.4f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
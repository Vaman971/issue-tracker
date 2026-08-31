import json

from typing import cast, Any

from app.core.config import settings
from app.rag.llm.client import build_openai_client
from app.rag.llm.usage import read_usage
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.reranking.base import BaseReranker
from app.rag.reranking.schemas import RerankResult, RerankResponse
from app.rag.retrievers.schemas import SearchResult

from app.rag.reranking.candidate import build_rerank_candidate

RERANK_TEMPLATE = "rerank.j2"


class OpenAiReranker(BaseReranker):

    def __init__(
            self,
            prompt_loader: PromptTemplateLoader
    ) -> None:

        self.client = build_openai_client()

        self.prompt_loader = prompt_loader

        self._model = settings.OPENAI_CHAT_MODEL

    @property
    def model(self)-> str:
        return self._model

    async def rerank(
            self,
            query: str,
            results: list[SearchResult],
            top_k: int
    ) -> RerankResponse:

        if not results:
            # rest of the arguments will default to zero
            return RerankResponse(
                results=[]
            )

        candidates = [
            build_rerank_candidate(result)
            for result in results
        ]

        prompt = self.prompt_loader.render(
            RERANK_TEMPLATE,
            query=query,
            results=candidates,
            # only what the pipeline consumes; output length drives latency
            top_k=min(top_k, len(candidates)),
        )

        response = await self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT}),
        )

        # read before parsing: the call was billed either way. Via the shared
        # reader because `output_tokens_details` is absent on some responses,
        # which the previous inline access would have raised on.
        usage = read_usage(response, self._model)

        payload = self._parse_response(
            response.output_text
        )

        if payload is None:
            default =  [
                RerankResult(
                    result=candidate,
                    score=candidate.score
                ) for candidate in results
            ]

            return RerankResponse(
                results = default[:top_k],
                # scores here are the retrieval scores these candidates
                # arrived with; the model judged nothing
                model_scored=False,
                model=usage.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                total_tokens=usage.total_tokens
            ) 

        reranked = self._build_results(
            payload = payload,
            candidates = results,
        )

        return RerankResponse(
                results = reranked[:top_k],
                model=usage.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                total_tokens=usage.total_tokens
            )


    @staticmethod
    def _parse_response(
        text: str,
    )-> dict | None:

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    @staticmethod
    def _build_results(
        payload: dict,
        candidates: list[SearchResult],
    ) -> list[RerankResult]:

        raw_results = payload.get("results")

        if not isinstance(raw_results, list):
            return [
                RerankResult(
                    result=candidate,
                    score=candidate.score
                ) for candidate in candidates
            ]

        candidate_map = {
            (
                result.entity_id,
                result.chunk_index,
            ): result
            for result in candidates
        }

        reranked: list[RerankResult] = []

        seen: set[tuple[int, int]] = set()

        for item in raw_results:

            if not isinstance(item, dict):
                continue

            entity_id = item.get("entity_id")
            chunk_index = item.get("chunk_index")
            score = item.get("score")

            if not isinstance(entity_id, int):
                continue

            if not isinstance(chunk_index, int):
                continue

            if not isinstance(score, (int, float)):
                continue

            score = float(score)

            if not 0.0 <= score <= 1.0:
                continue

            key = (
                entity_id,
                chunk_index,
            )

            if key in seen:
                continue

            candidate = candidate_map.get(key)

            if candidate is None:
                continue

            seen.add(key)

            reranked.append(
                RerankResult(
                    result=candidate,
                    score=score,
                )
            )

        # If the model omitted candidates, preserve them rather than silently
        # losing retrieval results.
        for candidate in candidates:

            key = (
                candidate.entity_id,
                candidate.chunk_index,
            )

            if key in seen:
                continue

            reranked.append(
                RerankResult(
                    result=candidate,
                    score=0.0,
                )
            )

        reranked.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return reranked

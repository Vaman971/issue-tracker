"""One flat record per answered question.

`RAGTrace` is shaped for the human reading `TracePrinter` output — nested by
stage, carrying prompts, documents and answers. That shape is wrong for
telemetry, which wants a fixed set of scalars per request so a log pipeline
can aggregate them without knowing anything about the pipeline's structure.

This module is the boundary between the two. `build_record` reads the trace
and produces the agreed payload; nothing downstream needs to know a
`RerankTrace` exists.

Field names follow the roadmap exactly, including `LLM_TTFT` and
`LLM_total_latency`, because they are a contract with whatever consumes
these logs rather than ordinary Python attributes.
"""

import logging
import uuid
from dataclasses import dataclass

from app.rag.tracing.schema import RAGTrace

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetryRecord:
    """The per-request payload, one field per agreed key."""

    request_id: str | None
    conversation_id: str | None

    # milliseconds, rounded — sub-microsecond precision is noise here
    total_latency: float
    rewrite_latency: float
    filter_latency: float
    multi_query_latency: float
    retrieval_latency: float
    rerank_latency: float
    LLM_TTFT: float
    LLM_total_latency: float

    cache_hits_misses: dict
    retrieval_candidate_count: int
    model_used: str
    input_output_tokens: dict
    cost: dict

    def as_dict(self) -> dict:
        """Plain dict for the log formatter.

        Written out rather than using `asdict()`, which would deep-copy the
        nested dicts for no benefit.
        """

        return {
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "total_latency": self.total_latency,
            "rewrite_latency": self.rewrite_latency,
            "filter_latency": self.filter_latency,
            "multi_query_latency": self.multi_query_latency,
            "retrieval_latency": self.retrieval_latency,
            "rerank_latency": self.rerank_latency,
            "LLM_TTFT": self.LLM_TTFT,
            "LLM_total_latency": self.LLM_total_latency,
            "cache_hits_misses": self.cache_hits_misses,
            "retrieval_candidate_count": self.retrieval_candidate_count,
            "model_used": self.model_used,
            "input_output_tokens": self.input_output_tokens,
            "cost": self.cost,
        }


def _ms(value: float) -> float:
    return round(value, 2)


def _cache_hits_misses(trace: RAGTrace) -> dict:
    """Every cache the turn consulted.

    Embedding and search are counts, not flags: multi-query means several
    lookups per turn, so a turn can be a partial hit. The three LLM-stage
    caches are one lookup each, so they stay booleans.
    """

    retrieval = trace.query.retrieval

    return {
        "embedding": {
            "hits": retrieval.embedding_cache_hits,
            "misses": retrieval.embedding_cache_misses,
        },
        "search": {
            "hits": retrieval.search_cache_hits,
            "misses": retrieval.search_cache_misses,
        },
        "filter": trace.query.filter.cache_hit,
        "multi_query": trace.query.multi_query.cache_hit,
        "rerank": trace.query.rerank.cache_hit,
    }


def _cost(trace: RAGTrace) -> dict:
    """What the turn cost, split by the models that charged for it.

    Only the two stages that record usage are counted. The rewrite, filter
    and multi-query stages also call a model but capture no token counts, so
    `total_usd` is a floor on the true cost, not the whole of it.
    """

    answer_usd = trace.llm.cost_usd
    rerank_usd = trace.query.rerank.cost_usd

    return {
        "answer_usd": round(answer_usd, 6),
        "rerank_usd": round(rerank_usd, 6),
        "total_usd": round(answer_usd + rerank_usd, 6),
    }


def build_record(
    trace: RAGTrace,
    request_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
) -> TelemetryRecord:
    """Flatten a completed trace into the telemetry payload."""

    query = trace.query

    return TelemetryRecord(
        request_id=request_id,
        conversation_id=str(conversation_id) if conversation_id else None,
        total_latency=_ms(trace.total_duration_ms),
        rewrite_latency=_ms(query.rewrite.duration_ms),
        filter_latency=_ms(query.filter.duration_ms),
        multi_query_latency=_ms(query.multi_query.duration_ms),
        retrieval_latency=_ms(query.retrieval.duration_ms),
        rerank_latency=_ms(query.rerank.duration_ms),
        LLM_TTFT=_ms(trace.llm.ttft_ms),
        LLM_total_latency=_ms(trace.llm.ttlt_ms),
        cache_hits_misses=_cache_hits_misses(trace),
        # what retrieval handed to the reranker, before it narrowed the set
        retrieval_candidate_count=len(query.retrieval.final_results),
        model_used=trace.llm.model,
        input_output_tokens={
            "input": trace.llm.input_tokens,
            "output": trace.llm.output_tokens,
            "total": trace.llm.total_tokens,
        },
        cost=_cost(trace),
    )


def emit(record: TelemetryRecord) -> None:
    """Log the record as structured data.

    `extra` rather than the message string, so `JsonFormatter` can nest it as
    an object and a log pipeline can query the fields directly instead of
    parsing prose.
    """

    logger.info(
        "RAG turn completed",
        extra={"telemetry": record.as_dict()},
    )

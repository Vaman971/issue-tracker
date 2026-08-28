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

`cost` and `input_output_tokens` cover every model call a turn makes — the
rewrite, filter, multi-query and rerank stages as well as the answer — so the
totals are the real figures. Both carry a per-stage split, because tuning the
pipeline means knowing which stage is spending.
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


def _model_stages(trace: RAGTrace) -> dict:
    """The pipeline stages that call a model, in the order they run.

    The answer model is handled separately: it streams, so its usage arrives
    through a different path and its trace has a different shape.
    """

    return {
        "rewrite": trace.query.rewrite,
        "filter": trace.query.filter,
        "multi_query": trace.query.multi_query,
        "rerank": trace.query.rerank,
    }


def _cost(trace: RAGTrace) -> dict:
    """What the turn cost, split by the stage that spent it.

    Every stage that calls a model is counted, so `total_usd` is the real
    figure rather than a floor. A stage reports zero when it was skipped,
    served from cache, or resolved without a model — so summing costs across
    a conversation never charges twice for work done once.
    """

    costs = {
        f"{name}_usd": stage.cost_usd
        for name, stage in _model_stages(trace).items()
    }

    costs["answer_usd"] = trace.llm.cost_usd

    total = sum(costs.values())

    return {key: round(value, 6) for key, value in costs.items()} | {
        "total_usd": round(total, 6),
    }


def _tokens(trace: RAGTrace) -> dict:
    """Tokens for the whole turn, and the per-stage split behind it.

    The totals cover every model call, not just the answer — tuning the
    pipeline means knowing which stage is spending the tokens, and reasoning
    tokens are broken out because they are the usual reason a cheap-looking
    stage is not.
    """

    by_stage = {
        name: {
            # per stage, because they do not all run on the same model
            "model": stage.model,
            "input": stage.input_tokens,
            "output": stage.output_tokens,
            "reasoning": stage.reasoning_tokens,
        }
        for name, stage in _model_stages(trace).items()
    }

    by_stage["answer"] = {
        "model": trace.llm.model,
        "input": trace.llm.input_tokens,
        "output": trace.llm.output_tokens,
        "reasoning": trace.llm.reasoning_tokens,
    }

    total_input = sum(stage["input"] for stage in by_stage.values())
    total_output = sum(stage["output"] for stage in by_stage.values())

    return {
        "input": total_input,
        "output": total_output,
        "total": total_input + total_output,
        "by_stage": by_stage,
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
        input_output_tokens=_tokens(trace),
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

from app.rag.query_pipeline.schemas import ProcessedQuery, QueryRequest
from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.tracing.schema import QueryTrace


class ConfidenceGateStage(BaseQueryStage):
    """Declines a turn when retrieval found nothing relevant enough.

    Covers the failure the router cannot: a question that genuinely belongs
    to this system, asked about something the corpus has no answer for.
    Vector search always returns its nearest neighbours — distance is never
    "none" — so without this the answer prompt receives five unrelated issues
    and, being told to list whatever is relevant, lists them.

    The reranker has already scored how well each candidate answers the
    question, so the judgement is free: no extra model call, just a
    comparison against a threshold.

    Runs last, after consolidation, so it judges exactly the set the answer
    model would otherwise have received.

    On the threshold: measured, not guessed. Across questions with real
    matches the top score ran 0.74-0.99; across plausible questions with
    nothing in the corpus it ran 0.06-0.18. `RAG_MIN_RELEVANCE_SCORE` sits
    in that gap. Re-measure before changing the reranker's model or prompt,
    since the scores are that model's opinion and nothing more.
    """

    def __init__(
        self,
        minimum_score: float,
    ) -> None:
        self.minimum_score = minimum_score

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        trace.gate.threshold = self.minimum_score
        trace.gate.top_score = processed.top_relevance or 0.0

        processed.low_confidence = self._is_low_confidence(processed)
        trace.gate.passed = not processed.low_confidence

        return processed

    def _is_low_confidence(self, processed: ProcessedQuery) -> bool:
        """Whether the retrieved set is too weak to answer from.

        Note what is deliberately NOT gated: `top_relevance` of None. That
        means no relevance judgement exists — the reranker's output could not
        be parsed, or no reranker ran at all — and a missing judgement is not
        evidence of a bad one. Declining there would turn a rare parsing
        failure into a refused answer, when the pipeline's existing fallback
        already degrades to retrieval order perfectly well.
        """

        if not processed.results:
            return True

        if processed.top_relevance is None:
            return False

        return processed.top_relevance < self.minimum_score

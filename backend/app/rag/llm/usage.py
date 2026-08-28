"""Reads token usage off an OpenAI Responses API result.

Every adapter needs the same four numbers, and the SDK reports them behind
optional attributes — `usage` is None when a call fails partway, and
`output_tokens_details` is absent on models that do no reasoning. Written out
once here rather than as a ternary repeated four times in each of five
adapters.
"""

from app.rag.llm.schemas import LLMUsage


def read_usage(response, model: str) -> LLMUsage:
    """Token counts for one call, zeroed when the provider reported none."""

    reported = getattr(response, "usage", None)

    if reported is None:
        return LLMUsage(model=model)

    details = getattr(reported, "output_tokens_details", None)

    return LLMUsage(
        model=model,
        input_tokens=reported.input_tokens,
        output_tokens=reported.output_tokens,
        reasoning_tokens=getattr(details, "reasoning_tokens", 0) if details else 0,
        total_tokens=reported.total_tokens,
    )

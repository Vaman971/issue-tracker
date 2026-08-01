"""Token pricing used to estimate the cost of a single LLM call.

Rates are USD per 1M tokens and are provider-agnostic — the lookup is keyed by
model name, so adding a non-OpenAI model means adding a row here and nothing
else. Prices change; treat this table as configuration, not as a constant.
"""

# model -> (input USD per 1M tokens, output USD per 1M tokens)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost, or 0.0 for a model with no known rate."""
    if model not in MODEL_PRICING:
        return 0.0

    input_rate, output_rate = MODEL_PRICING[model]

    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

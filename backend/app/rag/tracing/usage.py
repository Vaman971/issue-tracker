"""Records what one model call consumed onto the stage trace that made it.

Kept out of the stages because all five would otherwise repeat the same five
assignments plus the pricing lookup, and a stage that forgot the lookup would
silently report a cost of zero.
"""

from typing import Protocol

from app.rag.llm.pricing import estimate_cost
from app.rag.llm.schemas import LLMUsage


class SupportsUsage(Protocol):
    """The fields every stage trace exposes for its model call.

    A Protocol rather than a base class: the trace dataclasses use `slots`,
    and structural typing keeps the checker useful without making them
    inherit from anything.
    """

    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float


def record_usage(trace: SupportsUsage, usage: LLMUsage) -> None:
    """Copy a call's usage onto a stage trace and price it.

    Cost uses input and output only. Reasoning tokens are already counted
    inside `output_tokens` by the Responses API, so adding them would bill
    the same tokens twice.
    """

    trace.model = usage.model
    trace.input_tokens = usage.input_tokens
    trace.output_tokens = usage.output_tokens
    trace.reasoning_tokens = usage.reasoning_tokens

    trace.cost_usd = estimate_cost(
        usage.model,
        usage.input_tokens,
        usage.output_tokens,
    )

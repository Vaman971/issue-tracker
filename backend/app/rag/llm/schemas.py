from dataclasses import dataclass


@dataclass(slots=True)
class LLMResponse:

    content: str

    model: str

    input_tokens: int

    output_tokens: int

    total_tokens: int

@dataclass(slots=True)
class LLMUsage:
    """What one model call consumed.

    Used two ways. `stream()` fills it in as a sink, because streaming yields
    text and token counts only arrive at the end, and passing a sink keeps the
    iterator's element type a plain `str`. The non-streaming adapters return
    it on their result, built by `read_usage`.
    """

    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    # a SUBSET of output_tokens, not an addition to them — the Responses API
    # bills reasoning as output, so cost must not count it twice
    reasoning_tokens: int = 0

    total_tokens: int = 0

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
    """Filled in by `stream()` when the provider reports usage.

    Streaming yields text, so token counts can only arrive at the end.
    Passing a sink keeps the iterator's element type a plain `str`.
    """

    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    total_tokens: int = 0

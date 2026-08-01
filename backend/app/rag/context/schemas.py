from dataclasses import dataclass

@dataclass(slots=True)
class ContextDocument:

    source: str

    content: str

    metadata: dict
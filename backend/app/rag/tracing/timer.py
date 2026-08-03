from time import perf_counter

class Timer:
    def __init__(self):
        self.start = perf_counter()

    def elapsed_ms(self)-> float:
        return (perf_counter() - self.start) * 1000


def format_ms(milliseconds: float) -> str:
    """Render a duration for display: sub-second in ms, longer in seconds."""
    if milliseconds < 1000:
        return f"{milliseconds:.0f} ms"
    return f"{milliseconds / 1000:.2f} s"

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent / "templates"


class PromptTemplateLoader:
    """Renders prompt templates.

    Jinja2 is an implementation detail kept entirely inside this class; the
    rest of the codebase only calls `render(...)`. Swapping the templating
    engine means changing only this file.
    """

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,          # prompts are plain text, not HTML
            trim_blocks=True,          # drop the newline after a block tag
            lstrip_blocks=True,        # strip leading whitespace before a block tag
            undefined=StrictUndefined, # missing context vars raise instead of rendering ""
        )

    def render(self, template_name: str, **context) -> str:
        template = self._env.get_template(template_name)
        return template.render(**context)

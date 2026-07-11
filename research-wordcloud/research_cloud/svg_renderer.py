from __future__ import annotations

import html
from pathlib import Path

from .config import WordcloudConfig


def render_svg(records: list[dict[str, object]], config: WordcloudConfig, output: Path) -> None:
    elements = []
    for item in records:
        word = html.escape(str(item["word"]))
        transform = f"translate({item['x']} {item['y']}) rotate({item['rotate']})"
        elements.append(
            f'<text transform="{transform}" font-size="{item["font_size"]}" fill="{item["color"]}" '
            f'font-family="Arial, Helvetica, sans-serif" font-weight="600" dominant-baseline="hanging">{word}</text>'
        )
    background = config.background_color if config.background_color != "transparent" else "none"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {config.width} {config.height}" '
        f'width="{config.width}" height="{config.height}" role="img" aria-label="Research interests word cloud">'
        f'<rect width="100%" height="100%" fill="{background}"/>'
        + "".join(elements)
        + "</svg>"
    )
    (output / "wordcloud.svg").write_text(svg, encoding="utf-8")

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import AppConfig
from .models import PaperAnalysis, Topic


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_interactive(records: list[dict[str, object]], config: AppConfig, output: Path) -> None:
    template = _environment().get_template("wordcloud.html.j2")
    html = template.render(
        width=config.wordcloud.width,
        height=config.wordcloud.height,
        background_color=config.wordcloud.background_color if config.wordcloud.background_color != "transparent" else "#FAFBFD",
        records_json=json.dumps(records, ensure_ascii=False).replace("</", "<\\/"),
        new_tab=config.website.open_links_in_new_tab,
    )
    (output / "wordcloud.html").write_text(html, encoding="utf-8")


def render_report(
    papers: list[PaperAnalysis],
    topics: list[Topic],
    summary_markdown: str,
    config: AppConfig,
    output: Path,
) -> None:
    template = _environment().get_template("report.html.j2")
    categories: dict[str, int] = {}
    for topic in topics:
        categories[topic.category] = categories.get(topic.category, 0) + 1
    warnings = [f"{paper.file}: {warning}" for paper in papers for warning in paper.warnings]
    html = template.render(
        papers=papers,
        topics=topics,
        summary_markdown=summary_markdown,
        categories=sorted(categories.items(), key=lambda item: (-item[1], item[0])),
        warnings=warnings,
        new_tab=config.website.open_links_in_new_tab,
    )
    (output / "report.html").write_text(html, encoding="utf-8")

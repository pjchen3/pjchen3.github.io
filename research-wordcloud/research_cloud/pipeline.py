from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cache import AnalysisCache
from .config import AppConfig, TopicOverrides, load_overrides
from .html_renderer import render_interactive, render_report
from .llm_extractor import enrich_with_llm
from .models import PaperAnalysis, Topic
from .normalization import TermNormalizer
from .pdf_parser import discover_pdfs, extract_pdf
from .report import build_research_summary, build_timeline
from .svg_renderer import render_svg
from .topic_extractor import analyze_sections
from .weighting import aggregate_topics
from .wordcloud_renderer import layout_records, render_pngs


LOGGER = logging.getLogger("research_cloud")


@dataclass
class RunResult:
    papers: list[PaperAnalysis]
    topics: list[Topic]
    found: int
    cached: int
    analyzed: int
    failed: int


STARTER_OVERRIDES = {
    "rename": {},
    "merge": {},
    "exclude": [],
    "force_include": {},
    "category_override": {},
}


def _write_json(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, list):
        value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def run_analysis(
    input_directory: Path,
    output_directory: Path,
    config: AppConfig,
    *,
    force: bool = False,
    overrides_path: Path | None = None,
) -> RunResult:
    output_directory.mkdir(parents=True, exist_ok=True)
    if overrides_path is None:
        overrides_path = output_directory / "topic_overrides.yaml"
    if not overrides_path.exists():
        overrides_path.write_text(yaml.safe_dump(STARTER_OVERRIDES, sort_keys=False), encoding="utf-8")
    overrides: TopicOverrides = load_overrides(overrides_path)
    normalizer = TermNormalizer(config.topics, overrides)
    pdfs = discover_pdfs(input_directory, config.input.recursive)
    LOGGER.info("%d PDFs found", len(pdfs))
    if not pdfs:
        raise ValueError(f"No PDF files found in {input_directory}")

    cache = AnalysisCache(output_directory / ".cache", config.fingerprint())
    papers: list[PaperAnalysis] = []
    cached = analyzed = failed = 0
    for pdf in pdfs:
        try:
            paper = None if force else cache.load(pdf)
            if paper is not None:
                cached += 1
                LOGGER.debug("Cache hit: %s", pdf.name)
            else:
                sections = extract_pdf(pdf, config.extraction)
                paper = analyze_sections(pdf, sections, config, normalizer)
                if config.llm.enabled and config.llm.provider != "none":
                    paper = enrich_with_llm(paper, sections, config.llm)
                cache.store(pdf, paper)
                analyzed += 1
            papers.append(paper)
        except Exception as exc:
            failed += 1
            LOGGER.error("Failed to analyze %s: %s", pdf.name, exc)

    if not papers:
        raise RuntimeError("All PDFs failed analysis; see log messages above")
    topics = aggregate_topics(papers, config, normalizer, overrides)
    if not topics:
        raise RuntimeError("No usable topics were extracted; consider adding force_include entries or checking PDF text extraction")

    _write_json(output_directory / "papers.json", papers)
    _write_json(output_directory / "topics.json", topics)
    summary = build_research_summary(papers, topics)
    (output_directory / "research_summary.md").write_text(summary, encoding="utf-8")
    timeline = build_timeline(papers, topics, output_directory)
    _write_json(output_directory / "timeline.json", timeline)
    cloud = render_pngs(topics, config.wordcloud, output_directory)
    records = layout_records(cloud, topics)
    render_svg(records, config.wordcloud, output_directory)
    render_interactive(records, config, output_directory)
    render_report(papers, topics, summary, config, output_directory)
    LOGGER.info("%d loaded from cache, %d newly analyzed, %d failed", cached, analyzed, failed)
    return RunResult(papers=papers, topics=topics, found=len(pdfs), cached=cached, analyzed=analyzed, failed=failed)


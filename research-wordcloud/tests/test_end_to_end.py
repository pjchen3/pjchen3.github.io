import json
from pathlib import Path

import yaml

from research_cloud.cache import AnalysisCache
from research_cloud.cli import main
from research_cloud.config import AppConfig, load_config
from research_cloud.models import PaperAnalysis, Topic
from research_cloud.pipeline import run_analysis


def test_cache_hit(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"synthetic")
    cache = AnalysisCache(tmp_path / ".cache", "fingerprint")
    paper = PaperAnalysis(file=pdf.name, title="Synthetic")
    cache.store(pdf, paper)
    assert cache.load(pdf) == paper
    pdf.write_bytes(b"changed")
    assert cache.load(pdf) is None


def test_config_file_and_cli_style_overrides(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("topics:\n  final_max_words: 12\nweighting:\n  use_recency: true\n")
    config = load_config(config_path, {"topics": {"min_paper_count": 2}})
    assert config.topics.final_max_words == 12
    assert config.topics.min_paper_count == 2
    assert config.weighting.use_recency


def test_end_to_end_without_llm_and_output_schemas(tmp_path: Path, synthetic_pdf_factory):
    papers_dir = tmp_path / "papers"
    output_dir = tmp_path / "output"
    papers_dir.mkdir()
    synthetic_pdf_factory(papers_dir / "one.pdf", title="Planetary Nebulae and Central Stars", year=2025, terms="planetary nebulae and central stars", instrument="HST")
    synthetic_pdf_factory(papers_dir / "two.pdf", title="Mass Loss from Planetary Nebulae in M31", year=2026, terms="planetary nebulae in M31", instrument="Gaia")
    config = AppConfig()
    assert not config.llm.enabled
    result = run_analysis(papers_dir, output_dir, config)
    assert result.failed == 0
    expected = {
        "papers.json", "topics.json", "research_summary.md", "wordcloud.png", "wordcloud_transparent.png",
        "wordcloud.svg", "wordcloud.html", "report.html", "timeline.json", "topic_timeline.png", "topic_overrides.yaml",
    }
    assert expected <= {p.name for p in output_dir.iterdir()}
    assert all((output_dir / name).stat().st_size > 100 for name in expected - {"topic_overrides.yaml"})
    papers = [PaperAnalysis.model_validate(item) for item in json.loads((output_dir / "papers.json").read_text())]
    topics = [Topic.model_validate(item) for item in json.loads((output_dir / "topics.json").read_text())]
    assert len(papers) == 2
    assert any(topic.term == "planetary nebulae" and topic.paper_count == 2 for topic in topics)
    assert not ({"ABSTRACT", "INTRODUCTION", "CONCLUSIONS", "SUMMARY"} & {topic.term for topic in topics})
    assert "Interactive research topic cloud" in (output_dir / "wordcloud.html").read_text()
    assert (output_dir / "wordcloud.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "wordcloud.svg").read_text().startswith("<svg")


def test_cli_short_form(tmp_path: Path, synthetic_pdf_factory):
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    synthetic_pdf_factory(papers_dir / "one.pdf", title="Mira Variables in M31", year=2026, terms="Mira variables in M31", instrument="ZTF")
    output = tmp_path / "site-assets"
    assert main([str(papers_dir), "--output", str(output), "--max-words", "20"]) == 0
    assert (output / "topics.json").exists()

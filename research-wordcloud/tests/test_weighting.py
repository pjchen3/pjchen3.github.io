from pathlib import Path

from research_cloud.config import AppConfig
from research_cloud.models import PaperAnalysis, SectionBundle
from research_cloud.normalization import TermNormalizer
from research_cloud.topic_extractor import analyze_sections
from research_cloud.weighting import aggregate_topics


def _paper(file: str, scores: dict[str, float]) -> PaperAnalysis:
    return PaperAnalysis(
        file=file,
        title=file,
        topic_phrases=list(scores),
        topic_scores=scores,
        topic_categories={term: "object" for term in scores},
    )


def test_repetition_inside_one_paper_is_bounded():
    config = AppConfig()
    normalizer = TermNormalizer(config.topics)
    base = dict(title="Synthetic", abstract="", conclusion="", raw_text_length=3000)
    once = analyze_sections(Path("a.pdf"), SectionBundle(**base, main_text="planetary nebulae"), config, normalizer)
    repeated = analyze_sections(Path("b.pdf"), SectionBundle(**base, main_text=("planetary nebulae " * 500)), config, normalizer)
    assert repeated.topic_scores["planetary nebulae"] < once.topic_scores["planetary nebulae"] * 1.7


def test_cross_paper_coverage_outranks_single_paper_repetition():
    config = AppConfig()
    normalizer = TermNormalizer(config.topics)
    papers = [
        _paper("a.pdf", {"planetary nebulae": 1, "mira variables": 100}),
        _paper("b.pdf", {"planetary nebulae": 10}),
        _paper("c.pdf", {"planetary nebulae": 10}),
    ]
    topics = {topic.term: topic for topic in aggregate_topics(papers, config, normalizer)}
    assert topics["planetary nebulae"].weight > topics["mira variables"].weight
    assert topics["planetary nebulae"].paper_count == 3


from pathlib import Path

from research_cloud.config import AppConfig, TopicOverrides, TopicsConfig
from research_cloud.models import SectionBundle
from research_cloud.normalization import TermNormalizer
from research_cloud.topic_extractor import analyze_sections


def test_abbreviations_plural_and_synonyms_merge():
    normalizer = TermNormalizer(TopicsConfig())
    assert normalizer.canonicalize("PN") == "planetary nebulae"
    assert normalizer.canonicalize("PNe") == "planetary nebulae"
    assert normalizer.canonicalize("planetary nebula") == "planetary nebulae"
    assert normalizer.canonicalize("Andromeda Galaxy") == "M31"
    assert normalizer.canonicalize("gaia") == "Gaia"


def test_multiword_phrases_are_preserved():
    config = AppConfig()
    normalizer = TermNormalizer(config.topics)
    sections = SectionBundle(
        title="Mass Loss in Planetary Nebulae",
        abstract="We study planetary nebulae, central stars, and late-stage stellar evolution.",
        conclusion="We find that mass loss shapes planetary nebulae.",
        main_text="planetary nebulae central stars mass loss",
        raw_text_length=2000,
    )
    paper = analyze_sections(Path("synthetic.pdf"), sections, config, normalizer)
    assert "planetary nebulae" in paper.topic_phrases
    assert "mass loss" in paper.topic_phrases
    assert "planetary" not in paper.topic_phrases
    assert "stars mass loss" not in paper.topic_phrases


def test_user_merge_rename_exclude_and_category_override():
    overrides = TopicOverrides(
        rename={"custom pns": "Planetary Nebulae"},
        merge={"stellar remnants": ["remnant sample"]},
        exclude=["bad topic"],
        category_override={"stellar remnants": "physical_process"},
    )
    normalizer = TermNormalizer(TopicsConfig(), overrides)
    assert normalizer.canonicalize("custom pns") == "planetary nebulae"
    assert normalizer.canonicalize("remnant sample") == "stellar remnants"
    assert normalizer.is_excluded("bad topic")
    assert normalizer.category("stellar remnants") == "physical_process"

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

from .config import AppConfig, TopicOverrides
from .models import PaperAnalysis, Topic, paper_ref
from .normalization import TermNormalizer


SUMMARY_TEMPLATES = {
    "object": "Research on {term} and their astrophysical properties and evolution.",
    "physical_process": "Studies of {term} across the publication set.",
    "science_question": "Investigations addressing {term}.",
    "method": "Use and development of {term} for astrophysical analysis.",
    "survey_or_instrument": "Research using observations or products from {term}.",
    "galaxy_or_environment": "Studies carried out in or focused on {term}.",
    "general_field": "A recurring research area supported by multiple publication topics.",
}

FIELD_RULES = {
    "late-stage stellar evolution": {"planetary nebulae", "central stars", "asymptotic giant branch stars", "mass loss", "white dwarfs"},
    "time-domain astronomy": {"long-period variables", "mira variables", "pulsating variables", "time-series photometry", "period analysis", "ZTF", "TESS"},
    "extragalactic stellar astrophysics": {"M31", "M33", "Local Group", "nearby galaxies", "stellar populations"},
    "binary evolution": {"binary evolution", "post-common-envelope binaries", "common-envelope evolution", "mass transfer", "binary stars", "hierarchical triple systems", "stellar mergers", "post-AGB stars"},
    "stellar populations": {"stellar populations", "open clusters", "globular clusters", "metallicity distribution", "formation history"},
}


def _recency(year: int | None, config: AppConfig) -> float:
    if not config.weighting.use_recency or not year:
        return 1.0
    age = max(0, datetime.now().year - year)
    # Floor at 0.5 so old work remains visible.
    return 0.5 + 0.5 * math.pow(2.0, -age / max(config.weighting.recency_half_life_years, 0.1))


def _author_weight(paper: PaperAnalysis, config: AppConfig) -> float:
    if not config.author.name:
        return 1.0
    if paper.matched_author_role == "first":
        return config.author.first_author_weight
    if paper.matched_author_role == "coauthor":
        return config.author.coauthor_weight
    return config.author.coauthor_weight


def _level(category: str) -> int:
    if category == "general_field":
        return 1
    if category in {"method", "survey_or_instrument"}:
        return 3
    return 2


def _display_name(term: str) -> str:
    words = []
    for word in term.split():
        if word.upper() in {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}:
            words.append(word.upper())
        elif word.startswith("post-") and any(char.isupper() for char in word[5:]):
            words.append("Post-" + word[5:])
        elif word.isupper() or any(char.isupper() for char in word[1:]):
            words.append(word)
        else:
            words.append(word.title())
    return " ".join(words)


def aggregate_topics(
    papers: list[PaperAnalysis],
    config: AppConfig,
    normalizer: TermNormalizer,
    overrides: TopicOverrides | None = None,
) -> list[Topic]:
    overrides = overrides or TopicOverrides()
    per_term: dict[str, list[tuple[PaperAnalysis, float]]] = defaultdict(list)
    aliases: dict[str, set[str]] = defaultdict(set)
    categories: dict[str, str] = {}

    for paper in papers:
        if not paper.topic_scores:
            continue
        max_score = max(paper.topic_scores.values()) or 1.0
        for raw_term, raw_score in paper.topic_scores.items():
            term = normalizer.canonicalize(raw_term)
            if normalizer.is_excluded(term):
                continue
            # Normalize inside each paper first; total mentions cannot grow without bound.
            paper_importance = min(1.0, raw_score / max_score)
            score = paper_importance * _recency(paper.year, config) * _author_weight(paper, config)
            per_term[term].append((paper, score))
            aliases[term].update(paper.matched_forms.get(raw_term, []))
            aliases[term].update(normalizer.aliases_for(term))
            categories[term] = paper.topic_categories.get(raw_term, normalizer.category(term))

    raw_weights: dict[str, float] = {}
    for term, occurrences in per_term.items():
        coverage = len({p.file for p, _ in occurrences})
        mean_importance = sum(score for _, score in occurrences) / coverage
        coverage_weight = coverage * (1.0 + 0.22 * math.log1p(coverage))
        raw_weights[term] = coverage_weight * mean_importance * (1.0 + 0.1 * max(0, len(term.split()) - 1))

    # Infer broad first-level fields only when concrete evidence exists.
    for field, evidence_terms in FIELD_RULES.items():
        evidence = [term for term in per_term if term.casefold() in {x.casefold() for x in evidence_terms}]
        if not evidence:
            continue
        related: dict[str, PaperAnalysis] = {}
        for term in evidence:
            for paper, _ in per_term[term]:
                related[paper.file] = paper
        per_term[field] = [(paper, 1.0) for paper in related.values()]
        raw_weights[field] = max(raw_weights[x] for x in evidence) * 1.08
        categories[field] = "general_field"

    force = {**config.topics.force_include, **overrides.force_include}
    for display_term, details in force.items():
        term = normalizer.canonicalize(display_term)
        categories[term] = details.get("category", "general_field")
        configured_weight = float(details.get("weight", 100.0))
        raw_weights[term] = max(raw_weights.get(term, 0.0), configured_weight)
        if term not in per_term and papers:
            per_term[term] = [(paper, 1.0) for paper in papers]

    eligible = {
        term: value for term, value in raw_weights.items()
        if len({p.file for p, _ in per_term[term]}) >= config.topics.min_paper_count
    }
    if not eligible:
        return []
    minimum, maximum = min(eligible.values()), max(eligible.values())

    def scale(value: float) -> float:
        if maximum == minimum:
            return 100.0
        return 1.0 + 99.0 * (value - minimum) / (maximum - minimum)

    topics: list[Topic] = []
    for term, raw_weight in eligible.items():
        paper_map = {paper.file: paper for paper, _ in per_term[term]}
        category = categories.get(term, normalizer.category(term))
        display = config.topics.display_names.get(term, _display_name(term))
        warning_list = []
        if len(paper_map) == 1:
            warning_list.append("This topic is supported by only one paper")
        if len(term.split()) == 1 and term.casefold() in {"astronomy", "astrophysics", "evolution", "stars", "galaxies"}:
            warning_list.append("This high-level term may be too broad")
        topics.append(Topic(
            term=term,
            display_name=display,
            weight=round(scale(raw_weight), 2),
            category=category,  # type: ignore[arg-type]
            level=_level(category),
            paper_count=len(paper_map),
            papers=[paper_ref(p, config.website.paper_base_url, config.website.paper_links) for p in sorted(paper_map.values(), key=lambda x: (x.year or 0, x.title), reverse=True)],
            aliases=sorted({x for x in aliases[term] if x.casefold() != term.casefold()}, key=str.casefold),
            summary=SUMMARY_TEMPLATES[category].format(term=display),
            warnings=warning_list,
        ))
    topics.sort(key=lambda topic: (-topic.weight, topic.display_name.casefold()))
    return topics[: config.topics.final_max_words]

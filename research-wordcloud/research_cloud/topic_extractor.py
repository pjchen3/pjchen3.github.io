from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

from .config import AppConfig
from .metadata import infer_metadata
from .models import PaperAnalysis, SectionBundle
from .normalization import CATEGORY_TERMS, TermNormalizer, normalize_surface


SECTION_WEIGHTS = {
    "title": 5.0,
    "keywords": 4.5,
    "abstract": 4.0,
    "conclusion": 3.5,
    "introduction_goals": 3.0,
    "headings": 2.5,
    "captions": 1.3,
    "main_text": 1.0,
}

BAD_BOUNDARY_WORDS = {
    "we", "our", "these", "those", "such", "other", "several", "many", "most", "more", "less", "high", "low", "new",
    "using", "used", "based", "found", "present", "show", "derive", "determine", "investigate", "study", "paper", "result",
    "apply", "applied", "perform", "performed", "measure", "measured", "examine", "explore",
}

SCIENTIFIC_HINTS = {
    "star", "stars", "stellar", "nebula", "nebulae", "binary", "binaries", "variable", "variables", "cluster", "clusters",
    "galaxy", "galaxies", "evolution", "formation", "population", "populations", "photometry", "spectroscopy", "survey",
    "telescope", "analysis", "classification", "catalog", "catalogue", "relation", "distribution", "mass", "velocity", "velocities",
    "metallicity", "pulsation", "astrometry", "imaging", "environment", "environments", "light", "curve", "curves", "period",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|M\s?\d{1,3}", text)


def _candidate_ngrams(text: str, normalizer: TermNormalizer) -> list[str]:
    candidates: list[str] = []
    known_canonicals = {
        normalizer.canonicalize(term).casefold()
        for terms in CATEGORY_TERMS.values()
        for term in terms
    } | {canonical.casefold() for _, canonical in normalizer.known_forms()}
    lowered_text = text.casefold()
    present_known_surfaces = {
        alias
        for alias, _canonical in normalizer.known_forms()
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", lowered_text, re.I)
    }
    # Punctuation and line boundaries are hard phrase boundaries. Ignoring them creates
    # artifacts such as "mass loss stellar" across adjacent author keywords.
    segments = [segment for segment in re.split(r"[\n;,:.!?()[\]{}]+", text) if segment.strip()]
    for segment in segments:
        tokens = _tokens(segment)
        for n in (3, 2, 1):
            for i in range(len(tokens) - n + 1):
                phrase_tokens = tokens[i : i + n]
                low = [x.casefold() for x in phrase_tokens]
                if low[0] in normalizer.stopwords | BAD_BOUNDARY_WORDS or low[-1] in normalizer.stopwords | BAD_BOUNDARY_WORDS:
                    continue
                phrase = " ".join(phrase_tokens)
                canonical = normalizer.canonicalize(phrase)
                known = canonical.casefold() != normalize_surface(phrase).casefold() or canonical.casefold() in known_canonicals
                informative = [word for word in low if word not in normalizer.stopwords]
                if not known:
                    if n == 1:
                        if not (phrase.isupper() and 2 <= len(phrase) <= 12):
                            continue
                    else:
                        phrase_folded = " ".join(low)
                        if any(
                            phrase_folded != surface
                            and re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase_folded)}(?![A-Za-z0-9])", surface)
                            for surface in present_known_surfaces
                        ):
                            continue
                        # Do not keep accidental boundary phrases such as "mass loss stellar"
                        # when the complete, known constituent "mass loss" is already available.
                        if any(word in normalizer.stopwords for word in low):
                            continue
                        contains_known_subphrase = any(
                            " ".join(low[start:end]) in known_canonicals
                            for start in range(n)
                            for end in range(start + 1, n + 1)
                            if end - start < n
                        )
                        if contains_known_subphrase:
                            continue
                        if not (set(low) & SCIENTIFIC_HINTS or any(x.endswith(("tion", "metry", "scopy", "synthesis")) for x in low)):
                            continue
                if informative and not normalizer.is_excluded(canonical):
                    candidates.append(phrase)
    return candidates


def _matched_known_terms(text: str, normalizer: TermNormalizer) -> list[str]:
    found: list[str] = []
    lowered = text.casefold()
    for alias, canonical in normalizer.known_forms():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", lowered, re.I):
            found.append(canonical)
    return found


def _specificity(term: str) -> float:
    words = re.findall(r"[A-Za-z0-9]+", term)
    phrase_bonus = min(1.6, 1.0 + 0.22 * max(0, len(words) - 1))
    acronym_bonus = 1.12 if term.isupper() and 2 <= len(term) <= 12 else 1.0
    return phrase_bonus * acronym_bonus


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if 35 <= len(s.strip()) <= 500]


def _main_results(conclusion: str) -> list[str]:
    sentences = _split_sentences(conclusion)
    prioritized = [
        sentence for sentence in sentences
        if re.search(r"\b(?:we (?:find|found|show|derive|confirm|discover)|our results?|indicat(?:e|es)|demonstrat(?:e|es))\b", sentence, re.I)
    ]
    return (prioritized or sentences)[:5]


def _author_role(authors: list[str], config: AppConfig, metadata_author: str = "") -> str:
    if not config.author.name:
        return "unknown"
    aliases = [config.author.name, *config.author.aliases]
    normalized_aliases = {re.sub(r"[^a-z]", "", a.casefold()) for a in aliases}
    normalized_metadata = re.sub(r"[^a-z]", "", metadata_author.casefold())
    if any(alias == normalized_metadata for alias in normalized_aliases):
        return "first"
    matches = []
    for index, author in enumerate(authors):
        normalized_author = re.sub(r"[^a-z]", "", author.casefold())
        if any(
            len(alias) >= 5 and (alias in normalized_author or normalized_author in alias)
            for alias in normalized_aliases
        ):
            matches.append(index)
    if not matches:
        return "unknown"
    return "first" if matches[0] == 0 else "coauthor"


def analyze_sections(
    path: Path,
    sections: SectionBundle,
    config: AppConfig,
    normalizer: TermNormalizer,
) -> PaperAnalysis:
    year, authors, journal = infer_metadata(path, sections)
    section_texts = {
        "title": sections.title,
        "keywords": "; ".join(sections.keywords),
        "abstract": sections.abstract,
        "conclusion": sections.conclusion,
        "introduction_goals": sections.introduction_goals,
        "headings": "; ".join(sections.headings),
        "captions": sections.captions,
        # Main text is deliberately weak and length-limited; references were already removed.
        "main_text": sections.main_text[:120000],
    }
    scores: dict[str, float] = defaultdict(float)
    matched_forms: dict[str, set[str]] = defaultdict(set)
    section_hits: dict[str, set[str]] = defaultdict(set)

    for section, text in section_texts.items():
        if not text:
            continue
        raw_candidates = _matched_known_terms(text, normalizer) + _candidate_ngrams(text, normalizer)
        counts: dict[str, int] = defaultdict(int)
        for raw in raw_candidates:
            canonical = normalizer.canonicalize(raw)
            if normalizer.is_excluded(canonical):
                continue
            counts[canonical] += 1
            matched_forms[canonical].add(normalize_surface(raw))
        for canonical, count in counts.items():
            # log/cap prevents a long paper from dominating through repetition.
            repetition = 1.0 + 0.22 * math.log1p(min(count, 8))
            semantic = 1.18 if normalizer.category(canonical) in {"object", "science_question", "physical_process"} else 1.0
            scores[canonical] += SECTION_WEIGHTS[section] * repetition * semantic * _specificity(canonical)
            section_hits[canonical].add(section)

    ranked = sorted(scores, key=lambda term: (-scores[term], term.casefold()))[: config.topics.max_topics_per_paper]
    categories = {term: normalizer.category(term) for term in ranked}

    def terms_for(category: str) -> list[str]:
        return [term for term in ranked if categories[term] == category]

    confidence_parts = [bool(sections.title), bool(sections.abstract), bool(sections.conclusion), sections.raw_text_length >= 1000]
    confidence = min(1.0, 0.2 + 0.2 * sum(confidence_parts))
    warnings = list(dict.fromkeys(sections.warnings))
    if year is None:
        warnings.append("Publication year could not be identified")
    author_role = _author_role(authors, config, sections.metadata_author)
    if config.author.name and author_role == "unknown":
        warnings.append("Configured author name was not found reliably")

    return PaperAnalysis(
        file=path.name,
        title=sections.title,
        year=year,
        authors=authors,
        journal=journal,
        abstract=sections.abstract,
        keywords_from_paper=sections.keywords,
        research_objects=terms_for("object"),
        physical_processes=terms_for("physical_process"),
        science_questions=terms_for("science_question"),
        methods=terms_for("method"),
        surveys_and_instruments=terms_for("survey_or_instrument"),
        galaxies_and_environments=terms_for("galaxy_or_environment"),
        main_results=_main_results(sections.conclusion),
        topic_phrases=ranked,
        confidence=confidence,
        warnings=warnings,
        matched_author_role=author_role,
        matched_forms={term: sorted(matched_forms[term], key=str.casefold) for term in ranked},
        topic_scores={term: round(scores[term], 6) for term in ranked},
        topic_categories=categories,
        section_hits={term: sorted(section_hits[term]) for term in ranked},
    )

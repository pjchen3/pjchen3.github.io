from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TopicCategory = Literal[
    "object",
    "physical_process",
    "science_question",
    "method",
    "survey_or_instrument",
    "galaxy_or_environment",
    "general_field",
]


class PaperLink(BaseModel):
    title: str
    year: int | None = None
    file: str
    url: str = ""


class PaperAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    title: str = ""
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str = ""
    abstract: str = ""
    keywords_from_paper: list[str] = Field(default_factory=list)
    research_objects: list[str] = Field(default_factory=list)
    physical_processes: list[str] = Field(default_factory=list)
    science_questions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    surveys_and_instruments: list[str] = Field(default_factory=list)
    galaxies_and_environments: list[str] = Field(default_factory=list)
    main_results: list[str] = Field(default_factory=list)
    topic_phrases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    matched_author_role: Literal["first", "coauthor", "unknown"] = "unknown"
    matched_forms: dict[str, list[str]] = Field(default_factory=dict)
    topic_scores: dict[str, float] = Field(default_factory=dict)
    topic_categories: dict[str, TopicCategory] = Field(default_factory=dict)
    section_hits: dict[str, list[str]] = Field(default_factory=dict)


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    display_name: str
    weight: float = Field(ge=1.0, le=100.0)
    category: TopicCategory
    level: int = Field(ge=1, le=3)
    paper_count: int = Field(ge=1)
    papers: list[PaperLink]
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class SectionBundle(BaseModel):
    title: str = ""
    authors_line: str = ""
    metadata_author: str = ""
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    introduction_goals: str = ""
    headings: list[str] = Field(default_factory=list)
    conclusion: str = ""
    captions: str = ""
    main_text: str = ""
    raw_text_length: int = 0
    references_excluded: bool = False
    warnings: list[str] = Field(default_factory=list)


class CacheEntry(BaseModel):
    file_hash: str
    fingerprint: str
    paper: PaperAnalysis


def paper_ref(paper: PaperAnalysis, base_url: str = "", links: dict[str, str] | None = None) -> PaperLink:
    links = links or {}
    url = links.get(paper.file, "")
    if not url and base_url:
        url = f"{base_url.rstrip('/')}/{Path(paper.file).name}"
    return PaperLink(title=paper.title or paper.file, year=paper.year, file=paper.file, url=url)

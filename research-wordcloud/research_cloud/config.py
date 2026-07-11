from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import ALGORITHM_VERSION


class AuthorConfig(BaseModel):
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    first_author_weight: float = 1.0
    corresponding_author_weight: float = 1.0
    coauthor_weight: float = 0.6


class InputConfig(BaseModel):
    pdf_directory: str = "./papers"
    recursive: bool = True


class ExtractionConfig(BaseModel):
    use_ocr_fallback: bool = False
    exclude_references: bool = True
    max_pages_per_paper: int | None = None
    min_extracted_characters: int = 500


class TopicsConfig(BaseModel):
    language: str = "en"
    max_topics_per_paper: int = 15
    final_max_words: int = 80
    min_paper_count: int = 1
    prefer_phrases: bool = True
    stopwords: list[str] = Field(default_factory=list)
    synonyms: dict[str, list[str]] = Field(default_factory=dict)
    force_include: dict[str, dict[str, Any]] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=list)
    display_names: dict[str, str] = Field(default_factory=dict)
    categories: dict[str, str] = Field(default_factory=dict)


class WeightingConfig(BaseModel):
    use_recency: bool = False
    recency_half_life_years: float = 6.0


class WordcloudConfig(BaseModel):
    width: int = 1600
    height: int = 900
    background_color: str = "#FAFBFD"
    max_font_size: int = 138
    min_font_size: int = 20
    prefer_horizontal: float = 0.86
    relative_scaling: float = 0.38
    margin: int = 16
    random_seed: int = 17
    font_path: str | None = None
    colors: dict[str, str] = Field(default_factory=dict)


class WebsiteConfig(BaseModel):
    interactive: bool = True
    paper_base_url: str = ""
    open_links_in_new_tab: bool = True
    paper_links: dict[str, str] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai-compatible"
    model: str = ""
    api_base: str = ""
    api_key_env: str = "RESEARCH_CLOUD_API_KEY"
    timeout_seconds: int = 90


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: AuthorConfig = Field(default_factory=AuthorConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    topics: TopicsConfig = Field(default_factory=TopicsConfig)
    weighting: WeightingConfig = Field(default_factory=WeightingConfig)
    wordcloud: WordcloudConfig = Field(default_factory=WordcloudConfig)
    website: WebsiteConfig = Field(default_factory=WebsiteConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    def fingerprint(self) -> str:
        payload = {"algorithm": ALGORITHM_VERSION, "config": self.model_dump(mode="json")}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class TopicOverrides(BaseModel):
    rename: dict[str, str] = Field(default_factory=dict)
    merge: dict[str, list[str]] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=list)
    force_include: dict[str, dict[str, Any]] = Field(default_factory=dict)
    category_override: dict[str, str] = Field(default_factory=dict)


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None, cli_overrides: dict[str, Any] | None = None) -> AppConfig:
    data: dict[str, Any] = {}
    if path:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Configuration root must be a YAML mapping")
        data = loaded
    if cli_overrides:
        data = _deep_merge(data, cli_overrides)
    return AppConfig.model_validate(data)


def load_overrides(path: Path | None) -> TopicOverrides:
    if not path or not path.exists():
        return TopicOverrides()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return TopicOverrides.model_validate(data)

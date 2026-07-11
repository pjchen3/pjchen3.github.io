from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pydantic import BaseModel, Field

from .config import LLMConfig
from .models import PaperAnalysis, SectionBundle


class LLMPaperResult(BaseModel):
    research_objects: list[str] = Field(default_factory=list)
    physical_processes: list[str] = Field(default_factory=list)
    science_questions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    surveys_and_instruments: list[str] = Field(default_factory=list)
    galaxies_and_environments: list[str] = Field(default_factory=list)
    main_results: list[str] = Field(default_factory=list)
    topic_phrases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


SYSTEM_PROMPT = """You extract only the paper's own research topics from selected high-value sections.
Ignore references and background-only examples. Distinguish actual targets from cited objects. Do not invent facts.
Return strict JSON matching the supplied schema. Use normalized English scientific phrases. Lower confidence when uncertain."""


def _request(config: LLMConfig, sections: SectionBundle) -> LLMPaperResult:
    key = os.getenv(config.api_key_env)
    if not key:
        raise RuntimeError(f"Environment variable {config.api_key_env} is not set")
    if not config.api_base or not config.model:
        raise RuntimeError("LLM api_base and model are required")
    selected = {
        "title": sections.title,
        "keywords": sections.keywords,
        "abstract": sections.abstract[:7000],
        "introduction_goals": sections.introduction_goals[:3500],
        "headings": sections.headings,
        "conclusion": sections.conclusion[:7000],
    }
    payload = {
        "model": config.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"schema": LLMPaperResult.model_json_schema(), "paper": selected})},
        ],
    }
    endpoint = config.api_base.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
        result = json.loads(response.read())
    content = result["choices"][0]["message"]["content"]
    return LLMPaperResult.model_validate_json(content)


def enrich_with_llm(paper: PaperAnalysis, sections: SectionBundle, config: LLMConfig) -> PaperAnalysis:
    last_error: Exception | None = None
    for _ in range(2):
        try:
            result = _request(config, sections)
            updates = result.model_dump()
            updates["confidence"] = max(paper.confidence, result.confidence)
            for key in [
                "research_objects", "physical_processes", "science_questions", "methods",
                "surveys_and_instruments", "galaxies_and_environments", "main_results", "topic_phrases",
            ]:
                updates[key] = list(dict.fromkeys([*getattr(paper, key), *updates[key]]))
            return paper.model_copy(update=updates)
        except Exception as exc:  # remote failures must fall back locally
            last_error = exc
    paper.warnings.append(f"LLM extraction failed; local extraction used: {last_error}")
    return paper


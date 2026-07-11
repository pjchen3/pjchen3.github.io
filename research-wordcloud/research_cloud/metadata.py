from __future__ import annotations

import re
from pathlib import Path

from .models import SectionBundle


JOURNALS = {
    "astrophysical journal letters": "ApJL",
    "astrophysical journal": "ApJ",
    "astronomical journal": "AJ",
    "monthly notices of the royal astronomical society": "MNRAS",
    "astronomy & astrophysics": "A&A",
    "astronomy and astrophysics": "A&A",
    "science": "Science",
}


def extract_year(text: str) -> int | None:
    years = [int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b", text[:12000])]
    plausible = [year for year in years if 1900 <= year <= 2100]
    return plausible[0] if plausible else None


def extract_authors(authors_line: str) -> list[str]:
    line = re.sub(r"\d+|[*†‡]", "", authors_line)
    parts = re.split(r"\s*(?:,|;|\band\b|&)\s*", line)
    return [p.strip() for p in parts if 2 <= len(p.strip()) <= 100][:80]


def extract_journal(text: str) -> str:
    lowered = text[:15000].lower()
    for full, short in JOURNALS.items():
        if full in lowered:
            return short
    return ""


def infer_metadata(path: Path, sections: SectionBundle) -> tuple[int | None, list[str], str]:
    sample = "\n".join([sections.title, sections.authors_line, sections.main_text[:12000]])
    return extract_year(sample), extract_authors(sections.authors_line), extract_journal(sample)


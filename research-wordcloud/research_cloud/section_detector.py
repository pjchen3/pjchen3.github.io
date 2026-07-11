from __future__ import annotations

import re

from .models import SectionBundle


REFERENCE_RE = re.compile(r"(?im)^\s*(?:\d+[.\s]+)?(?:references|bibliography|literature cited)\b")
ABSTRACT_START_RE = re.compile(r"(?im)^\s*(?:abstract|a\s+b\s+s\s+t\s+r\s+a\s+c\s+t|summary)\s*[:.—-]?\s*")
KEYWORDS_RE = re.compile(r"(?im)^\s*(?:keywords?|key words|subject headings)\s*[:.—-]\s*(.+)$")
CONCLUSION_RE = re.compile(
    r"(?im)^\s*(?:\d+(?:\.\d+)*[.\s]+)?(?:summary(?: and conclusions?)?|conclusions?(?: and future perspectives?)?|discussion and conclusions?|concluding remarks)(?!\s+of\b)"
)
HEADING_RE = re.compile(r"(?m)^\s*(?:\d+(?:\.\d+)*[.\s]+)?([A-Z][A-Z0-9 /&,:()\-]{3,70})\s*$")
INTRO_RE = re.compile(r"(?im)^\s*(?:\d+[.\s]+)?introduction\s*$")
CAPTION_RE = re.compile(r"(?im)^\s*(?:fig(?:ure)?\.?|table)\s*\d+\s*[.:—-]\s*(.+(?:\n(?!\s*\n).+)*)")


def exclude_references(text: str) -> tuple[str, bool]:
    matches = list(REFERENCE_RE.finditer(text))
    for match in matches:
        # A real reference section is normally in the latter half of a paper.
        if match.start() > len(text) * 0.45:
            return text[: match.start()].rstrip(), True
    return text, False


def _slice_until_heading(text: str, start: int, max_chars: int) -> str:
    tail = text[start : start + max_chars]
    heading = re.search(r"\n\s*(?:\d+(?:\.\d+)*[.\s]+)?[A-Z][A-Z0-9 /&,:()\-]{3,70}\s*\n", tail[80:])
    if heading:
        tail = tail[: heading.start() + 80]
    return tail.strip()


def detect_sections(text: str, *, exclude_refs: bool = True) -> SectionBundle:
    warnings: list[str] = []
    working, excluded = exclude_references(text) if exclude_refs else (text, False)
    if exclude_refs and not excluded and len(text) > 5000:
        warnings.append("Reference section could not be identified reliably")

    lines = [line.strip() for line in working.splitlines() if line.strip()]
    title = ""
    for line in lines[:25]:
        low = line.lower()
        if len(line) >= 12 and not re.match(r"^(arxiv|doi|draft|accepted|advance access|the astronomical|the astrophysical|mnras\b|monthly notices|copyright|©)", low):
            title = line
            break

    abstract = ""
    abstract_match = ABSTRACT_START_RE.search(working[: min(len(working), 14000)])
    if abstract_match:
        abstract = _slice_until_heading(working, abstract_match.end(), 7000)
        abstract = re.split(r"(?im)^\s*(?:keywords?|key words|subject headings)\s*[:.—-]", abstract)[0].strip()
    else:
        warnings.append("Abstract not found")

    keywords: list[str] = []
    keyword_match = KEYWORDS_RE.search(working[: min(len(working), 18000)])
    if keyword_match:
        keywords = [k.strip(" .") for k in re.split(r"[;,·•]", keyword_match.group(1)) if k.strip(" .")]

    headings = []
    for match in HEADING_RE.finditer(working):
        heading = re.sub(r"\s+", " ", match.group(1)).title()
        if heading.lower() not in {"abstract", "references", "keywords"} and heading not in headings:
            headings.append(heading)

    conclusion = ""
    conclusion_match = CONCLUSION_RE.search(working)
    if conclusion_match:
        conclusion = _slice_until_heading(working, conclusion_match.end(), 12000)
    else:
        inline_conclusion = re.search(
            r"(?im)\b\d+(?:\.\d+)*\.\s*(?:summary|conclusions?(?: and future perspectives?)?)(?=\s|[A-Z])",
            working,
        )
        summary_sentences = list(re.finditer(r"(?i)\bin summary,\s*", working))
        if inline_conclusion:
            conclusion = working[inline_conclusion.end() : inline_conclusion.end() + 12000].strip()
        elif summary_sentences:
            conclusion = working[summary_sentences[-1].start() : summary_sentences[-1].start() + 4000].strip()
        else:
            warnings.append("Conclusion or summary section not found")

    intro_goals = ""
    intro_match = INTRO_RE.search(working)
    if intro_match:
        intro = _slice_until_heading(working, intro_match.end(), 10000)
        paragraphs = re.split(r"\n\s*\n", intro)
        goal_paragraphs = [
            p for p in paragraphs if re.search(r"\b(?:we (?:aim|investigate|study|present|examine|explore)|our (?:aim|goal|purpose))\b", p, re.I)
        ]
        intro_goals = "\n\n".join(goal_paragraphs[-2:] or paragraphs[-1:]).strip()

    captions = "\n".join(m.group(1).strip() for m in CAPTION_RE.finditer(working))[:8000]
    authors_line = ""
    for index, raw_line in enumerate(lines[1:30], start=1):
        line = re.sub(r"^Received:\s*\d+\s+\w+\s+\d{4}\s*", "", raw_line, flags=re.I).strip()
        if not line or line == title or re.search(r"\b(?:university|observator|institute|journal|doi|published|accepted|republic of china)\b", line, re.I):
            continue
        name_pairs = re.findall(r"\b[A-Z][A-Za-z'-]+\s+[A-Z][A-Za-z'-]+(?:\d+|aa|bb)*\b", line)
        if len(name_pairs) < 2 or not re.search(r"(?:,|\band\b|&)", line, re.I):
            continue
        parts = [line]
        for continuation in lines[index + 1 : index + 3]:
            if re.search(r"\b(?:accepted|received|department|university|institute|school|laboratory)\b", continuation, re.I):
                break
            if re.search(r"(?:,|\band\b|&)", continuation, re.I):
                parts.append(continuation)
        authors_line = " ".join(parts)
        break
    return SectionBundle(
        title=title[:500],
        authors_line=authors_line[:1000],
        abstract=abstract,
        keywords=keywords,
        introduction_goals=intro_goals,
        headings=headings[:80],
        conclusion=conclusion,
        captions=captions,
        main_text=working,
        raw_text_length=len(text),
        references_excluded=excluded,
        warnings=warnings,
    )

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz
from PIL import Image

from .config import ExtractionConfig
from .models import SectionBundle
from .section_detector import detect_sections


def discover_pdfs(directory: Path, recursive: bool = True) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Input PDF directory not found: {directory}")
    candidates = directory.rglob("*") if recursive else directory.glob("*")
    return sorted((p for p in candidates if p.is_file() and p.suffix.casefold() == ".pdf"), key=lambda p: str(p).lower())


def _dehyphenate(text: str) -> str:
    return re.sub(r"(?<=[A-Za-z])[-‐]\n(?=[a-z])", "", text)


def clean_page_texts(pages: list[str]) -> str:
    if not pages:
        return ""
    page_lines = [[line.strip() for line in page.splitlines() if line.strip()] for page in pages]
    edge_counts: Counter[str] = Counter()
    for lines in page_lines:
        normalized_edges = {re.sub(r"\d+", "#", x).lower() for x in (lines[:3] + lines[-3:]) if 2 < len(x) < 160}
        edge_counts.update(normalized_edges)
    threshold = max(2, round(len(pages) * 0.5))
    repeated = {line for line, count in edge_counts.items() if count >= threshold}

    cleaned_pages: list[str] = []
    for lines in page_lines:
        kept = []
        for line in lines:
            normalized = re.sub(r"\d+", "#", line).lower()
            if normalized in repeated or re.fullmatch(r"\s*\d+\s*", line):
                continue
            line = re.sub(r"^\s*\d{1,4}\s+(?=[A-Za-z])", "", line)  # common arXiv line numbers
            kept.append(line)
        cleaned_pages.append("\n".join(kept))
    text = _dehyphenate("\n\n".join(cleaned_pages))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    for ligature, replacement in {
        "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
    }.items():
        text = text.replace(ligature, replacement)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ocr_selected_pages(document: fitz.Document, extracted_pages: list[str], page_limit: int) -> tuple[str, str]:
    try:
        import pytesseract
    except ImportError:
        return "", "OCR fallback requested but the optional pytesseract package is not installed"

    page_count = min(page_limit, len(document))
    sparse = [index for index, text in enumerate(extracted_pages) if len(text.strip()) < 120]
    # For an entirely scanned paper, the first pages normally contain the title/abstract
    # and the final pages contain conclusions. Avoid OCRing a long paper indiscriminately.
    if len(sparse) == page_count and page_count > 6:
        selected = sorted({0, 1, 2, page_count - 3, page_count - 2, page_count - 1})
    else:
        selected = sparse[:6]
    if not selected:
        return "", "OCR fallback was not needed for any individual page"

    chunks: list[str] = []
    try:
        for index in selected:
            pixmap = document[index].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            chunks.append(pytesseract.image_to_string(image))
    except Exception as exc:
        return "", f"OCR fallback failed: {exc}"
    return "\n\n".join(chunks).strip(), f"OCR fallback used on {len(selected)} selected page(s)"


def extract_pdf(path: Path, config: ExtractionConfig) -> SectionBundle:
    try:
        document = fitz.open(path)
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise ValueError(f"Cannot open PDF {path.name}: {exc}") from exc
    try:
        page_limit = config.max_pages_per_paper or len(document)
        pages = [document[i].get_text("text", sort=True) for i in range(min(page_limit, len(document)))]
        metadata = document.metadata or {}
        text = clean_page_texts(pages)
        ocr_warning = ""
        if len(text) < config.min_extracted_characters and config.use_ocr_fallback:
            ocr_text, ocr_warning = _ocr_selected_pages(document, pages, page_limit)
            if len(ocr_text) > len(text):
                text = clean_page_texts([ocr_text])
    finally:
        document.close()
    sections = detect_sections(text, exclude_refs=config.exclude_references)
    metadata_title = (metadata.get("title") or "").strip()
    if metadata_title and not re.match(r"^(?:the astrophysical journal|mnras\b|monthly notices|doi\b|arxiv\b)", metadata_title, re.I):
        sections.title = metadata_title
    sections.metadata_author = (metadata.get("author") or "").strip()
    if len(text) < config.min_extracted_characters:
        sections.warnings.append(
            f"Very little extractable text ({len(text)} characters); this may be a scanned PDF"
        )
    if ocr_warning:
        sections.warnings.append(ocr_warning)
    return sections

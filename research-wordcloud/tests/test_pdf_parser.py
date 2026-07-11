from pathlib import Path

from research_cloud.config import ExtractionConfig
from research_cloud.pdf_parser import clean_page_texts, discover_pdfs, extract_pdf
from research_cloud.section_detector import exclude_references


def test_pdf_discovery_is_recursive_and_sorted(tmp_path: Path):
    (tmp_path / "b.pdf").write_bytes(b"x")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.PDF").write_bytes(b"x")
    (tmp_path / "ignore.txt").write_text("x")
    assert [p.name for p in discover_pdfs(tmp_path)] == ["b.pdf", "a.PDF"]
    assert [p.name for p in discover_pdfs(tmp_path, recursive=False)] == ["b.pdf"]


def test_two_column_style_cleanup_removes_headers_and_repairs_hyphens():
    pages = [
        "Synthetic Journal 2026\nPlanetary neb-\nulae evolve.\n1",
        "Synthetic Journal 2026\nCentral stars and mass loss.\n2",
    ]
    cleaned = clean_page_texts(pages)
    assert "Synthetic Journal" not in cleaned
    assert "planetary nebulae" in cleaned.lower()


def test_reference_exclusion():
    text = "ABSTRACT\nPlanetary nebulae.\n" + ("body text\n" * 30) + "REFERENCES\nActive galactic nuclei"
    cleaned, excluded = exclude_references(text)
    assert excluded
    assert "Active galactic nuclei" not in cleaned


def test_extracts_abstract_conclusion_and_excludes_references(tmp_path: Path, synthetic_pdf_factory):
    pdf = synthetic_pdf_factory(tmp_path / "paper.pdf", title="Planetary Nebulae in M31", year=2025, terms="planetary nebulae in M31")
    sections = extract_pdf(pdf, ExtractionConfig(min_extracted_characters=100))
    assert "planetary nebulae" in sections.abstract.lower()
    assert "mass loss" in sections.conclusion.lower()
    assert "Active Galactic Nuclei" not in sections.main_text

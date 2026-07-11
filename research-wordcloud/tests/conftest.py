from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.pdfgen import canvas


@pytest.fixture
def synthetic_pdf_factory():
    def build(path: Path, *, title: str, year: int, terms: str, instrument: str = "Gaia") -> Path:
        c = canvas.Canvas(str(path))
        c.setTitle(title)
        y = 790
        lines = [
            title,
            f"Alice Researcher, Ada Example, and Bea Example ({year})",
            "ABSTRACT",
            f"We investigate {terms} with {instrument} and time-series photometry.",
            f"Our aim is to understand mass loss and stellar evolution in {terms}.",
            f"Keywords: {terms}; mass loss; {instrument}; time-series photometry",
            "1 INTRODUCTION",
            f"We study {terms} to measure their physical properties and evolutionary pathways.",
            "This is synthetic test prose and contains no text from a real publication.",
            "2 METHODS",
            f"Period analysis and spectroscopy are applied to {instrument} measurements.",
        ]
        lines += [f"Synthetic body line {i} about {terms}." for i in range(18)]
        lines += [
            "5 SUMMARY AND CONCLUSIONS",
            f"We find that {terms} exhibit evidence of mass loss.",
            "Our results demonstrate the value of time-series photometry.",
            "REFERENCES",
            "Example, A. 1999, Synthetic Journal, 1, 1",
            "Unrelated Background Author 2001, Active Galactic Nuclei",
        ]
        for line in lines:
            if y < 45:
                c.showPage()
                y = 790
            c.drawString(48, y, line[:150])
            y -= 17
        c.save()
        return path

    return build

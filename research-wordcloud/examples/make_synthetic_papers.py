"""Create tiny, copyright-free PDFs for a local Research Cloud smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.pdfgen import canvas


PAPERS = [
    ("synthetic_2024.pdf", "Planetary Nebulae and Their Central Stars", 2024, "planetary nebulae and central stars", "HST"),
    ("synthetic_2026.pdf", "Mass Loss from Planetary Nebulae in M31", 2026, "planetary nebulae in M31", "Gaia"),
]


def make_pdf(path: Path, title: str, year: int, topic: str, instrument: str) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.setTitle(title)
    y = 790
    lines = [
        title,
        f"Alice Researcher, Ada Example, and Bea Example ({year})",
        "ABSTRACT",
        f"We investigate {topic} with {instrument}, spectroscopy, and time-series photometry.",
        f"Keywords: {topic}; mass loss; stellar evolution; {instrument}",
        "1 INTRODUCTION",
        f"Our aim is to understand the evolutionary pathways of {topic}.",
        "All prose in this document is synthetic and was written solely for software testing.",
        "2 METHODS",
        "We apply period analysis, spectral classification, and catalog construction.",
    ]
    lines.extend(f"Synthetic test paragraph {i} concerns {topic}." for i in range(20))
    lines.extend([
        "5 SUMMARY AND CONCLUSIONS",
        f"We find evidence that mass loss shapes the observed properties of {topic}.",
        "Our results demonstrate the complementary value of photometry and spectroscopy.",
        "REFERENCES",
        "Example, A. 2000, Synthetic Journal, 1, 1",
    ])
    for line in lines:
        if y < 45:
            pdf.showPage()
            y = 790
        pdf.drawString(48, y, line[:150])
        y -= 17
    pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=Path("./papers"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, title, year, topic, instrument in PAPERS:
        make_pdf(args.output / filename, title, year, topic, instrument)
    print(f"Created {len(PAPERS)} synthetic PDFs in {args.output.resolve()}")


if __name__ == "__main__":
    main()

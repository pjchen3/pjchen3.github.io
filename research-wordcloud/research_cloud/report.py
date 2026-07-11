from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .models import PaperAnalysis, Topic


def build_research_summary(papers: list[PaperAnalysis], topics: list[Topic]) -> str:
    level_one = [t for t in topics if t.level == 1][:6]
    concrete = [t for t in topics if t.level == 2][:10]
    tools = [t for t in topics if t.level == 3][:8]
    top_names = ", ".join(t.display_name for t in concrete[:5]) or "no stable topics could be identified"
    lines = [
        "# Research summary",
        "",
        f"This publication set contains {len(papers)} paper{'s' if len(papers) != 1 else ''}. Its strongest content-derived themes are {top_names}.",
        "The ranking emphasizes concepts found in titles, abstracts, author keywords, research-goal paragraphs, and conclusions, while excluding references and limiting within-paper repetition.",
        "",
        "## Primary research fields",
        "",
    ]
    if level_one:
        for field in level_one:
            examples = "; ".join(p.title for p in field.papers[:3])
            lines.append(f"- **{field.display_name}** - representative papers: {examples}")
    else:
        lines.append("- No broad field met the evidence rules; inspect the concrete topics below.")
    lines.extend(["", "## Main research objects and questions", ""])
    lines.extend(f"- {topic.display_name} ({topic.paper_count} paper{'s' if topic.paper_count != 1 else ''})" for topic in concrete)
    lines.extend(["", "## Data, surveys, and methods", ""])
    lines.extend(f"- {topic.display_name}" for topic in tools)

    dated = [paper for paper in papers if paper.year]
    lines.extend(["", "## Topic evolution", ""])
    if len(dated) >= 2:
        years = sorted({paper.year for paper in dated if paper.year is not None})
        midpoint = years[len(years) // 2]
        early = {term for p in dated if p.year and p.year <= midpoint for term in p.topic_phrases[:5]}
        recent = {term for p in dated if p.year and p.year > midpoint for term in p.topic_phrases[:5]}
        emerging = sorted(recent - early)[:6]
        persistent = sorted(recent & early)[:6]
        lines.append(f"- Coverage: {min(years)}-{max(years)}; the split used here is {midpoint}.")
        lines.append(f"- Persistent topics: {', '.join(persistent) if persistent else 'none identified robustly'}.")
        lines.append(f"- More recent-only topics in this sample: {', '.join(emerging) if emerging else 'none identified robustly'}.")
    else:
        lines.append("- Too few papers with identified years for a reliable temporal comparison.")
    return "\n".join(lines) + "\n"


def build_timeline(papers: list[PaperAnalysis], topics: list[Topic], output: Path) -> dict[str, object]:
    years = sorted({p.year for p in papers if p.year is not None})
    top_terms = [topic.term for topic in topics if topic.level == 2][:8]
    series: dict[str, dict[str, float]] = defaultdict(dict)
    paper_by_file = {paper.file: paper for paper in papers}
    for topic in topics:
        if topic.term not in top_terms:
            continue
        for ref in topic.papers:
            paper = paper_by_file.get(ref.file)
            if paper and paper.year:
                series[topic.display_name][str(paper.year)] = series[topic.display_name].get(str(paper.year), 0.0) + 1.0
    payload: dict[str, object] = {"years": years, "series": dict(series)}

    fig, ax = plt.subplots(figsize=(12, 6), dpi=140)
    if years and series:
        for term, values in series.items():
            ax.plot(years, [values.get(str(year), 0.0) for year in years], marker="o", linewidth=2, label=term)
        ax.set_ylabel("Papers mentioning topic")
        ax.set_xlabel("Publication year")
        ax.set_xticks(years)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    else:
        ax.text(0.5, 0.5, "Insufficient dated topic data", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    ax.set_title("Research topic timeline")
    fig.tight_layout()
    fig.savefig(output / "topic_timeline.png", transparent=False, facecolor="white")
    plt.close(fig)
    return payload


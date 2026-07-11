from __future__ import annotations

from pathlib import Path

from matplotlib import font_manager
from wordcloud import WordCloud

from .config import WordcloudConfig
from .models import Topic


DEFAULT_COLORS = {
    "object": "#315FCE",
    "physical_process": "#D1495B",
    "science_question": "#7456C9",
    "method": "#16817A",
    "survey_or_instrument": "#C77918",
    "galaxy_or_environment": "#A34D8C",
    "general_field": "#172033",
}


def _frequencies(topics: list[Topic]) -> dict[str, float]:
    level_factor = {1: 1.1, 2: 1.0, 3: 0.72}
    return {topic.display_name: max(1.0, topic.weight * level_factor[topic.level]) for topic in topics}


def build_wordcloud(topics: list[Topic], config: WordcloudConfig, *, transparent: bool = False) -> WordCloud:
    if not topics:
        raise ValueError("No topics remain after filtering; cannot render a word cloud")
    category_by_display = {topic.display_name: topic.category for topic in topics}
    colors = {**DEFAULT_COLORS, **config.colors}
    font_path = config.font_path or font_manager.findfont("DejaVu Sans")

    def color_func(word: str, **_: object) -> str:
        return colors.get(category_by_display.get(word, "object"), "#1F2937")

    cloud = WordCloud(
        width=config.width,
        height=config.height,
        background_color=None if transparent else (config.background_color if config.background_color != "transparent" else "white"),
        mode="RGBA" if transparent else "RGB",
        max_font_size=config.max_font_size,
        min_font_size=config.min_font_size,
        prefer_horizontal=config.prefer_horizontal,
        random_state=config.random_seed,
        font_path=font_path,
        collocations=False,
        margin=config.margin,
        relative_scaling=config.relative_scaling,
    )
    cloud.generate_from_frequencies(_frequencies(topics)).recolor(color_func=color_func, random_state=config.random_seed)
    return cloud


def render_pngs(topics: list[Topic], config: WordcloudConfig, output: Path) -> WordCloud:
    cloud = build_wordcloud(topics, config, transparent=False)
    cloud.to_file(str(output / "wordcloud.png"))
    transparent_cloud = build_wordcloud(topics, config, transparent=True)
    transparent_cloud.to_file(str(output / "wordcloud_transparent.png"))
    return cloud


def layout_records(cloud: WordCloud, topics: list[Topic]) -> list[dict[str, object]]:
    by_display = {topic.display_name: topic for topic in topics}
    records: list[dict[str, object]] = []
    for (word, _frequency), font_size, (y, x), orientation, color in cloud.layout_:
        topic = by_display[word]
        records.append({
            "word": word,
            "x": int(x),
            "y": int(y),
            "font_size": int(font_size),
            "rotate": 0 if orientation is None else 90,
            "color": str(color),
            "topic": topic.model_dump(mode="json"),
        })
    return records

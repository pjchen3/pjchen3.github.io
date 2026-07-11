# Research Wordcloud

`research-wordcloud` scans a directory of personal publication PDFs, extracts high-information sections, identifies semantic research phrases, and produces a paper-traceable topic cloud for an academic website. It runs fully locally without an API key. A remote or local OpenAI-compatible model can be enabled explicitly as an optional enrichment step.

The default ranking is not raw full-text frequency. It weights title, author keywords, abstract, research-goal paragraphs, headings, and conclusions more strongly; removes the reference section; caps repetition inside each paper; and then rewards coverage across distinct papers.

## Requirements and installation

- Python 3.11 or newer
- Text-based PDFs for the default parser
- Optional: a system font path for custom word-cloud typography

Create an isolated environment from this directory:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

The core dependencies include PyMuPDF, Pydantic, scikit-learn, wordcloud, Matplotlib, Jinja2, Pillow, and PyYAML. The current rule-based extractor does not download an embedding model.

## Quick start

Put PDFs under one directory:

```text
papers/
├── Chen2025_ApJ.pdf
├── Chen2025_AJ.pdf
└── Chen2026_ApJL.pdf
```

Then run either CLI form:

```bash
python -m research_cloud analyze \
  --input ./papers \
  --output ./output \
  --config ./config.example.yaml
```

```bash
research-cloud ./papers --output ./output
```

The main options are:

```text
--input PATH
--output PATH
--config PATH
--overrides PATH
--author-name NAME
--language en
--max-words N
--min-paper-count N
--use-recency / --no-use-recency
--llm-provider none|openai-compatible|local
--llm-model MODEL
--api-base URL
--force
--verbose
```

`--force` bypasses the analysis cache. It does not delete files.

## How extraction works

For each PDF, the parser cleans repeated page headers and footers, repairs common line-break hyphenation, identifies the abstract and paper keywords, finds headings and introduction goal sentences, extracts conclusions or summary sections, and excludes text after the references heading. PyMuPDF's sorted text extraction provides a useful baseline for common two-column astronomy papers, although unusual layouts can still require review.

The local topic extractor combines a curated astronomy vocabulary with unigram, bigram, and trigram candidates. It prefers complete phrases such as `planetary nebulae`, `time-series photometry`, and `late-stage stellar evolution`. It filters ordinary English, academic boilerplate, and low-information standalone astronomy words while retaining those words inside meaningful phrases.

Default section weights are:

| Section | Weight |
|---|---:|
| Title | 5.0 |
| Paper keywords | 4.5 |
| Abstract | 4.0 |
| Conclusion/summary | 3.5 |
| Introduction goals | 3.0 |
| Headings | 2.5 |
| Selected captions | 1.3 |
| Main text | 1.0 |
| References | 0.0 |

Within a paper, repeated occurrences receive only a capped logarithmic bonus. Every paper is normalized before aggregation. The final transparent score combines paper coverage, within-paper semantic importance, phrase specificity, optional recency, and optional author role. Recency has a 0.5 floor, so older work does not disappear. Corresponding-author status is never guessed.

## Configuration

Copy [`config.example.yaml`](config.example.yaml) and edit it. It covers author aliases and role weights, recursive discovery, OCR warnings, topic limits, recency, image dimensions, category colors, paper URLs, and the optional LLM endpoint.

Useful custom topic settings include:

```yaml
topics:
  stopwords: ["synthetic catalog"]
  synonyms:
    "planetary nebulae": ["PN", "PNe", "planetary nebula"]
  exclude: ["generic candidate"]
  display_names:
    "time-series photometry": "Time-series Photometry"
  categories:
    "custom instrument": "survey_or_instrument"
```

Configuration is schema-validated. Unknown keys fail loudly instead of being silently ignored.

## Manual topic corrections

On the first run, the output directory receives `topic_overrides.yaml`. Edit it and rerun to rename, merge, exclude, force-include, or recategorize terms without changing Python code. See [`topic_overrides.example.yaml`](topic_overrides.example.yaml) for the full format.

Aggregation-level overrides are applied on every run. Use `--force` after changing a merge, rename, or category rule when an existing per-paper topic list itself must be rebuilt.

## Output files

```text
output/
├── .cache/                      # content-addressed per-PDF analyses
├── papers.json                  # structured per-paper results and warnings
├── topics.json                  # weighted topics and related papers
├── research_summary.md          # content-derived prose summary
├── wordcloud.png                # 1600 x 900 by default
├── wordcloud_transparent.png    # transparent background
├── wordcloud.svg                # reconstructed vector layout
├── wordcloud.html               # self-contained interactive cloud
├── report.html                  # complete static analysis report
├── timeline.json                # per-year topic counts
├── topic_timeline.png           # static timeline plot
└── topic_overrides.yaml         # editable correction layer
```

Each `topics.json` entry contains its normalized term, display name, 1-100 weight, category, hierarchy level, paper count, aliases, description, and supporting paper records. Each `papers.json` entry contains title, year, authors, journal, abstract, author keywords, categorized topics, main-result sentences, confidence, warnings, matched forms, and section provenance.

The hierarchy is:

- Level 1: broad research fields inferred only when concrete supporting terms exist.
- Level 2: research objects, physical processes, science questions, and environments; these dominate the cloud.
- Level 3: methods, surveys, and instruments; these receive a smaller visual factor.

## Embed in a website

Static image:

```html
<img
  src="/assets/research-wordcloud.png"
  alt="Research interests word cloud"
/>
```

Interactive iframe:

```html
<iframe
  src="/assets/research-wordcloud.html"
  title="Interactive research interests word cloud"
  width="100%"
  height="650"
  frameborder="0"
  loading="lazy"
></iframe>
```

The generated `wordcloud.html` is responsive and self-contained. It can also be copied into a site template: retain the `.stage`, `.canvas`, `.word`, tooltip, and details styles together with the embedded `records` JSON and JavaScript. No server or CDN is required. Configure exact publication destinations under `website.paper_links`, or set `website.paper_base_url` for predictable file URLs.

## Incremental updates

Every PDF receives a SHA-256 content hash. Cached data is reused only when both the hash and the analysis fingerprint match. Adding a PDF analyzes only that file; modifying a PDF produces a new cache entry; deleting a PDF removes it from the next aggregate because discovery is authoritative. The CLI reports counts such as:

```text
12 PDFs found
10 loaded from cache
2 newly analyzed
0 failed
```

Algorithm and configuration changes invalidate the relevant cache automatically. Old content-addressed cache files are harmless and may be removed manually.

## Optional LLM mode

LLM use is off by default. To enable an OpenAI-compatible endpoint:

```bash
export RESEARCH_CLOUD_API_KEY="..."
research-cloud ./papers --output ./output \
  --llm-provider openai-compatible \
  --llm-model YOUR_MODEL \
  --api-base https://your-endpoint.example/v1
```

The API key is read only from the environment variable named by `llm.api_key_env`; do not put it in YAML. Only the title, paper keywords, abstract, introduction-goal excerpt, headings, and conclusion excerpt are sent. The model must return schema-valid JSON. One retry is attempted, then local extraction is retained with a visible warning. The full paper and reference list are never intentionally sent.

`--llm-provider local` uses the same OpenAI-compatible HTTP shape and can target a locally hosted server. It still requires the configured environment variable unless that server accepts any placeholder key.

## OCR and scanned PDFs

Nearly text-free PDFs receive an explicit warning. OCR is optional and therefore needs both the Python adapter and the local Tesseract executable:

```bash
python -m pip install -e ".[ocr]"
# macOS: brew install tesseract
# Ubuntu/Debian: sudo apt-get install tesseract-ocr
```

Then set `extraction.use_ocr_fallback: true`. OCR runs only when extracted text is below the configured threshold. Sparse pages are selected directly; for a long, entirely scanned paper, only up to three opening and three closing pages are processed so the title, abstract, and conclusion can be recovered without OCRing the full document by default. Missing or failing OCR dependencies produce an explicit warning and preserve the original local extraction.

## Quality warnings and troubleshooting

Warnings appear in `papers.json` and `report.html`. They cover missing abstracts or conclusions, very little extractable text, uncertain reference removal, missing publication years, and configured author names not found. Topic warnings flag one-paper support and overly broad high-ranking terms.

- **No PDFs found:** verify `--input`, recursive settings, and file permissions.
- **Very little text:** the PDF is probably scanned or has unusual font encoding.
- **Abstract/conclusion missing:** check `papers.json`; add custom terms through overrides if the publisher layout is unusual.
- **No usable topics:** inspect extraction warnings and use `force_include` only for a topic genuinely supported by the papers.
- **Font error:** set `wordcloud.font_path` to a readable `.ttf` or `.otf` file, or leave it `null`.
- **LLM failure:** confirm the API base, model, key environment variable, and OpenAI-compatible `/chat/completions` behavior. Local output still completes when possible.

## Tests

The test suite creates tiny synthetic PDFs at runtime and contains no real or copyrighted paper text:

```bash
pytest
```

For a visible end-to-end smoke test, generate two synthetic papers and analyze them:

```bash
python examples/make_synthetic_papers.py ./papers
research-cloud ./papers --output ./output --author-name "Alice Researcher"
```

It covers PDF discovery, layout cleanup, reference exclusion, abbreviation and synonym merging, phrase preservation, bounded within-paper repetition, cross-paper coverage, cache hits, configuration overrides, JSON schemas, all website assets, CLI behavior, and operation without an LLM key.

## Privacy

PDFs are processed locally by default. No paper content, API key, output path, or author name is hard-coded. Content can leave the machine only when the user explicitly enables an HTTP LLM provider; even then, only selected high-value excerpts are submitted. Review the endpoint's privacy policy before enabling it.

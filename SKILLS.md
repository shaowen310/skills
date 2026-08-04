# Skills Catalogue

A detailed index of the reusable skills available in this repository. For repository overview and usage instructions, see the [main README](./README.md).

## Basic Skills

Atomic, single-purpose capabilities.

### 1. `pptx-translate` — PowerPoint Translation

**Translate PowerPoint presentations while preserving all formatting.**

- **Description**: Chinese-to-English (or vice versa) PPT/PPTX translation with complete formatting preservation
- **Features**:
  - Paragraph-level translation with context awareness
  - Preserves fonts, colors, layouts, images, tables, and all visual elements
  - Automatic font optimization (switches sans-serif fonts to Arial for better English readability)
  - Handles group shapes, tables, slide notes, and complex layouts
  - Intelligent line spacing adjustment for professional results
- **Use When**: User asks to translate PPT/slides/presentation, convert presentation language, or localize slide content
- **Triggers**: "翻译PPT", "translate PPT/slides/presentation", "PPT英文化", "PPT翻译成英文"
- **Tech Stack**: Python, `python-pptx` library
- **Complementary Skill**: Use the **`humanizer`** skill (if available) during Step 2.5 of the translation workflow to automatically polish translated text and remove "AI taste" — see the skill doc for details
- **[Learn more →](./pptx-translate/SKILL.md)**

### 2. `eddx-translate` — Edraw Diagram Translation

**Translate text labels in EdrawMax/EdrawMind (.eddx) diagrams seamlessly.**

- **Description**: Chinese-to-English (or vice versa) translation of text inside Edraw diagrams with complete structural preservation
- **Features**:
  - Targets only `<tp>` text nodes — shapes, coordinates, styles, and metadata are untouched
  - Non-destructive: source `.eddx` file is never modified
  - ZIP-preserving repack: retains original file order, compression, and attributes
  - Validates output ZIP integrity and XML well-formedness
- **Use When**: User asks to translate an `.eddx`/Edraw diagram, localize shapes in a flowchart, or replace terminology across multiple elements
- **Triggers**: "翻译 eddx 文件", "translate Edraw/eddx diagram", "替换 .eddx 中的文字"
- **Tech Stack**: Python, `zipfile` (stdlib), regex
- **[Learn more →](./eddx-translate/SKILL.md)**

### 3. `meeting-minutes` — Meeting Minutes

**Turn a meeting transcript plus a Markdown template into clean, structured meeting minutes.**

- **Description**: Convert a transcript (or pasted text) and a Markdown minute template into a structured minute. No audio processing; the user supplies text.
- **Features**:
  - Two paths: fill the template directly, or render deterministically via `scripts/fill_minutes.py`
  - Bilingual output — localizes generated labels/headers to the transcript's language (`en` / `zh`)
  - Auto-named output `YYYYMMDD_{MeetingPurpose}_Minutes.md` (short purpose, safety-capped)
  - Renders action items as a Markdown table, discussion as sub-sections, agenda as a numbered list
  - **Empty section cleanup** — `{{next_meeting}}` with no data is automatically removed from output (heading + content)
- **Use When**: User asks to summarize a meeting, write minutes from a transcript, or fill a minutes template
- **Triggers**: "会议纪要", "整理会议纪要", "meeting minutes", "summarize the meeting", "fill the minutes template"
- **Tech Stack**: Python (stdlib only, `argparse` + `re`)
- **[Learn more →](./meeting-minutes/SKILL.md)**

### 4. `docx2md` — Word to Markdown

**Convert Word `.docx` files to clean Markdown with images extracted to an `assets/` folder.**

- **Description**: Faithful `.docx → md` extraction for editing, search, re-styling, or knowledge-base ingestion — no AI rewriting
- **Features**:
  - Preserves headings (H1–H6), lists (bulleted/numbered), tables, and inline formatting (bold, italic, code)
  - Extracts all inline images into `assets/rIdX.<ext>` with relative paths
  - Tables rendered as GitHub-flavored Markdown tables
  - Hyperlinks preserved as Markdown link syntax
  - Text cleaned of invisible control characters for clean KB output
  - Deterministic output contract for KB chunking (`<!-- Page N -->` anchors, relative `assets/` paths, UTF-8 no-BOM)
  - CLI and Python API (`convert()` function)
- **Use When**: User asks to turn a Word doc into markdown, archive/search document content, or ingest Word docs into a knowledge base
- **Triggers**: "把Word转成markdown", "docx转md", "Word→MD", "把Word转成md", "导出Word内容", "extract Word as markdown", "convert Word to markdown"
- **Tech Stack**: Python, `python-docx` + `Pillow`
- **[Learn more →](./docx2md/SKILL.md)**

### 5. `pptx2md` — PowerPoint to Markdown

**Convert PowerPoint `.pptx` files to Markdown with images extracted into an `assets/` folder, preserving original text, reading order, tables, and swimlane diagrams.**

- **Description**: Faithful `pptx → md` extraction for editing, search, re-styling, or knowledge-base ingestion (agent/RAG pipelines) — no AI rewriting
- **Features**:
  - Recursively unwraps GROUP shapes and orders shapes by (top, left) to reconstruct visual flow
  - Extracts all pictures into `assets/page-XX-img-YY.<ext>` with relative paths
  - **Tables** rendered as GitHub-flavored Markdown tables (trailing blank rows dropped)
  - **Auto-excludes master/background images** via three heuristics: full-bleed covers, majority-recurring copies, and small corner-anchored brand logos
  - **Diagram handling** — slides with LINE connectors or ≥15 AUTO_SHAPE descendants are rendered as cropped PNGs via LibreOffice (best quality). Flowchart bbox is computed from the connectors and the nodes they actually touch, so side caption / container boxes stay OUTSIDE the cropped image
  - **Split-slide text extraction** — on slides with explanatory copy to the left of the diagram, that text is emitted as paragraphs FIRST, then the cropped flowchart image is appended (so descriptive copy is never duplicated inside the picture)
  - **Swimlane text fallback** — when LibreOffice is unavailable (or its render fails for a particular diagram slide), the page falls back to GROUP-defined swimlanes: each GROUP shape on the slide becomes a `### <lane-name>` subsection whose text items are joined with `→` arrows. Items above the topmost lane land in a synthetic role bar at the start. If the slide has no GROUP-shaped lanes, the page is emitted as plain text instead.
  - **Decorative standalone-picture exclusion** — title keywords (loaded from `references/decorative_keywords.txt`, never hard-coded) drop purely illustrative icons on matched non-diagram pages so KB output stays text-only without losing signal
  - **Deterministic output contract** for KB chunking (`<!-- Slide N -->` anchors, `##` titles, relative `assets/` paths, UTF-8 no-BOM, native punctuation preserved) — see `references/styling.md`
  - Optional `--keywords-file PATH` CLI flag and `convert(..., decorative_keywords=...)` Python API to override the keyword list per run
- **Use When**: User asks to turn a PPTX into markdown, archive/re-search slide content, or feed slides into a knowledge base
- **Triggers**: "把PPT转成markdown", "pptx转markdown", "PPTX→MD", "把幻灯片转成md", "导出PPTX内容", "extract slides as markdown", "把PPT做成知识库", "PPT转知识库给AI用"
- **Tech Stack**: Python, `python-pptx` + `Pillow` (LibreOffice optional for diagram rendering)
- **[Learn more →](./pptx2md/SKILL.md)**

## Orchestrator Skills

Composite workflows that chain one or more basic skills.

### 6. `kb-ingest` — PPTX Knowledge-Base Ingestion

**Thin orchestrator that turns `.pptx` slides into knowledge-base-ready, slide-level JSONL chunks for RAG / agent pipelines.**

- **Description**: Delegates extraction to `pptx2md`, then chunks the Markdown per the deterministic output contract into one JSONL record per slide (title, body, images, metadata)
- **Features**:
  - End-to-end: `.pptx` → `out.md + assets/` (via `pptx2md`) → `kb.jsonl`
  - Also ingests an already-converted `.md` (skips the conversion step)
  - Optional `--base-url` to resolve relative `assets/` paths into absolute URLs for an HTTP-served KB
  - Backend-agnostic JSONL: embed and index with any vector store
- **Use When**: User wants to ingest slide decks into a knowledge base / RAG system / search index / agent memory
- **Triggers**: "把PPT做成知识库", "PPT转知识库给AI用", "ingest PPTX into KB", "build RAG dataset from slides", "把幻灯片切片入库"
- **Tech Stack**: Python, `python-pptx` (for conversion), stdlib (`json`, `re`)
- **[Learn more →](./kb-ingest/SKILL.md)**

### 7. `meeting-minutes-export` — Meeting Minutes → Word Export

**Orchestrator that runs meeting-minutes then exports the result to Word (.docx).**

- **Description**: Chains `meeting-minutes` (transcript → structured `.md`) with `md-exporter` (`.md` → `.docx`) in one workflow
- **Features**:
  - End-to-end: transcript + template → `.md` (via meeting-minutes) → `.docx` (via md-exporter)
  - Custom `.docx` style template support (user-provided, bundled default, or Pandoc fallback)
  - Auto-named outputs `YYYYMMDD_{MeetingPurpose}_Minutes.md` and `.docx`
- **Use When**: User asks for both structured meeting minutes and a Word document copy
- **Triggers**: "整理会议纪要并导出为Word", "summarize meeting and export as docx", "会议记录生成 docx 文件"
- **Tech Stack**: Python (meeting-minutes), Pandoc / md-exporter
- **Complementary Skills**: Depends on **`meeting-minutes`** for the `.md` output
- **[Learn more →](./meeting-minutes-export/SKILL.md)**


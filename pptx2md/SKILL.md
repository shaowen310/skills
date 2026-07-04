---
name: pptx2md
description: 'Convert .pptx files to Markdown with all images extracted into an assets/ folder, preserving original text and reading order. Recursively unwraps GROUP shapes and orders shapes by (top, left) to reconstruct the visual flow. Triggers on: "把PPT转成markdown", "pptx转markdown", "PPTX→MD", "把幻灯片转成md", "导出PPTX内容", "extract slides as markdown", "把PPT做成知识库", "PPT转知识库给AI用". Best for technical writers, training-material authors, consultants, and agent/RAG pipelines who need to archive, search, re-style, or ingest slide content into a knowledge base. Do NOT use for translating PPTX (use the pptx-translate skill), editing the original .pptx file, or converting .pdf/.key files.'
agent_created: true
---

# pptx2md

Convert PowerPoint `.pptx` files to Markdown with images extracted into an
`assets/` folder. Preserves original text, group-shape hierarchy, reading
order, **tables** and **swimlane diagrams**. Output is faithful — no AI
rewriting — making it suitable as a preprocessing step for knowledge-base
ingestion.

## When to use

- Turn a `.pptx` into `.md` + images for editing, search, archiving, or restyling
- Preprocessing for knowledge-base / RAG ingestion (deterministic structure — see `references/styling.md`)

Do **not** use for: translating slides (use `pptx-translate`), modifying the
original `.pptx`, or converting `.pdf` / `.key` files.

## Quick start

```bash
python "<skill_dir>/scripts/pptx2md.py" <input.pptx> [output.md]
```

- `<output.md>` is optional; defaults to the source file's stem
- Extracted images go to `<output_dir>/assets/`; old contents are removed first
- Returns a `{page: [filename, ...]}` mapping for downstream tools
- The script lives at `scripts/pptx2md.py`; for programmatic use, import the
  `convert()` function — the skill is not a Python package

```python
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "pptx2md", pathlib.Path("<skill_dir>") / "scripts" / "pptx2md.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
md_path, by_page = mod.convert('input.pptx', 'out.md', asset_dir='assets')
# by_page == {1: ['page-01-img-01.png', ...], 2: [...], ...}
```

## How it works

### 1. Item extraction

The converter walks `Presentation.slides`, recursively descends into GROUP
shapes, and collects four kinds of items:

| Item type | What happens |
|-----------|-------------|
| **Picture** | Extracted to `assets/page-XX-img-YY.ext` (after master/background filtering) |
| **Text frame** | Paragraph text concatenated, kept as one block per shape |
| **Table** | Cell text extracted row-by-row, rendered as a GFM Markdown table |
| **Connector / diagram** | LINE shapes signal a diagram slide (see *Diagram handling* below) |

### 2. Diagram handling

Slides with LINE/connector shapes are detected automatically and rendered as
a cropped PNG image via LibreOffice (best quality). Two refinements keep the
output faithful to what users actually see in PowerPoint:

1. **Diagram-region cropping.** The flowchart's bounding box is computed from
   the LINE connectors and the `AUTO_SHAPE` nodes they actually touch
   (recursing through GROUPs). Standalone caption / container boxes on the
   side of a split slide are deliberately excluded. The rendered full-slide
   PNG is then cropped to that box, so descriptive copy that lives *outside*
   the diagram is **not** duplicated inside the image.
2. **Split-slide text extraction.** On split slides the left-hand
   explanatory column is pulled out and emitted as **plain paragraphs
   FIRST**, then the cropped **rendered image** of the flowchart is appended.
   This keeps the descriptive copy readable in plain-text / RAG pipelines
   while the diagram itself is preserved as a picture (its node text is not
   parsed, as that proved unreliable). A slide is treated as split only
   when some non-title text sits clearly to the **left** of the diagram
   bbox (beyond a clearance margin). A slide whose entire body *is* the
   flowchart is emitted as the cropped image alone.

LibreOffice is auto-detected in PATH, `LIBREOFFICE_PATH` env var, or common
install locations.

Additional rules:

- **Vector-SmartArt pages are also rendered.** Pages with no `LINE` shapes
  but ≥ `SHAPE_DIAGRAM_THRESHOLD` (= 15) `AUTO_SHAPE` descendants are
  treated as diagrams. This catches SmartArt / native PowerPoint shapes
  that were never converted to `PICTURE` and have no connectors.
- **Fallback when no renderer is available.** If LibreOffice is missing or
  fails to produce an image for a particular diagram slide, the page is
  emitted as structured swimlane text instead. Lanes are taken from the
  slide's `GROUP` shapes — the first text inside each GROUP is its lane
  name, and text items on the slide are assigned to the lane whose `top`
  is the last one `≤` the item's `top` (so they read in visual order
  within each lane). Items above the topmost lane form a synthetic role
  bar at the start. Each lane renders as a `### <name>` subsection with
  its items joined by `→` arrows. If the slide has no `GROUP`-shaped
  lanes at all, the helper returns an empty result and the page is
  emitted as plain text via the generic path (no `→` arrows).

### 3. Brand / master image exclusion

Background and decorative images are excluded so `assets/` stays focused on
real slide content. An image is dropped when **any** of these triggers:

| # | Heuristic | When it triggers | Typical case |
|---|-----------|------------------|--------------|
| 1 | **Full-bleed background** | `top ≈ 0`, `left ≈ 0`, `right ≥ 0.95 × slide_w`, `bottom ≥ 0.95 × slide_h` | Slide-master background covering the whole canvas |
| 2 | **Majority-recurring** | Identical image bytes (sha256) on `≥ max(2, ceil(0.5 × total_slides))` pages | Background image copied onto every slide |
| 3 | **Small corner brand** | Area `< 2%` of slide **and** width/height `< 20%` **and** 2+ edges within 10% of slide edge | Corporate logo, footer mark (too sparse for rule 2) |

The brand-asset thresholds are module-level constants at the top of
`scripts/pptx2md.py` (`BRAND_AREA_FRAC`, `BRAND_DIM_FRAC`,
`BRAND_MARGIN_FRAC`).

### 3b. Decorative standalone-picture exclusion (by slide title)

Some content slides carry purely illustrative pictures (e.g. icon art on
*业务痛点* / *应用价值* pages) whose information is already fully captured
by the extracted text. For those slides the standalone pictures are dropped
so the KB/RAG output stays text-only without losing signal.

Targeted, low-risk rule: a non-diagram slide's standalone pictures are
skipped only when its `##` title **contains** a keyword. The keyword list
is **not hard-coded** — it lives in `references/decorative_keywords.txt`
(one keyword per line, `#` comments and blank lines ignored; missing file →
no exclusions). It never touches the rendered flowchart image, never
touches body paragraphs, and only affects the specific pages whose title
matches. Edit that text file to enable/disable per deck. Programmatic
callers may pass `convert(..., decorative_keywords=[...])` or
`convert(..., decorative_keywords="path/to/file.txt")` to override per run.

### 4. Text cleaning

PowerPoint text frequently contains invisible control characters (e.g. `U+000B` vertical
tab for manual line breaks within a paragraph, `U+00A0` non-breaking space, or Unicode
format characters) that are not visible in PowerPoint but render as garbled boxes or
symbols in markdown output. All extracted text — body paragraphs, table cells, and slide
titles — passes through `_clean_text()` which:

| Character(s) | Treatment |
|---|---|
| `U+000B` (vertical tab / manual line break) | Replaced with space |
| `U+000C` (form feed) | Replaced with space |
| `U+00A0` (non-breaking space) | Replaced with space |
| C0 control set except `\n\r\t` | Stripped |
| C1 control set (`U+0080–U+009F`) | Stripped |
| Unicode format chars (`U+200B–U+200F`, `U+2028–U+202F`, `U+FEFF`) | Stripped |
| Multiple consecutive spaces | Collapsed to one |

This ensures the markdown output is clean, readable, and safe for downstream
knowledge-base ingestion without manual cleanup.

### 5. Reading order & headings

After collection, items are **sorted by (top, left)** to reconstruct
top-to-bottom, left-to-right reading order. The first short text per slide
(`len < 60`, no newline) becomes a `##` heading. Image references use
**relative paths** so the markdown is portable.

### Why not markitdown[pptx]?

`markitdown` writes image references like `![alt](图片28.jpg)` but **does
not** extract the image binary — the reference name (Chinese) does not match
the actual file inside the zip. All links are broken. `python-pptx` walking
the shape tree directly is the only reliable approach.

## Output layout

```
<output_dir>/
├── out.md                  # one section per slide, separated by ---
│                               # diagram slides include:
│                               #   cropped rendered image
└── assets/
    ├── page-01-img-01.png  # extracted pictures
    ├── page-01-img-02.jpg
    ├── slide-06.png         # cropped rendered diagram (if LibreOffice available)
    └── ...
```

## Dependencies

```bash
pip install python-pptx Pillow
```

**Optional — diagram rendering:** Install [LibreOffice](https://www.libreoffice.org/).
Without it, diagram slides fall back to structured text output.

## Bundled resources

- `scripts/pptx2md.py` — main converter (item extraction, brand filtering,
  table rendering, diagram detection + LibreOffice rendering / swimlane fallback)
- `references/styling.md` — deterministic output contract for KB ingestion
- `references/decorative_keywords.txt` — title keywords whose standalone
  decorative pictures are dropped on non-diagram slides (edit per deck)

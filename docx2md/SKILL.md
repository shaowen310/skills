---
name: docx2md
description: 'Convert .docx files to Markdown with all images extracted into an assets/ folder, preserving headings, lists, tables, and inline formatting. Triggers on: "把Word转成markdown", "docx转md", "Word→MD", "把Word转成md", "导出Word内容", "extract Word as markdown", "convert Word to markdown". Best for technical writers, documentation authors, and agent/RAG pipelines who need to archive, search, re-style, or ingest Word document content into a knowledge base. Do NOT use for translating .docx files (would need a separate skill), editing the original .docx, or converting .pdf/.pptx files.'
agent_created: true
---

# docx2md

Convert Word `.docx` files to Markdown with images extracted into an `assets/`
folder. Preserves headings, lists, tables, inline formatting (bold, italic,
code), and reading order. Output is faithful — no AI rewriting — making it
suitable as a preprocessing step for knowledge-base ingestion.

## When to use

- Turn a `.docx` into `.md` + images for editing, search, archiving, or restyling
- Preprocessing for knowledge-base / RAG ingestion (deterministic structure — see `references/styling.md`)

Do **not** use for: translating documents (would need a separate skill),
modifying the original `.docx`, or converting `.pdf` / `.pptx` files (use
`pptx2md` for the latter).

## Quick start

```bash
python "<skill_dir>/scripts/docx2md.py" <input.docx> [output.md]
```

- `<output.md>` is optional; defaults to the source file's stem with `.md`
- Extracted images go to `<output_dir>/assets/`; old contents are removed first
- Returns a `{page: [filename, ...]}` mapping via stdout as JSON

```python
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "docx2md", pathlib.Path("<skill_dir>") / "scripts" / "docx2md.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
md_path, by_page = mod.convert('input.docx', 'out.md', asset_dir='assets')
# by_page == {1: ['page-01-img-01.png', ...], 2: [...], ...}
```

## How it works

### 1. Item extraction

The converter walks `Document.paragraphs`, `Document.tables`, and inline shapes,
collecting these item types:

| Item type | What happens |
|-----------|-------------|
| **Heading** (style `Heading N`) | Rendered as `##` / `###` etc. — preserves hierarchy |
| **Paragraph** | Plain text with inline formatting converted to Markdown (`**bold**`, `*italic*`, `` `code` ``) |
| **List** (bulleted / numbered) | Rendered as proper Markdown list syntax with proper nesting |
| **Table** | Cell text extracted row-by-row, rendered as a GFM Markdown table |
| **Inline image** | Extracted to `assets/page-XX-img-YY.ext` |
| **Page break** | Rendered as `---` horizontal rule |

### 2. Image extraction

Each inline shape / picture is written to `assets/page-XX-img-YY.<ext>` with
a relative reference in the Markdown output. Master/header/footer images
are excluded.

### 3. Text cleaning

Word documents frequently contain invisible control characters. All extracted
text passes through a cleaning pass:

| Character(s) | Treatment |
|---|---|
| `U+000B` (vertical tab) | Replaced with space |
| `U+000C` (form feed) | Replaced with space |
| `U+00A0` (non-breaking space) | Replaced with space |
| C0 control set except `\n\r\t` | Stripped |
| C1 control set (`U+0080–U+009F`) | Stripped |
| Unicode format chars (`U+200B–U+200F`, `U+2028–U+202F`, `U+FEFF`) | Stripped |
| Multiple consecutive spaces | Collapsed to one |

### 4. Reading order & headings

Items are processed in document order (the natural reading order of a Word
document). The highest-level heading found becomes the document title (`#`),
with subsequent headings rendered at their appropriate level (`##` → `###` etc).

## Output layout

```
<output_dir>/
├── out.md                  # one section per heading, separated by ---
└── assets/
    ├── page-01-img-01.png  # extracted pictures
    ├── page-01-img-02.jpg
    └── ...
```

## Dependencies

```bash
pip install python-docx Pillow
```

- **Windows**: EMF/WMF vector diagrams (e.g. Visio-style flow charts) are
  rendered to PNG automatically via the built-in GDI API — no extra package
  needed.
- **Other platforms**: install `pillow-emf` (EMF) and/or `PyMuPDF` so vector
  diagrams still convert to viewable PNG. If no converter is available, the
  vector file is left as-is and the reference is still emitted (but may not
  render in all viewers).

## Bundled resources

- `scripts/docx2md.py` — main converter (item extraction, table rendering,
  image extraction, text cleaning)
- `references/styling.md` — deterministic output contract for KB ingestion

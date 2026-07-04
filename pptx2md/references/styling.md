# Output Specification (for Knowledge Base Construction and Agent Consumption)

The markdown produced by `pptx2md` is a **machine-readable, splittable, traceable** knowledge-base corpus. This document defines its deterministic structure so that an Agent can parse, chunk, and extract fields into a knowledge base directly, with no manual polishing required.

---

## 1. Output Contract

The whole file satisfies the following invariants; an Agent can perform deterministic parsing against them.

| Item | Rule | Example |
|------|------|---------|
| First line of file | `# <PPT file name>` (emitted by the script) | `# Quarterly Report` |
| Slide boundary | `<!-- Slide N -->` comment, **unique and monotonically increasing**, used as a chunk anchor | `<!-- Slide 3 -->` |
| Slide title | The first short text on the slide (< 60 characters, no line breaks) is rendered as `##` | `## Project Progress` |
| Body | The remaining text paragraphs, original line breaks preserved | Paragraph block |
| Image reference | Relative path, fixed name `assets/page-XX-img-YY.<ext>` | `![Image](assets/page-03-img-01.png)` |
| Flow diagram | Rendered as `assets/slide-XX.png` plus a swimlane text version | See SKILL.md "Diagram handling" |

> **Masters, backgrounds, and brand images are auto-excluded** (see the "Heuristic" table in `SKILL.md`): `assets/` and image references only contain real content images. The rules cover three categories of decorative image: full-bleed backgrounds, page-spanning copies of the same background, and corner-anchored small brand logos / header-footer marks. No further filtering is needed at KB ingestion time.

---

## 2. Chunking Strategy

The knowledge base should treat **a single slide as the smallest ingestion unit**:

1. **Splitting** — use the regex `<!--\s*Slide\s+(\d+)\s*-->` to slice out each slide block.
2. **Unit structure** — each chunk = `{ slide_no, title, body_text, images[] }`.
3. **Title** — take the first `## ` line inside the block as `title`; if none, `title` falls back to empty or the file-level title.
4. **Body** — the plain text remaining after stripping `<!-- Slide N -->` and the title line.
5. **Images** — extract every `!\[[^\]]*\]\((assets/[^)]+)\)` into the `images` list (relative paths; concatenate with the assets root at ingestion time).

```python
import re
text = open(md_path, encoding='utf-8').read()
blocks = re.split(r'<!--\s*Slide\s+(\d+)\s*-->', text)
# blocks[0] = file header; thereafter, every two blocks = (slide_no, content)
for i in range(1, len(blocks), 2):
    no, content = int(blocks[i]), blocks[i+1]
    title = re.search(r'^##\s+(.+)$', content, re.M)
    images = re.findall(r'!\[[^\]]*\]\((assets/[^)]+)\)', content)
```

---

## 3. Suggested Fields and Metadata

When writing to the knowledge base, attach the following to each chunk:

| Field | Source |
|-------|--------|
| `source_file` | Original PPT file name (the `# ` line) |
| `slide_no` | The N in `<!-- Slide N -->` |
| `title` | The `## ` title line |
| `content` | Plain text of the body |
| `images` | List of relative paths |
| `has_diagram` | Whether the `slide-XX.png` render exists |
| `lang` | Source language; set explicitly per deck (e.g. `zh`, `en`) |

---

## 4. Image Handling

- Paths are always **relative** and case-sensitive: `page-03-img-01.png` ≠ `Page-03-img-01.png`.
- Move the `assets/` directory together with the markdown at ingestion time so the relative references stay valid; otherwise the images break.
- Non-ASCII file names are allowed, but markdown references must **not** be URL-encoded.

---

## 5. Character Set and Encoding

- Output file is **UTF-8 (no BOM)**; agents should read with `encoding='utf-8'`.
- Source-language punctuation is preserved as-is. Do **not** auto-convert Chinese punctuation (`，。：；？""''`) to English equivalents — that loses the original meaning. Likewise, leave English punctuation in English decks untouched.

---

## 6. Do Not "Rewrite"

Extraction is not rewriting. The ingested corpus must be the **same content** the user sees against the PPT:

| Anti-pattern | Consequence |
|--------------|-------------|
| Adding emoji to titles | Distorts the original intent |
| Bolding every number | Loses fidelity |
| Merging adjacent paragraphs | Loses line breaks |
| Fixing typos | User can no longer cross-check with screenshots and original business description |
| Auto-numbering / auto-listing | Destroys the author's original structure |

If a "secondarily processed" version is needed, save it to a **new** file — do not overwrite the raw extraction.

---

## 7. Speaker Notes (Not Extracted)

`pptx2md` does **not** extract speaker notes. If they need to be ingested as well, do a second pass with `python-pptx` and attach the result as an independent `notes` field on the corresponding `slide_no`:

```python
from pptx import Presentation
prs = Presentation(pptx_path)
for i, slide in enumerate(prs.slides, 1):
    notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ''
    # write to chunk[i]['notes']
```

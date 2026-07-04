# docx2md Output Contract

This document defines the deterministic output contract that `docx2md`
guarantees. Downstream tools (knowledge-base ingestion, RAG pipelines,
search indexing) can rely on this structure.

## File Encoding

- **UTF-8 without BOM**
- Line endings: `\n` (LF)

## Section Structure

Every heading in the document produces a section delimited by a `<!-- Page N -->`
anchor comment:

```markdown
<!-- Page 1 -->
# Document Title

Content for the first section…

<!-- Page 2 -->
## First Heading

Content for the second section…
```

**Rules:**
- `#` (H1) is used for the document title (Word "Title" style or "Heading 1")
- `##`–`######` (H2–H6) map directly to Word "Heading 2"–"Heading 6" styles
- Each heading increments the page counter by 1
- Non-heading content belongs to the preceding heading's section

## Inline Formatting

| Word Formatting | Markdown Output |
|-----------------|-----------------|
| **Bold** | `**bold text**` |
| *Italic* | `*italic text*` |
| Bold + Italic | `***bold italic***` |
| `Courier New` font | `` `inline code` `` |
| Hyperlink | `[link text](url)` |

## Lists

### Bulleted Lists

```markdown
- Item level 1
  - Item level 2
    - Item level 3
```

### Numbered Lists

```markdown
1. First item
1. Second item
   1. Nested item
```

## Tables

Tables are rendered as GitHub Flavored Markdown tables:

```markdown
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

**Rules:**
- Column widths are padded to align with the widest cell per column
- Empty cells are represented as empty strings
- Trailing blank rows are dropped

## Images

- Extracted to `assets/` directory next to the output `.md` file
- Referenced with relative paths: `![alt](assets/rIdX.png)`
- Naming: `rId<number>.<ext>` (as extracted from the Word document's image relationships)
- Supported formats: PNG, JPEG, GIF, BMP, TIFF, EMF, WMF, SVG

## Text Cleaning

All extracted text is cleaned of invisible control characters:

| Character | Replacement |
|-----------|-------------|
| U+000B (vertical tab) | Space |
| U+000C (form feed) | Space |
| U+00A0 (non-breaking space) | Space |
| C0 controls (except `\n\r\t`) | Removed |
| C1 controls (U+0080–U+009F) | Removed |
| Unicode format characters | Removed |
| Multiple consecutive spaces | Collapsed to one |

## No AI Rewriting

The output is a **faithful** extraction of the original Word document's text.
No summarization, rephrasing, or content generation is performed.

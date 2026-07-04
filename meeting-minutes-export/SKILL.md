---
name: meeting-minutes-export
description: 'Orchestrator that runs meeting-minutes then exports the result to Word (.docx). Use when the user wants both structured meeting minutes and a Word document. Depends on the local meeting-minutes skill and the md-exporter pip package.'
agent_created: true
---

# Meeting Minutes Export

Convert a meeting **transcript** into both structured meeting minutes (`.md`) and a
Word document (`.docx`). This is a thin orchestrator that chains two steps.

## Dependencies

| Dependency | Type | Role |
|------------|------|------|
| **meeting-minutes** | Local skill | Extracts structured data, fills template → `.md` |
| **md-exporter** (`pip install md-exporter`) | Python package | Converts `.md` → `.docx` via Pandoc |

## Workflow

### Step 1: Run meeting-minutes

Follow the `meeting-minutes` skill workflow:
- Gather transcript + template
- Extract structured data (attendees, agenda, discussion, decisions, action items, etc.)
- Fill template → `output.md` in CWD

### Step 2: Install md-exporter (if missing)

```bash
pip install md-exporter
```

### Step 3: Convert to .docx

```bash
markdown-exporter md_to_docx <output.md> <output.docx>
```

**Custom style template** — if the user provides a `.docx` style reference:

```bash
markdown-exporter md_to_docx <output.md> <output.docx> --template custom_style.docx
```

Users can create the template in Word or LibreOffice by styling the built-in
names (Heading 1/2/3, Normal, Table Grid), saving it as `.docx`, and uploading
it. Under the hood `md_to_docx` passes `--reference-doc=<path>` to Pandoc.

**Priority:**
1. User-provided template (`--template` / `docx_template_file` parameter)
2. Bundled default template (`md_exporter/assets/template/docx_template.docx`)
3. Pandoc built-in default (fallback)

### Step 4: Present outputs

Present both the `.md` (for editing/review) and the `.docx` (for sharing/printing).
Summarize: # attendees, # decisions, # action items, and any `TBD` items.

## Output files

| Artifact | Pattern | Example |
|----------|---------|---------|
| Markdown minute | `YYYYMMDD_{MeetingPurpose}_Minutes.md` | `20250709_Sprint_Retro_Minutes.md` |
| Word document | `YYYYMMDD_{MeetingPurpose}_Minutes.docx` | `20250709_Sprint_Retro_Minutes.docx` |

Both files are saved to the working directory (CWD).

## Typical user prompts

| Language | Example |
|----------|---------|
| English | "Summarize this transcript into meeting minutes and export as Word" |
| Chinese | "把这份会议录音整理成会议纪要，并导出为 Word 文档" |
| Chinese | "整理会议记录并生成 docx 文件" |

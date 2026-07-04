---
name: kb-ingest
description: 'Thin orchestrator that turns PowerPoint `.pptx` slides into knowledge-base-ready, slide-level JSONL chunks for RAG / agent pipelines. Delegates extraction to the pptx2md skill, then parses the Markdown per the deterministic output contract (slide anchors, field extraction, image/encoding rules) into one record per slide with title, body, images, and metadata. Triggers on: "把PPT做成知识库", "PPT转知识库给AI用", "ingest PPTX into KB", "build RAG dataset from slides", "把幻灯片切片入库". Best for building agent/RAG knowledge bases, search indexes, or training corpora from slide decks. Do NOT use for translating PPTX (use the pptx-translate skill) or for plain markdown export without chunking (use the pptx2md skill).'
agent_created: true
---

# kb-ingest

A **thin orchestrator** that converts PowerPoint decks into a deterministic,
slide-level JSONL dataset ready for any knowledge-base / RAG / agent pipeline.
It does **not** re-implement extraction — it delegates to the `pptx2md` skill
for the faithful `pptx → md` transform, then applies the chunking contract
from `pptx2md/references/styling.md`.

```
.pptx ──(pptx2md)──▶ out.md + assets/ ──(build_kb.py)──▶ kb.jsonl
                                                  (one record per slide)
```

## When to use

- The user wants to **ingest slide decks into a knowledge base / RAG system /
  search index / agent memory** — not just a human-readable markdown file.
- The user says things like "把PPT做成知识库", "把幻灯片切片入库",
  "build a RAG dataset from these slides", "PPT转知识库给AI用".
- You already have a `pptx2md`-produced `.md` and want to chunk it for ingestion
  (skips the conversion step).

Do **not** use for: translating the deck (use `pptx-translate`), or plain
markdown export without chunking (use `pptx2md` directly).

## Workflow

### Step 1 — Convert (only if starting from .pptx)

`build_kb.py` calls `pptx2md` automatically. If you already have the `.md`,
pass it directly and Step 1 is skipped.

### Step 2 — Chunk into JSONL

```bash
# End-to-end from a pptx (conversion + chunking):
python "<skill_dir>/scripts/build_kb.py" input.pptx --out kb.jsonl

# From an existing markdown (skip conversion):
python "<skill_dir>/scripts/build_kb.py" input.md --out kb.jsonl

# Resolve relative assets/ paths to absolute URLs for an HTTP-served KB:
python "<skill_dir>/scripts/build_kb.py" input.md \
    --base-url https://kb.example.com/assets/ --out kb.jsonl
```

> **Note**: `pptx2md` is resolved automatically as a sibling skill
> (`../pptx2md/scripts/pptx2md.py`). If it lives elsewhere, pass
> `--pptx2md-dir /path/to/pptx2md`.

## Output schema

`kb.jsonl` has **one JSON object per line, one per slide**:

| Field | Type | Source |
|-------|------|--------|
| `source_file` | string | original `.pptx` stem (the `# ` title) |
| `slide_no` | int | `N` from `<!-- Slide N -->` |
| `title` | string | first `## ` heading (or `""` if none) |
| `content` | string | body text; anchors/titles stripped |
| `images` | string[] | relative paths under `assets/` (or absolute URLs w/ `--base-url`) |
| `has_diagram` | bool | `true` if a rendered diagram image (`slide-XX.png`) is present |
| `lang` | string | fixed `zh` by default (`--lang` to override) |

Example line:

```json
{"source_file":"季度汇报","slide_no":3,"title":"项目进展","content":"Q1 完成 80%…","images":["assets/page-03-img-01.png"],"has_diagram":false,"lang":"zh"}
```

## Downstream ingestion

`kb.jsonl` is backend-agnostic. Typical next steps (outside this skill):

- **Embed + index**: read each line, embed `title + "\n" + content`
  (optionally append image OCR/caption), upsert into a vector store.
- **Keep assets**: copy the `assets/` directory alongside `kb.jsonl` so the
  relative image paths resolve, or serve it and pass `--base-url`.
- **Graph/diagram**: index rendered diagram images (`slide-XX.png`) separately for diagram search.

## Dependencies

```bash
pip install python-pptx   # only needed when converting a .pptx
```

## Bundled resources

- `scripts/build_kb.py` — the orchestrator: delegates to `pptx2md`, parses
  markdown per `styling.md`, emits deterministic `kb.jsonl`.

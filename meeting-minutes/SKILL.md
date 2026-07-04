---
name: meeting-minutes
description: 'Turn a meeting transcript (or pre-transcribed text) plus a Markdown minute template into a clean, structured meeting minute. Use when the user asks to summarize a meeting, write meeting notes/minutes from a transcript, or fill a minutes template. Triggers on: "会议纪要", "整理会议纪要", "meeting minutes", "summarize the meeting", "写会议纪要", "根据录音整理", "fill the minutes template", "把会议记录整理成模板". The assistant reads the transcript, extracts attendees/agenda/discussion/decisions/action items, and fills the Markdown template. Source transcript and template are never modified.'
agent_created: true
---

# Meeting Minutes

Convert a meeting **transcript** (or any pre-transcribed text) plus a **Markdown
minute template** into a clean, structured meeting minute. No audio processing
is involved — the user supplies text.

## When to use

- The user pastes a transcript, or points to a `.md` / `.txt` transcript file,
  and wants a structured meeting minute.
- The user has a minutes template (Markdown) they want filled, or wants the
  skill's default template.
- The user says "整理会议纪要", "summarize the meeting", "fill the minutes
  template", etc.

Do **not** use for: transcribing raw audio/video (out of scope — ask the user to
provide a transcript first).

## Inputs / outputs

| Item | Rule |
|------|------|
| **Transcript** | Read-only text source (`.md` / `.txt`, or pasted). Never modified. |
| **Template** | Markdown minute template (yours, or the bundled default). Never modified. |
| **Output** | Filled minute, saved to **CWD**: `YYYYMMDD_{MeetingPurpose}_Minutes.md` <br>`MeetingPurpose` comes from `meeting_purpose`/`meeting_title`, kept short (≤5 words; safety cap prevents lengthy names). Falls back to `{MeetingPurpose}_Minutes.md` if no date is found. |

The skill ships `references/minutes_template.md` as the default template.

## Workflow

### Step 1: Gather inputs

1. Get the transcript — a file path, or pasted text.
2. Get the template — a user template, or use the default:
   `references/minutes_template.md`.
3. Confirm the desired **output path** (default: `meeting-minutes.md` in CWD).

### Step 2: Extract structured data from the transcript

Read the transcript and produce a JSON data object with these keys. Use `null`
or `[]` when a section is absent — do **not** invent content.

| Key | Type | Notes |
|-----|------|-------|
| `meeting_title` | string | From subject/opening, else infer a short title |
| `meeting_purpose` | string | Optional. Short purpose/theme used in the output filename (`YYYYMMDD_{MeetingPurpose}_Minutes.md`). Keep it short (aim for ≤5 words; the script applies a safety cap so the filename stays brief). Defaults to `meeting_title` when omitted. |
| `date` | string | `YYYY-MM-DD` when stated |
| `time` | string | Start–end, e.g. `14:00–15:00` |
| `location` | string | Room / platform (Zoom, Teams…) |
| `note_taker` | string | Person recording minutes |
| `language` | string | Output language code: `"en"` (default) or `"zh"` (or any label the assistant understands, e.g. `"中文"`). Localizes the script's generated labels/headers so the minute matches the **transcript's language**. |
| `attendees` | list[str] | `Name (role)` — from speaker labels (`Alice:`) or roll-call. Unlabeled or "not present" mentions — note under `Open Issues` or the relevant discussion point; no separate `absent` field is exposed. |
| `agenda` | list[str] | Topics planned / announced |
| `discussion` | list[obj] | `{ "topic": str, "summary": str }` — 2–4 concise bullets of key points, options considered, disagreements |
| `decisions` | list[str] | Explicit decisions / approvals, with rationale when given |
| `action_items` | list[obj] | `{ "action": str, "owner": str, "due": str, "status": "Open" }` — owner/due `TBD` if not stated |
| `open_issues` | list[str] | Risks, blockers, parking-lot items |
| `next_meeting` | obj | `{ "date": str, "topics": str }` — if absent, the `## Next Meeting` section is **omitted entirely** from the output |

**Extraction rules (opinionated):**

- Map `Speaker:` labels in the transcript → `attendees`. Unlabeled or
  "not present" mentions — note under `Open Issues` or the
  relevant discussion point; no separate `absent` field is exposed.
- Pull explicit decisions, approvals, and "we will / let's / agreed to" phrasing
  → `action_items` with owner + due when stated, else `TBD`.
- Summarize each agenda topic into 2–4 bullets; **preserve numbers, dates,
  names, and technical terms** verbatim — do not paraphrase metrics.
- **Language:** Detect the transcript's language and set `language` to match
  (e.g. `zh` for a Chinese transcript). Write **all** extracted content in that
  language. For Path A also localize the template's section headers/labels; for
  Path B pass a localized template — the script localizes its own generated
  action-items table headers and the `(None)` / `(TBD)` labels via `language`.
  Empty sections (`{{next_meeting}}` with no data) are automatically removed
  from the rendered output.
- If the transcript is partial, mark uncertain fields `TBD` and note it in the
  minute (e.g. under Open Issues).

### Step 3: Fill the template

Two equivalent paths — pick whichever fits:

**A. Direct (recommended):** Fill the template in place from the JSON you just
built. Replace each `{{placeholder}}` with the rendered value, and remove any
leftover `{{...}}` tokens. Section headers in the template stay as-is.

**B. Scripted (deterministic):** Save the JSON to a file and render with the
bundled script. This guarantees consistent formatting/tables:

```bash
python "<skill_dir>/scripts/fill_minutes.py" <data.json> <template.md> <output.md>
```

- `<template.md>` and `<output.md>` are optional; they default to the bundled
  template and `YYYYMMDD_<MeetingPurpose>_Minutes.md` in CWD (named from the
  `date` + `meeting_purpose`/`meeting_title` field; `<MeetingPurpose>_Minutes.md` if no date).
- To scaffold a sample JSON, run:
  ```bash
  python "<skill_dir>/scripts/fill_minutes.py" --init-skeleton skeleton.json
  ```

The script renders `{{attendees}}`/`{{decisions}}`/`{{open_issues}}`
as bullet lists, `{{agenda}}` as a numbered list, `{{discussion}}` as
`### topic` sub-sections, `{{action_items}}` as a Markdown table, and
`{{next_meeting}}` as a key/value block. When `{{next_meeting}}` data is
absent, the entire `## Next Meeting` heading and its content are
**removed** from the output — no placeholder or fallback remains.

### Step 4: Verify & present

1. Confirm no `{{placeholder}}` tokens remain in the `.md` output.
2. Confirm the `.md` file was written.
3. Confirm the source transcript and template are untouched.
4. Present the output path and a short summary: # attendees, # decisions, #
   action items, and any `TBD`/open items needing follow-up.

If the user also needs a Word (.docx) copy, use the
**meeting-minutes-export** orchestrator skill.

> *For the full end-to-end workflow (.md → .docx), see*
> *`meeting-minutes-export/SKILL.md`.*

## File organization rules

- **Input transcript / template**: Read-only. Never modified.
- **Output minute**: Saved to CWD. Never overwrites the template.

## Bundled resources

- `references/minutes_template.md` — default Markdown template with
  `{{placeholder}}` tokens.
- `scripts/fill_minutes.py` — deterministic renderer (JSON → templated `.md`).

## Typical user prompts

| Language | Example |
|----------|---------|
| Chinese | "把这份会议记录整理成会议纪要" |
| Chinese | "根据录音整理成模板格式的纪要" |
| English | "Summarize this meeting transcript into minutes" |
| English | "Fill my minutes template from this transcript" |

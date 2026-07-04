#!/usr/bin/env python3
"""
fill_minutes.py — Render a Markdown meeting-minute template from a JSON data file.

Usage:
  python fill_minutes.py <data.json> [template.md] [output.md]
  python fill_minutes.py --init-skeleton [skeleton.json]

If template.md is omitted, the bundled default template
(references/minutes_template.md) is used.
If output.md is omitted, it defaults to YYYYMMDD_<MeetingPurpose>_Minutes.md
(derived from `date` + `meeting_title`/`meeting_purpose`, purpose capped at 5
words); falls back to <MeetingPurpose>_Minutes.md when no date is found.

The script renders {{placeholder}} tokens using a fixed data schema:
  scalar     : meeting_title, date, time, location, note_taker
  language   : language code ("en"/"zh"/...) controlling script-generated labels
  bullets    : attendees, decisions, open_issues
  discussion   -> list of {topic, summary}
  table      : action_items -> list of {action, owner, due, status}
  key/value  : next_meeting -> {date, topics}

The source transcript and template are never modified.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# --- Known schema keys ------------------------------------------------------

SCALAR_KEYS = {
    "meeting_title", "date", "time", "location", "note_taker",
}

BULLET_KEYS = {"attendees", "decisions", "open_issues", "agenda"}

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

# Matches a Markdown heading followed by only whitespace/blank lines,
# terminated by another heading (same file) or end-of-string.  Used in
# post-processing to clean up empty sections after template filling.
EMPTY_SECTION_RE = re.compile(
    r"^#{1,3}\s+.+\n(?:\s*\n)*(?=#{1,3}\s+|\Z)",
    re.MULTILINE,
)


# --- Localization -----------------------------------------------------------

# Hardcoded (non-template) strings the script emits. Localized by the
# `language` data field so the output matches the transcript's language.
L10N: dict[str, dict[str, Any]] = {
    "en": {
        "none_recorded": "(None recorded)",
        "none": "(None)",
        "tbd": "(TBD)",
        "date_label": "Date",
        "topics_label": "Proposed topics",
        "open_status": "Open",
        "action_headers": ["Action", "Owner", "Deadline", "Status"],
    },
    "zh": {
        "none_recorded": "（未记录）",
        "none": "（无）",
        "tbd": "（待定）",
        "date_label": "日期",
        "topics_label": "拟议议题",
        "open_status": "进行中",
        "action_headers": ["行动项", "负责人", "截止日期", "状态"],
    },
}


def _l10n(data: dict[str, Any]) -> dict[str, Any]:
    """Resolve the localization bundle from the data's `language` field.

    Defaults to English to stay backward compatible when `language` is absent.
    """
    lang = str(data.get("language", "en")).strip().lower()
    if lang.startswith("zh") or lang in ("chinese", "中文", "汉语"):
        return L10N["zh"]
    return L10N["en"]


# --- Renderers --------------------------------------------------------------

def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def render_scalar(value, l10n: dict[str, Any]) -> str:
    if _empty(value):
        return l10n["none_recorded"]
    return str(value).strip()


def render_bullets(value, l10n: dict[str, Any]) -> str:
    if _empty(value):
        return l10n["none"]
    if isinstance(value, str):
        # Treat each non-empty line as a bullet
        lines = [ln.strip("- ").strip() for ln in value.splitlines() if ln.strip()]
        return "\n".join(f"- {ln}" for ln in lines) if lines else l10n["none"]
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return "\n".join(f"- {it}" for it in items) if items else l10n["none"]
    return render_scalar(value, l10n)


def render_discussion(value, l10n: dict[str, Any]) -> str:
    if _empty(value):
        return l10n["none"]
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        blocks = []
        for entry in value:
            if isinstance(entry, dict):
                topic = str(entry.get("topic", "")).strip() or "Topic"
                summary = entry.get("summary", "")
                if isinstance(summary, (list, tuple)):
                    body = "\n".join(f"- {str(s).strip()}" for s in summary if str(s).strip())
                else:
                    body = str(summary).strip()
                blocks.append(f"### {topic}\n{body}".rstrip())
            else:
                blocks.append(f"- {str(entry).strip()}")
        return "\n\n".join(blocks) if blocks else l10n["none"]
    return render_scalar(value, l10n)


def render_action_items(value, l10n: dict[str, Any]) -> str:
    if _empty(value):
        return l10n["none"]
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], dict):
        headers = l10n["action_headers"]
        rows = [list(headers), ["---"] * len(headers)]
        for item in value:
            rows.append([
                str(item.get("action", "")).strip(),
                str(item.get("owner", l10n["tbd"])).strip() or l10n["tbd"],
                str(item.get("due", l10n["tbd"])).strip() or l10n["tbd"],
                str(item.get("status", l10n["open_status"])).strip() or l10n["open_status"],
            ])
        return "\n".join("| " + " | ".join(cells) + " |" for cells in rows)
    # Fallback: single-column bullet list
    return render_bullets(value, l10n)


def render_next_meeting(value, l10n: dict[str, Any]) -> str:
    if _empty(value):
        return ""
    if isinstance(value, dict):
        date = str(value.get("date", l10n["tbd"])).strip() or l10n["tbd"]
        topics = str(value.get("topics", l10n["tbd"])).strip() or l10n["tbd"]
        return f"- **{l10n['date_label']}:** {date}\n- **{l10n['topics_label']}:** {topics}"
    return render_scalar(value, l10n)


RENDERERS = {
    "discussion": render_discussion,
    "action_items": render_action_items,
    "next_meeting": render_next_meeting,
}


def render_value(key: str, value, l10n: dict[str, Any]) -> str:
    if key in SCALAR_KEYS:
        return render_scalar(value, l10n)
    if key in BULLET_KEYS:
        return render_bullets(value, l10n)
    if key in RENDERERS:
        return RENDERERS[key](value, l10n)
    # Unknown key: best-effort
    if isinstance(value, (list, tuple)):
        return render_bullets(value, l10n)
    return render_scalar(value, l10n)


# --- Template filling -------------------------------------------------------

def fill_template(template_text: str, data: dict[str, Any]) -> str:
    l10n = _l10n(data)

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return render_value(key, data.get(key), l10n)

    filled = PLACEHOLDER_RE.sub(repl, template_text)
    return EMPTY_SECTION_RE.sub("", filled)


# --- CLI helpers ------------------------------------------------------------

def default_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "minutes_template.md"


def write_skeleton(path: Path) -> None:
    skeleton = {
        "meeting_title": "Example Project Sync",
        "date": "2026-07-06",
        "time": "14:00-15:00",
        "location": "Zoom",
        "note_taker": "Bob (Eng)",
        "language": "en",
        "attendees": ["Alice (PM)", "Bob (Eng)", "Carol (Design)"],
        "agenda": ["Project status", "Q3 goals"],
        "discussion": [
            {"topic": "Project status", "summary": "On track; 2 items at risk."},
            {"topic": "Q3 goals", "summary": "Prioritize onboarding flow."},
        ],
        "decisions": ["D1: Slip launch to August.", "D2: Hire 1 contractor."],
        "action_items": [
            {"action": "Draft onboarding spec", "owner": "Carol", "due": "2026-07-13", "status": "Open"},
            {"action": "Post risk to tracker", "owner": "Bob", "due": "2026-07-08", "status": "Open"},
        ],
        "open_issues": ["API latency above SLO."],
        "next_meeting": {"date": "2026-07-20", "topics": "Design review"},
    }
    path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Wrote sample data skeleton: {path}")


# --- Main -------------------------------------------------------------------

def _slug(text: str, max_words: int = 5) -> str:
    """Build a filesystem-safe meeting-purpose slug from text.

    Keeps word characters (incl. CJK), strips other punctuation. The purpose
    should be kept short (aim for ~5 words); `max_words` is a soft safety cap so
    the filename never gets lengthy. Falls back to "meeting" when nothing
    usable remains.
    """
    words = [re.sub(r"[^\w一-鿿]+", "", w) for w in str(text).split()]
    words = [w for w in words if w][:max_words]
    return "-".join(words) or "meeting"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Markdown minutes template from JSON.")
    parser.add_argument("data_json", nargs="?", help="JSON data file")
    parser.add_argument("template_md", nargs="?", help="Template .md (defaults to bundled template)")
    parser.add_argument("output_md", nargs="?", help="Output .md (defaults to YYYYMMDD_<Purpose>_Minutes.md)")
    parser.add_argument("--init-skeleton", nargs="?", const="skeleton.json",
                        help="Write a sample JSON data file and exit")
    args = parser.parse_args()

    if args.init_skeleton:
        write_skeleton(Path(args.init_skeleton))
        return 0

    if not args.data_json:
        parser.error("data_json is required (or use --init-skeleton)")

    data_path = Path(args.data_json)
    if not data_path.exists():
        print(f"❌ Data file not found: {data_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {data_path}: {e}", file=sys.stderr)
        return 1

    template_path = Path(args.template_md) if args.template_md else default_template_path()
    if not template_path.exists():
        print(f"❌ Template not found: {template_path}", file=sys.stderr)
        return 1

    template_text = template_path.read_text(encoding="utf-8")
    output_text = fill_template(template_text, data)

    if args.output_md:
        out_path = Path(args.output_md)
    else:
        # Default name: YYYYMMDD_<MeetingPurpose>_Minutes.md
        # Purpose comes from `meeting_purpose` (or `meeting_title`); kept short
        # (aim ~5 words) with a 5-word safety cap so the filename stays brief.
        date_str = str(data.get("date", "")).strip()
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
        date_part = f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}" if m else ""
        purpose = _slug(data.get("meeting_purpose") or data.get("meeting_title", ""), 5)
        name = f"{date_part}_{purpose}_Minutes.md" if date_part else f"{purpose}_Minutes.md"
        out_path = Path(name)
    out_path.write_text(output_text, encoding="utf-8")

    remaining = PLACEHOLDER_RE.findall(output_text)
    if remaining:
        print(f"⚠️  {len(remaining)} unfilled placeholder(s): {sorted(set(remaining))}")

    print(f"✓ Minutes written: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

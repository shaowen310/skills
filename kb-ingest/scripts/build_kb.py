#!/usr/bin/env python3
"""
build_kb.py — pptx2md orchestrator for knowledge-base ingestion.

Turns a .pptx (or an already-converted .md) into a deterministic JSONL of
slide-level chunks ready for any RAG / vector-store pipeline.

This is a thin orchestrator: it delegates the actual PPTX→Markdown extraction
to the `pptx2md` skill (scripts/pptx2md.py), then parses the produced Markdown
according to the deterministic output contract documented in
`pptx2md/references/styling.md` (slide anchors, field extraction, image and
encoding rules, no rewriting).

Output
------
Each line of the JSONL output is one JSON object, one per slide:

  {
    "source_file": str,    # original .pptx stem (the `# ` title)
    "slide_no":    int,    # N from `<!-- Slide N -->`
    "title":       str,    # first `## ` heading, or "" if none
    "content":     str,    # body text, no anchors/titles
    "images":      [str],  # relative paths under assets/
    "has_diagram": bool,   # True if a rendered diagram image is present
    "lang":        str     # fixed "zh" by default
  }

Usage
-----
  # Convert a pptx end-to-end (pptx2md is invoked automatically):
  python build_kb.py <input.pptx> --out kb.jsonl

  # Ingest an already-converted markdown (skips the pptx2md step):
  python build_kb.py <input.md> --out kb.jsonl

  # Turn relative image paths into absolute URLs for an HTTP-served asset dir:
  python build_kb.py <input.md> --base-url https://kb.example.com/assets/ --out kb.jsonl

Dependencies: python-pptx (only needed when a .pptx is given).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

# A single slide chunk written to the output JSONL. Values are heterogeneous
# (str / int / list[str] / bool), so we use a broad alias rather than a
# narrower typed dict.
Chunk = dict[str, Any]


# ----------------------------------------------------------------------------
# Locating the pptx2md converter
# ----------------------------------------------------------------------------
def _load_pptx2md(skill_dir: str | None) -> Any:
    """Import the pptx2md.convert function from the sibling skill.

    Resolution order:
      1. --pptx2md-dir argument (explicit)
      2. ../pptx2md/scripts/pptx2md.py  (sibling skill, relative to this file)
      3. module import 'pptx2md' (if installed on PYTHONPATH)
    """
    candidates: list[Path] = []
    if skill_dir:
        candidates.append(Path(skill_dir) / "scripts" / "pptx2md.py")
    here = Path(__file__).resolve().parent
    candidates.append(here.parent.parent / "pptx2md" / "scripts" / "pptx2md.py")

    for cand in candidates:
        if cand.exists():
            spec = importlib.util.spec_from_file_location("pptx2md", cand)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    # Fall back to a normal import (e.g. packaged as a module).
    try:
        import pptx2md
        return pptx2md
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Could not locate the pptx2md converter. Pass --pptx2md-dir "
            "pointing at the pptx2md skill directory."
        ) from exc


# ----------------------------------------------------------------------------
# Markdown → chunk parsing (contract from pptx2md/references/styling.md)
# ----------------------------------------------------------------------------
_SLIDE_RE = re.compile(r"<!--\s*Slide\s+(\d+)\s*-->")
_TITLE_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _parse_markdown(text: str, source_file: str, lang: str) -> list[Chunk]:
    """Split markdown into per-slide chunks per the styling.md contract."""
    parts = _SLIDE_RE.split(text)
    # parts[0] = file header; then alternating (slide_no, content)
    chunks: list[Chunk] = []
    if len(parts) < 3:
        # No slide anchors found — treat the whole doc as a single chunk.
        content = parts[0]
        title_m = _TITLE_RE.search(content)
        chunks.append(_make_chunk(0, content, source_file, lang, title_m))
        return chunks

    for i in range(1, len(parts), 2):
        no = int(parts[i])
        content = parts[i + 1]
        title_m = _TITLE_RE.search(content)
        chunks.append(_make_chunk(no, content, source_file, lang, title_m))
    return chunks


def _make_chunk(no: int, content: str, source_file: str, lang: str,
                title_m: re.Match[str] | None) -> Chunk:
    title = title_m.group(1).strip() if title_m else ""
    # Per the styling.md contract, `content` is the slide body text. We strip
    # only the (1) title `## ` line and (2) inter-slide `---` separators.
    # `![图](assets/..)` refs are DELIBERATELY kept inline (matching the
    # reference implementation) and also surfaced as the `images` field for
    # structured indexing.
    body = content
    if title_m:
        body = body.replace(title_m.group(0), "", 1)
    lines = [ln for ln in body.splitlines() if ln.strip() != "---"]
    body = "\n".join(lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    images = _IMG_RE.findall(content)
    return {
        "source_file": source_file,
        "slide_no": no,
        "title": title,
        "content": body,
        "images": images,
        "has_diagram": any("slide-" in img for img in images),
        "lang": lang,
    }


def _resolve_images(chunks: list[Chunk], base_url: str | None) -> None:
    if not base_url:
        return
    base = base_url.rstrip("/") + "/"
    for ch in chunks:
        ch["images"] = [base + img.lstrip("/") for img in ch["images"]]


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
def build(input_path: str, out_path: str, *, pptx2md_dir: str | None = None,
          base_url: str | None = None, lang: str = "zh",
          asset_dir: str = "assets") -> int:
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(input_p)

    if input_p.suffix.lower() == ".pptx":
        # Delegate conversion to the pptx2md skill.
        mod = _load_pptx2md(pptx2md_dir)
        md_path, _by_page = mod.convert(str(input_p), asset_dir=asset_dir)
        md_path = Path(md_path)
        source_file = input_p.stem
    else:
        md_path = input_p
        source_file = input_p.stem
        # Recover the original pptx stem if the doc carries `> 源文件：…`
        text0 = md_path.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(.+)$", text0, re.MULTILINE)
        if m:
            source_file = m.group(1).strip()

    text = md_path.read_text(encoding="utf-8")
    chunks = _parse_markdown(text, source_file, lang)
    _resolve_images(chunks, base_url)

    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with out_p.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    diagrams = sum(1 for ch in chunks if ch["has_diagram"])
    print(f"source : {source_file}")
    print(f"md     : {md_path}")
    print(f"chunks : {len(chunks)} slides -> {out_p}")
    print(f"diagrams: {diagrams} slide(s) with diagram")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Convert a .pptx (or .md) into KB-ready JSONL chunks.")
    ap.add_argument("input", help="Input .pptx or already-converted .md")
    ap.add_argument("--out", required=True, help="Output .jsonl path")
    ap.add_argument("--pptx2md-dir", default=None,
                    help="Directory of the pptx2md skill (auto-detected)")
    ap.add_argument("--base-url", default=None,
                    help="Prefix to turn relative assets/ paths into absolute URLs")
    ap.add_argument("--lang", default="zh", help="Language tag (default zh)")
    ap.add_argument("--asset-dir", default="assets",
                    help="Asset folder name when converting a .pptx (default assets)")
    args = ap.parse_args(argv[1:])

    try:
        return build(args.input, args.out, pptx2md_dir=args.pptx2md_dir,
                     base_url=args.base_url, lang=args.lang,
                     asset_dir=args.asset_dir)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

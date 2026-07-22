#!/usr/bin/env python3
"""
Convert every .docx file in ./cache into Markdown under ./outputs.

For each source document ``<name>.docx`` the script writes:

    outputs/<name>/<name>.md
    outputs/<name>/assets/      # extracted images

Usage (run from this directory):
    python run_all.py

Dependencies:
    pip install python-docx Pillow

Note: On Windows, EMF/WMF vector diagrams are rendered to PNG via the built-in
GDI API (no extra package). On other platforms, install ``pillow-emf`` (EMF)
and/or ``PyMuPDF`` so vector diagrams still convert to viewable PNG.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVERTER = HERE.parent / "scripts" / "docx2md.py"
CACHE_DIR = HERE / "cache"
OUTPUT_DIR = HERE / "outputs"


def _load_converter():
    """Import the converter module from scripts/docx2md.py."""
    if not CONVERTER.exists():
        sys.exit(f"Converter not found: {CONVERTER}")
    spec = importlib.util.spec_from_file_location("docx2md", CONVERTER)
    if spec is None or spec.loader is None:
        sys.exit(f"Failed to load converter: {CONVERTER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    converter = _load_converter()

    docx_files = sorted(CACHE_DIR.glob("*.docx"))
    if not docx_files:
        print(f"No .docx files found in {CACHE_DIR}", file=sys.stderr)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for docx in docx_files:
        stem = docx.stem
        out_md = OUTPUT_DIR / stem / f"{stem}.md"
        out_asset = OUTPUT_DIR / stem / "assets"
        try:
            md_path, _ = converter.convert(docx, out_md, asset_dir=out_asset)
            print(f"✅ {docx.name} -> {md_path}", file=sys.stderr)
            results.append(
                {
                    "source": docx.name,
                    "md_path": str(md_path),
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"❌ {docx.name} failed: {exc}", file=sys.stderr)
            results.append({"source": docx.name, "error": str(exc)})


if __name__ == "__main__":
    main()

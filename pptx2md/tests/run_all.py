#!/usr/bin/env python3
"""
Convert every .pptx file in ./cache into Markdown under ./outputs.

For each source presentation ``<name>.pptx`` the script writes:

    outputs/<name>/<name>.md
    outputs/<name>/assets/      # extracted images

Usage (run from this directory):
    python run_all.py

Dependencies:
    pip install python-pptx Pillow
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVERTER = HERE.parent / "scripts" / "pptx2md.py"
CACHE_DIR = HERE / "cache"
OUTPUT_DIR = HERE / "outputs"


def _load_converter():
    """Import the converter module from scripts/pptx2md.py."""
    if not CONVERTER.exists():
        sys.exit(f"Converter not found: {CONVERTER}")
    spec = importlib.util.spec_from_file_location("pptx2md", CONVERTER)
    if spec is None or spec.loader is None:
        sys.exit(f"Failed to load converter: {CONVERTER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    converter = _load_converter()

    pptx_files = sorted(CACHE_DIR.glob("*.pptx"))
    if not pptx_files:
        print(f"No .pptx files found in {CACHE_DIR}", file=sys.stderr)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for pptx in pptx_files:
        stem = pptx.stem
        out_md = OUTPUT_DIR / stem / f"{stem}.md"
        out_asset = OUTPUT_DIR / stem / "assets"
        try:
            md_path, image_index_by_page = converter.convert(
                str(pptx), str(out_md), asset_dir=str(out_asset)
            )
            print(f"✅ {pptx.name} -> {md_path}", file=sys.stderr)
            results.append(
                {
                    "source": pptx.name,
                    "md_path": str(md_path),
                    "image_index_by_page": image_index_by_page,
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"❌ {pptx.name} failed: {exc}", file=sys.stderr)
            results.append({"source": pptx.name, "error": str(exc)})

    # Machine-readable summary on stdout
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

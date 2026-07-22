#!/usr/bin/env python3
"""tests/run_consolidate.py — consolidate the IR JSONs in tests/cache.

Discovers every ``*.ir.json`` file under ``tests/cache`` and merges them into a
single consolidated ``ParsedStatement`` written to ``tests/outputs``.

The actual merge logic lives in ``scripts/consolidate.py`` (de-dup by ``txn_id``,
provenance tracking, IR version gate); this script is a thin convenience wrapper
that wires up the cache/inputs and outputs directories so the consolidation can
be exercised as a test.

Usage:
    python tests/run_consolidate.py
    python tests/run_consolidate.py --cache tests/cache --out tests/outputs/consolidated.ir.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the sibling scripts/ importable regardless of the cwd.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # bank-ir-consolidate/
sys.path.insert(0, str(ROOT / "scripts"))

from consolidate import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    DEFAULT_MIN_IR_VERSION,
    consolidate_statements,
)
from _parser_loader import load_parser_modules  # noqa: E402  # pyright: ignore[reportMissingImports]
from render_md import render as render_md  # noqa: E402  # pyright: ignore[reportMissingImports]

DEFAULT_CACHE = HERE / "cache"
DEFAULT_OUTPUT = HERE / "outputs" / "consolidated.ir.json"
DEFAULT_OUTPUT_MD = HERE / "outputs" / "consolidated.md"


def collect_inputs(cache_dir: Path) -> list[str]:
    """Return sorted *.ir.json paths, skipping any already-consolidated output."""
    if not cache_dir.is_dir():
        sys.exit(f"[error] cache directory not found: {cache_dir}")
    paths = sorted(str(p) for p in cache_dir.glob("*.ir.json"))
    if not paths:
        sys.exit(f"[error] no *.ir.json files found in {cache_dir}")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description="Consolidate IR JSONs from tests/cache.")
    _ = ap.add_argument("--cache", default=str(DEFAULT_CACHE), help="Directory of input *.ir.json files")
    _ = ap.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output consolidated IR JSON path")
    _ = ap.add_argument("--out-md", default=str(DEFAULT_OUTPUT_MD), help="Output consolidated markdown path")
    _ = ap.add_argument("--parser-dir", default=None, help="Path to sg-bank-to-md skill dir")
    _ = ap.add_argument("--min-ir-version", default=DEFAULT_MIN_IR_VERSION, help="Minimum accepted ir_version")
    _ = ap.add_argument("--no-dedup", action="store_true", help="Disable txn_id de-duplication")
    _ = ap.add_argument("--no-mask", action="store_true", help="Disable masking of IDs/names in markdown")
    _ = ap.add_argument("--indent", type=int, default=2, help="JSON indent")
    args = ap.parse_args()

    inputs = collect_inputs(Path(args.cache))
    pm = load_parser_modules(args.parser_dir)
    ir = pm.ir_schema

    # IR version gate (mirrors scripts/consolidate.py main).
    def _version_ge(a: str, b: str) -> bool:
        def _parts(v: str) -> list[int]:
            return [int(x) for x in v.split(".") if x.isdigit()]

        return _parts(a) >= _parts(b)

    stmts_with_paths: list[tuple[str, object]] = []
    for path in inputs:
        text = Path(path).read_text(encoding="utf-8")
        try:
            stmt = ir.from_json(text)
        except ValueError as e:
            sys.exit(f"[error] {path}: {e}")
        if not _version_ge(stmt.ir_version, args.min_ir_version):
            sys.exit(f"[error] {path}: ir_version {stmt.ir_version!r} < required {args.min_ir_version!r}")
        stmts_with_paths.append((str(path), stmt))

    consolidated, total_in, deduped = consolidate_statements(
        stmts_with_paths, ir, do_dedup=not args.no_dedup  # type: ignore[arg-type]
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _ = out.write_text(consolidated.to_json(indent=args.indent), encoding="utf-8")

    # Render the consolidated IR to a human-readable markdown summary.
    md = render_md(consolidated, pm.helpers, pm.common, do_mask=not args.no_mask)
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _ = out_md.write_text(md, encoding="utf-8")

    total_out = total_in - deduped
    print(f"Consolidated {len(inputs)} input file(s) -> {out}")
    print(f"Rendered markdown summary -> {out_md}")
    for p in inputs:
        print(f"  + {Path(p).name}")
    print(
        f"  inputs={len(stmts_with_paths)} accounts={len(consolidated.accounts)} "+
        f"txns_in={total_in} txns_out={total_out} deduped={deduped}"
    )


if __name__ == "__main__":
    main()

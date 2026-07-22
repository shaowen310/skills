#!/usr/bin/env python3
"""consolidate.py — merge multiple sg-bank-to-md IR JSON files.

Reads N ``*.ir.json`` (``ParsedStatement``) files, merges accounts grouped by
``(institution, account_no, name)``, de-duplicates transactions by ``txn_id``,
and writes a single consolidated ``ParsedStatement`` as ``consolidated.ir.json``.

Usage:
    python consolidate.py a.ir.json b.ir.json -o consolidated.ir.json
    python consolidate.py *.ir.json -o consolidated.ir.json --min-ir-version 2026.3
"""
from __future__ import annotations

import argparse
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running as a standalone script from scripts/ or the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _parser_loader import load_parser_modules  # noqa: E402

VERSION = "0.1.0"
DEFAULT_MIN_IR_VERSION = "2026.3"


def _version_ge(a: str, b: str) -> bool:
    def _parts(v: str) -> list[int]:
        return [int(x) for x in v.split(".") if x.isdigit()]

    return _parts(a) >= _parts(b)


def _merge_fd(accs: list[Any]) -> list[Any] | None:
    """Concatenate fd_records across statements, de-dup by deposit_no."""
    recs: list[Any] = []
    seen: set[str] = set()
    for acc in accs:
        for r in acc.fd_records or []:
            if r.deposit_no and r.deposit_no in seen:
                continue
            if r.deposit_no:
                seen.add(r.deposit_no)
            recs.append(r)
    return recs or None


def _merge_inv(accs: list[Any]) -> list[Any] | None:
    """Concatenate investment_holdings across statements, de-dup by name."""
    recs: list[Any] = []
    seen: set[str] = set()
    for acc in accs:
        for h in acc.investment_holdings or []:
            if h.name and h.name in seen:
                continue
            if h.name:
                seen.add(h.name)
            recs.append(h)
    return recs or None


def consolidate_statements(
    stmts_with_paths: list[tuple[str, Any]],
    ir: types.ModuleType,
    do_dedup: bool,
) -> tuple[Any, int, int]:
    """``stmts_with_paths`` is a list of (path, ParsedStatement)."""
    groups: dict[tuple[str, str, str], list[Any]] = {}
    sources: list[dict[str, Any]] = []
    total_txns_in = 0

    for src_path, stmt in stmts_with_paths:
        meta = stmt.statement_meta
        sources.append(
            {
                "source_file": stmt.source_file or src_path,
                "parser": f"{stmt.parser.name} {stmt.parser.version}".strip(),
                "parsed_at": stmt.parsed_at,
                "ir_version": stmt.ir_version,
                "institution": meta.institution,
                "n_accounts": len(stmt.accounts),
                "n_txns": sum(len(a.transactions) for a in stmt.accounts),
            }
        )
        total_txns_in += sum(len(a.transactions) for a in stmt.accounts)
        for acc in stmt.accounts:
            key = (meta.institution, acc.account_no, acc.name)
            groups.setdefault(key, []).append(acc)

    merged_accounts = []
    deduped = 0
    for (_inst, _no, _name), accs in groups.items():
        base = accs[0]
        txns = []
        seen: set[str] = set()
        for acc in accs:
            for t in acc.transactions:
                if do_dedup and t.txn_id:
                    if t.txn_id in seen:
                        deduped += 1
                        continue
                    seen.add(t.txn_id)
                txns.append(t)
        def _txn_sort_key(t: Any) -> tuple[Any, Any]:
            return (t.posted_date, t.txn_id)

        txns.sort(key=_txn_sort_key)

        extras = dict(base.extras or {})
        extras["_source_institution"] = _inst

        merged_accounts.append(
            ir.Account(
                name=base.name,
                account_no=base.account_no,
                account_type=base.account_type,
                currency=base.currency,
                account_holder=base.account_holder,
                opening_balance=base.opening_balance,
                closing_balance=base.closing_balance,
                balance=base.balance,
                balance_sgd=base.balance_sgd,
                transactions=txns,
                fd_records=_merge_fd(accs),
                investment_holdings=_merge_inv(accs),
                extras=extras,
            )
        )

    periods_from = [
        s.statement_meta.period_from
        for _, s in stmts_with_paths
        if s.statement_meta.period_from
    ]
    periods_to = [
        s.statement_meta.period_to
        for _, s in stmts_with_paths
        if s.statement_meta.period_to
    ]
    meta = ir.StatementMeta(
        institution="",
        institution_code=None,
        account_holder=None,
        currency="",
        period_from=min(periods_from) if periods_from else None,
        period_to=max(periods_to) if periods_to else None,
    )
    min_ir = min((s.ir_version for _, s in stmts_with_paths), default=DEFAULT_MIN_IR_VERSION)
    warnings: list[str] = []
    for src_path, stmt in stmts_with_paths:
        for w in stmt.warnings:
            warnings.append(f"{stmt.source_file or src_path}: {w}")

    consolidated = ir.ParsedStatement(
        ir_version=min_ir,
        parsed_at=datetime.now(timezone.utc).isoformat(),
        parser=ir.ParserInfo(name="bank-ir-consolidate", version=VERSION),
        source_file="",
        statement_meta=meta,
        accounts=merged_accounts,
        warnings=warnings,
        extras={
            "consolidation": {
                "sources": sources,
                "deduped": deduped,
                "n_inputs": len(stmts_with_paths),
            }
        },
    )
    return consolidated, total_txns_in, deduped


def main() -> None:
    ap = argparse.ArgumentParser(description="Consolidate sg-bank-to-md IR JSON files.")
    _ = ap.add_argument("inputs", nargs="+", help="Input *.ir.json files")
    _ = ap.add_argument("-o", "--out", default="consolidated.ir.json", help="Output IR JSON path")
    _ = ap.add_argument("--parser-dir", default=None, help="Path to sg-bank-to-md skill dir")
    _ = ap.add_argument("--min-ir-version", default=DEFAULT_MIN_IR_VERSION, help="Minimum accepted ir_version")
    _ = ap.add_argument("--no-dedup", action="store_true", help="Disable txn_id de-duplication")
    _ = ap.add_argument("--indent", type=int, default=2, help="JSON indent")
    args = ap.parse_args()

    pm = load_parser_modules(args.parser_dir)
    ir = pm.ir_schema

    stmts_with_paths: list[tuple[str, Any]] = []
    for path in args.inputs:
        text = Path(path).read_text(encoding="utf-8")
        try:
            stmt = ir.from_json(text)
        except ValueError as e:
            sys.exit(f"[error] {path}: {e}")
        if not _version_ge(stmt.ir_version, args.min_ir_version):
            sys.exit(
                f"[error] {path}: ir_version {stmt.ir_version!r} < required "+
                f"{args.min_ir_version!r}"
            )
        stmts_with_paths.append((str(path), stmt))

    consolidated, total_in, deduped = consolidate_statements(
        stmts_with_paths, ir, do_dedup=not args.no_dedup
    )
    out = Path(args.out)
    _ = out.write_text(consolidated.to_json(indent=args.indent), encoding="utf-8")
    total_out = total_in - deduped
    print(f"Wrote {out}")
    print(
        f"  inputs={len(stmts_with_paths)} accounts={len(consolidated.accounts)} "+
        f"txns_in={total_in} txns_out={total_out} deduped={deduped}"
    )


if __name__ == "__main__":
    main()

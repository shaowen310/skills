#!/usr/bin/env python3
"""render_md.py — render a consolidated (or any) IR JSON into markdown.

Reads a ``ParsedStatement`` IR JSON (typically the output of ``consolidate.py``)
and writes a human-readable, cross-bank markdown summary with masking applied
(consistent with ``sg-bank-to-md``).

Usage:
    python render_md.py consolidated.ir.json -o consolidated.md
    python render_md.py consolidated.ir.json -o consolidated.md --no-mask
"""
from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path
from typing import Any

# Allow running as a standalone script from scripts/ or the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _parser_loader import load_parser_modules  # noqa: E402


def _money(v: float | None, currency: str = "") -> str:
    if v is None:
        return "—"
    try:
        return f"{v:,.2f} {currency}".strip()
    except Exception:  # pragma: no cover - defensive
        return str(v)


def render(
    stmt: Any,
    helpers: types.ModuleType,
    common: types.ModuleType,
    do_mask: bool,
) -> str:
    mask_desc = helpers.md_masked_description
    mask_id = common.mask_id
    meta = stmt.statement_meta
    lines: list[str] = []

    lines.append("# Consolidated Bank Statement")
    lines.append("")
    consolidation = (stmt.extras or {}).get("consolidation", {})
    sources = consolidation.get("sources", [])
    lines.append(f"- **Statements consolidated**: {len(sources)}")
    institutions = sorted({s.get("institution") for s in sources if s.get("institution")})
    if institutions:
        lines.append(f"- **Banks**: {', '.join(institutions)}")
    period = " → ".join(filter(None, [meta.period_from or "", meta.period_to or ""]))
    if period:
        lines.append(f"- **Period**: {period}")
    lines.append("")

    # --- Net Position ---
    lines.append("## Net Position")
    lines.append("")
    sgd = sum(a.balance_sgd for a in stmt.accounts if a.balance_sgd is not None)
    lines.append(f"- **Total (SGD, where available)**: {_money(sgd, 'SGD')}")
    per_ccy: dict[str, float] = {}
    for a in stmt.accounts:
        if a.balance is not None and a.currency:
            per_ccy[a.currency] = per_ccy.get(a.currency, 0.0) + a.balance
    if per_ccy:
        lines.append("")
        lines.append("Per-currency balances:")
        for ccy in sorted(per_ccy):
            lines.append(f"- {ccy}: {_money(per_ccy[ccy], ccy)}")
    lines.append("")

    # --- Group accounts by institution ---
    by_inst: dict[str, list[Any]] = {}
    for a in stmt.accounts:
        inst = (a.extras or {}).get("_source_institution") or "—"
        by_inst.setdefault(inst, []).append(a)

    for inst in sorted(by_inst):
        heading = inst if inst != "—" else "Other accounts"
        lines.append(f"## {heading}")
        lines.append("")
        for acc in by_inst[inst]:
            title = acc.name
            suffix = f"({acc.currency})"
            if acc.currency and not title.strip().endswith(suffix):
                title = f"{title} {suffix}"
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"- **Account**: {mask_id(acc.account_no, do_mask=do_mask)}")
            lines.append(f"- **Type**: {acc.account_type}")
            if acc.opening_balance is not None or acc.closing_balance is not None:
                lines.append(
                    f"- **Opening**: {_money(acc.opening_balance, acc.currency)}  "+
                    f"**Closing**: {_money(acc.closing_balance, acc.currency)}"
                )
            elif acc.balance is not None:
                lines.append(f"- **Balance**: {_money(acc.balance, acc.currency)}")
            if acc.balance_sgd is not None:
                lines.append(f"- **Balance (SGD)**: {_money(acc.balance_sgd, 'SGD')}")
            lines.append("")

            if acc.transactions:
                lines.append("| Date | Description | Withdrawal | Deposit | Balance |")
                lines.append("| --- | --- | ---: | ---: | ---: |")
                for t in acc.transactions:
                    desc = mask_desc(t.description, do_mask=do_mask) if do_mask else t.description
                    if t.amount < 0:
                        wd, dp = _money(abs(t.amount), t.currency), ""
                    else:
                        wd, dp = "", _money(t.amount, t.currency)
                    lines.append(
                        f"| {t.posted_date} | {desc} | {wd} | {dp} | "+
                        f"{_money(t.balance_after, t.currency)} |"
                    )
                lines.append("")

            if acc.fd_records:
                lines.append("#### Fixed Deposits")
                lines.append("")
                lines.append("| Deposit No | Value Date | Maturity | Rate | Principal | Interest |")
                lines.append("| --- | --- | --- | --- | ---: | ---: |")
                for r in acc.fd_records:
                    rate = (
                        r.raw_interest_rate
                        if r.raw_interest_rate
                        else (f"{r.interest_rate * 100:.3f}%" if r.interest_rate is not None else "—")
                    )
                    lines.append(
                        f"| {mask_id(r.deposit_no, do_mask=do_mask)} | "+
                        f"{r.value_date or '—'} | {r.maturity_date or '—'} | {rate} | "+
                        f"{_money(r.principal, r.currency)} | {_money(r.interest_amount, r.currency)} |"
                    )
                lines.append("")

            if acc.investment_holdings:
                lines.append("#### Investments")
                lines.append("")
                lines.append("| Name | Units | Currency | Unit Price | Valuation | Cost | Unrealised P/L |")
                lines.append("| --- | ---: | --- | --- | --- | --- | --- |")
                for h in acc.investment_holdings:
                    lines.append(
                        f"| {h.name} | {h.units or '—'} | {h.currency or '—'} | "+
                        f"{h.unit_price or '—'} | {h.valuation or '—'} | "+
                        f"{h.cost or '—'} | {h.unrealised_pl or '—'} |"
                    )
                lines.append("")

        lines.append("")

    # --- Warnings ---
    if stmt.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in stmt.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Auto-generated by bank-ir-consolidate from consolidated IR ({stmt.ir_version})._")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a bank IR JSON to markdown.")
    _ = ap.add_argument("input", help="Input *.ir.json file")
    _ = ap.add_argument("-o", "--out", default="consolidated.md", help="Output markdown path")
    _ = ap.add_argument("--parser-dir", default=None, help="Path to sg-bank-to-md skill dir")
    _ = ap.add_argument("--no-mask", action="store_true", help="Disable masking of IDs/names")
    args = ap.parse_args()

    pm = load_parser_modules(args.parser_dir)
    text = Path(args.input).read_text(encoding="utf-8")
    stmt = pm.ir_schema.from_json(text)
    md = render(stmt, pm.helpers, pm.common, do_mask=not args.no_mask)
    out = Path(args.out)
    _ = out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

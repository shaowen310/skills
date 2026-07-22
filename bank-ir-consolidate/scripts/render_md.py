#!/usr/bin/env python3
"""render_md.py — render a consolidated (or any) IR JSON into markdown.

Reads a ``ParsedStatement`` IR JSON (typically the output of ``consolidate.py``),
builds a render-oriented ``RenderModel`` and writes a human-readable, cross-bank
markdown summary with masking applied (consistent with ``sg-bank-to-md``).

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
from render_model import build_render_model, TXN_SECTION_ORDER  # noqa: E402


def _money(v: float | None, currency: str = "") -> str:
    if v is None:
        return "—"
    try:
        return f"{v:,.2f} {currency}".strip()
    except Exception:  # pragma: no cover - defensive
        return str(v)


def _account_institution(acc: Any) -> str:
    """Resolve the owning institution from the account's institution field."""
    return acc.institution or "—"


def render(
    model: Any,
    helpers: types.ModuleType,
    common: types.ModuleType,
    do_mask: bool,
) -> str:
    mask_desc = helpers.md_masked_description
    mask_id = common.mask_id
    lines: list[str] = []

    # --- Header / meta (from model) ---
    lines.append("# Consolidated Bank Statement")
    lines.append("")
    lines.append(f"- **Statements consolidated**: {len(model.sources)}")
    if model.institutions:
        lines.append(f"- **Banks**: {', '.join(model.institutions)}")
    period = " → ".join(filter(None, [model.period_from or "", model.period_to or ""]))
    if period:
        lines.append(f"- **Period**: {period}")
    lines.append("")

    # --- Net Position (from model) ---
    lines.append("## Net Position")
    lines.append("")
    lines.append(f"- **Total (SGD, where available)**: {_money(model.net_sgd, 'SGD')}")
    # Skip zero-balance currencies so the table only shows meaningful rows.
    non_zero_ccy = {ccy: bal for ccy, bal in model.per_ccy_balances.items() if bal}
    if non_zero_ccy:
        lines.append("")
        lines.append("Per-currency balances:")
        for ccy in sorted(non_zero_ccy):
            lines.append(f"- {ccy}: {_money(non_zero_ccy[ccy])}")
    lines.append("")

    # --- Combined transactions: one section per account type, one table per currency ---
    def _render_ccy_section(tables: list[Any], heading: str) -> None:
        lines.append(f"## {heading} (by Currency)")
        lines.append("")
        for ct in tables:
            lines.append(f"### {ct.currency}")
            lines.append("")
            lines.append("| Date | Bank | Account | Description | Withdrawal | Deposit | Balance |")
            lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
            for r in ct.rows:
                acct = mask_id(r.account, do_mask=do_mask)
                desc = mask_desc(r.description, do_mask=do_mask) if do_mask else r.description
                wd = f"{r.withdrawal:,.2f}" if r.withdrawal is not None else ""
                dp = f"{r.deposit:,.2f}" if r.deposit is not None else ""
                bal = _money(r.balance_after)  # currency omitted; table is grouped by currency (### header)
                lines.append(
                    f"| {r.date} | {r.bank} | {acct} | {desc} | {wd} | {dp} | {bal} |"
                )
            lines.append(
                f"| | | | **Total** | {ct.total_withdrawal:,.2f} | "+
                f"{ct.total_deposit:,.2f} | |"
            )
            lines.append("")

    covered: set[str] = set()
    for atype, heading in TXN_SECTION_ORDER:
        tables = model.txn_tables_by_type.get(atype)
        if tables:
            _render_ccy_section(tables, heading)
            covered.add(atype)
    # Fallback for any transaction-bearing type not in the canonical order list.
    for atype in sorted(model.txn_tables_by_type):
        if atype in covered:
            continue
        heading = f"{atype.replace('_', ' ').title()} Transactions"
        _render_ccy_section(model.txn_tables_by_type[atype], heading)

    # --- Per-bank drill-down ---
    by_inst: dict[str, list[Any]] = {}
    for a in model.accounts:
        inst = _account_institution(a)
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
    if model.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in model.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Auto-generated by bank-ir-consolidate from consolidated IR ({model.ir_version})._")
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
    md = render(build_render_model(stmt), pm.helpers, pm.common, do_mask=not args.no_mask)
    out = Path(args.out)
    _ = out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

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


def _get_balance(acc: Any) -> float:
    """Get the effective balance of an account.

    Falls back through:
    1. ``acc.balance``
    2. ``acc.closing_balance``
    3. Last transaction's ``balance_after`` (common for OCBC accounts)
    4. FD record principal (for OCBC TIME DEPOSITS-style accounts)
    5. 0.0
    """
    if acc.balance is not None:
        return acc.balance
    if acc.closing_balance is not None:
        return acc.closing_balance
    if acc.transactions:
        last_ba = None
        for t in acc.transactions:
            if t.balance_after is not None:
                last_ba = t.balance_after
        if last_ba is not None:
            return last_ba
    if acc.fd_records:
        return sum(getattr(r, "principal", 0) or 0 for r in acc.fd_records)
    return 0.0


def _sgd_equiv(balance: float, currency: str, fx_rates: dict[str, float]) -> float | None:
    """Compute SGD equivalent of *balance* in *currency* using the given FX rates."""
    rate = fx_rates.get(currency)
    if rate is None:
        return None
    return balance * rate


# Net Position display types: (account_type, section_heading) in display order.
_NET_POSITION_TYPES: list[tuple[str, str]] = [
    ("current", "Current Accounts"),
    ("fixed_deposit", "Fixed Deposits"),
    ("srs", "SRS"),
    ("credit_card", "Credit Cards"),
    ("ewallet", "E-wallets"),
    ("unit_trust", "Unit Trusts"),
    ("unknown", "Other Accounts"),
]

# FX rate display order (for the FX rate table).
_FX_RATE_CCY_ORDER: list[str] = ["SGD", "USD", "JPY", "CNY"]


def _render_net_position(model: Any, mask_id: Any, do_mask: bool) -> list[str]:
    lines: list[str] = []
    lines.append("## Net Position")
    lines.append("")

    period_to = model.period_to or "—"
    lines.append(f"### FX Rate Table (as of {period_to})")
    lines.append("")
    lines.append(
        "*Mid-market rates from ValutaFX (last business day before "
        + f"{period_to} if it falls on a weekend). "
        + "SGD per 1 unit of foreign currency.*"
    )
    lines.append("")
    lines.append("| Currency | Mid-market (1 SGD =) | SGD per 1 unit |")
    lines.append("| --- | --- | ---: |")
    # Look up inverse rates (1 SGD = X CCY) from the model's fx_rates.
    for ccy in _FX_RATE_CCY_ORDER:
        rate = model.fx_rates.get(ccy)
        if rate is None or ccy == "SGD":
            inv = "—"
            fwd = "1.0000"
        else:
            inv = f"{1.0 / rate:.4f}"
            fwd = f"{rate:.4f}"
        lines.append(f"| {ccy} | {inv} | {fwd} |")
    lines.append("")

    # Group accounts by type.
    by_type: dict[str, list[Any]] = {}
    for a in model.accounts:
        by_type.setdefault(a.account_type, []).append(a)

    grand_total_sgd = 0.0

    for atype, heading in _NET_POSITION_TYPES:
        accounts = by_type.get(atype)
        if not accounts:
            continue

        lines.append(f"### {heading}")
        lines.append("")

        if atype == "fixed_deposit":
            lines.append(
                "| Bank | Account | Currency | Principal | Balance (SGD) |"
            )
            lines.append(
                "| --- | --- | --- | ---: | ---: |"
            )
        else:
            lines.append(
                "| Bank | Account | Currency | Balance | Balance (SGD) |"
            )
            lines.append(
                "| --- | --- | --- | ---: | ---: |"
            )

        type_total_sgd = 0.0
        zero_bal_wallets: list[str] = []

        for acc in sorted(accounts, key=lambda a: (a.institution or "", a.account_no or "")):
            bal = _get_balance(acc)

            if bal == 0:
                # Collect zero-balance wallets for a footnote instead of cluttering the table.
                inst = _account_institution(acc)
                ccy = acc.currency or "—"
                zero_bal_wallets.append(f"{inst} {ccy}")
                continue

            sgd_val = _sgd_equiv(bal, acc.currency or "SGD", model.fx_rates)
            if sgd_val is None:
                sgd_equiv_display = "—"
                row_sgd = 0.0
            else:
                sgd_equiv_display = f"{sgd_val:,.2f}"
                row_sgd = sgd_val
            acct_id = mask_id(acc.account_no, do_mask=do_mask)
            inst = _account_institution(acc)
            ccy = acc.currency or "—"
            bal_str = f"{bal:,.2f}"

            if atype == "fixed_deposit":
                lines.append(
                    f"| {inst} | {acct_id} | {ccy} | {bal_str} | {sgd_equiv_display} |"
                )
            else:
                lines.append(
                    f"| {inst} | {acct_id} | {ccy} | {bal_str} | {sgd_equiv_display} |"
                )
            type_total_sgd += row_sgd

        lines.append(
            f"| | **Subtotal** | | | **{type_total_sgd:,.2f}** |"
        )
        lines.append("")

        if zero_bal_wallets:
            grouped: dict[str, list[str]] = {}
            for entry in zero_bal_wallets:
                inst, ccy = entry.split(" ", 1)
                grouped.setdefault(inst, []).append(ccy)
            notes = []
            for inst in sorted(grouped):
                notes.append(f"{inst} ({', '.join(sorted(grouped[inst]))})")
            lines.append(f"  _Zero-balance accounts: {'; '.join(notes)}._")

        grand_total_sgd += type_total_sgd

    # Grand total line.
    lines.append(f"### Grand Total")
    lines.append("")
    lines.append(f"**{grand_total_sgd:,.2f} SGD**")
    lines.append("")

    return lines


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
    lines.extend(_render_net_position(model, mask_id, do_mask))

    # --- Combined transactions: one section per account type, one table per currency ---
    def _render_ccy_section(tables: list[Any], heading: str) -> None:
        lines.append(f"## {heading} (by Currency)")
        lines.append("")
        for ct in tables:
            lines.append(f"### {ct.currency}")
            lines.append("")
            lines.append("| Date | Bank | Account | Description | Withdrawal | Deposit | Net Deposit |")
            lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
            for r in ct.rows:
                # Skip zero-amount transactions (no withdrawal and no deposit).
                if not (r.withdrawal or 0) and not (r.deposit or 0):
                    continue
                acct = mask_id(r.account, do_mask=do_mask)
                desc = mask_desc(r.description, do_mask=do_mask) if do_mask else r.description
                wd = f"{r.withdrawal:,.2f}" if r.withdrawal is not None else ""
                dp = f"{r.deposit:,.2f}" if r.deposit is not None else ""
                # Net Deposits: running net (deposit - withdrawal) within the currency table.
                # The per-account balance_after is meaningless once rows from multiple
                # accounts are interleaved, so the consolidated view uses this instead.
                netd = _money(r.net_deposits)  # currency omitted; table is grouped by currency (### header)
                lines.append(
                    f"| {r.date} | {r.bank} | {acct} | {desc} | {wd} | {dp} | {netd} |"
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
                    if t.amount == 0:
                        continue  # skip zero-amount transactions
                    # Skip internal "PAYMENT BY INTERNET" lines (negative amount).
                    if t.amount < 0 and "PAYMENT BY INTERNET" in (t.description or "").upper():
                        continue
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

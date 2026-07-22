"""render_model.py — flatten a ParsedStatement into a render-oriented model.

Keeps ``consolidated.ir.json`` as the authoritative ``ParsedStatement`` (no data
duplication) while giving the markdown renderer a clean, render-ready structure.

Masking is intentionally NOT applied here — descriptions/account numbers stay
raw so the data remains unmasked; masking happens at render time.

FX rates (``DEFAULT_FX_RATES``) are **not embedded in the statement data**;
they are sourced externally (e.g. ValutaFX historical mid-market rates) and
used to estimate SGD-equivalent values for non-SGD accounts in the Net Position
section. Override by passing a custom ``fx_rates`` dict on construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# FX rates — SGD per 1 unit of foreign currency, mid-market as of period_to
# (last business day: 2026-07-17 since 2026-07-18 is a Saturday).
# Source: ValutaFX historical rates; 1 SGD = 0.7745 USD, 125.82 JPY, 5.2473 CNY.
DEFAULT_FX_RATES: dict[str, float] = {
    "SGD": 1.0,
    "USD": 1.2912,     # 1 / 0.7745
    "JPY": 0.0079498,  # 1 / 125.82
    "CNY": 0.19057,    # 1 / 5.2473
}

# Account types that carry FD/investment records instead of spend transactions.
_NON_TXN_ACCOUNTS = ("fixed_deposit", "unit_trust")

# Canonical order of combined transaction sections. Each transaction-bearing
# account_type gets its own section so credit cards / e-wallets / SRS, etc. are
# not folded into "Current Account Transactions".
TXN_SECTION_ORDER: list[tuple[str, str]] = [
    ("current", "Current Account Transactions"),
    ("credit_card", "Credit Card Transactions"),
    ("ewallet", "E-wallet Transactions"),
    ("srs", "SRS Transactions"),
    ("unknown", "Other Account Transactions"),
]


@dataclass
class TxnRow:
    date: str
    bank: str
    account: str            # raw account_no (mask at render)
    description: str        # raw description (mask at render)
    withdrawal: float | None
    deposit: float | None
    balance_after: float | None
    net_deposits: float | None = None  # running net (deposit - withdrawal) within a currency table
    txn_id: str = ""
    currency: str = ""


@dataclass
class CurrencyTable:
    currency: str
    rows: list[TxnRow] = field(default_factory=list)

    @property
    def total_withdrawal(self) -> float:
        return sum((r.withdrawal or 0.0) for r in self.rows)

    @property
    def total_deposit(self) -> float:
        return sum((r.deposit or 0.0) for r in self.rows)


@dataclass
class RenderModel:
    ir_version: str
    sources: list[dict[str, Any]]
    institutions: list[str]
    period_from: str | None
    period_to: str | None
    net_sgd: float
    per_ccy_balances: dict[str, float]
    fx_rates: dict[str, float]       # currency → SGD per 1 unit (SGD = 1.0)
    txn_tables_by_type: dict[str, list[CurrencyTable]]
    accounts: list[Any]      # original accounts, for the per-bank drill-down
    warnings: list[str]


def _account_institution(acc: Any) -> str:
    """Resolve the owning institution from the account's institution field."""
    return acc.institution or ""


def _skip_in_consolidated_table(txn: Any) -> bool:
    """Internal lines excluded from the consolidated combined transaction table.

    DBS labels internet-banking transfers as ``PAYMENT BY INTERNET``; these carry
    a negative (debit) amount and are internal/posted summaries that shouldn't
    appear in the consolidated table (nor in its totals / running net).
    """
    return txn.amount < 0 and "PAYMENT BY INTERNET" in (txn.description or "").upper()


def build_render_model(stmt: Any, fx_rates: dict[str, float] | None = None) -> RenderModel:
    meta = stmt.statement_meta
    consolidation = (stmt.extras or {}).get("consolidation", {})
    sources = consolidation.get("sources", [])
    institutions = sorted({s.get("institution") for s in sources if s.get("institution")})

    effective_fx = {**DEFAULT_FX_RATES, **(fx_rates or {})}

    net_sgd = 0.0
    for a in stmt.accounts:
        if a.balance is not None and a.currency:
            rate = effective_fx.get(a.currency)
            if rate is not None:
                net_sgd += a.balance * rate
    per_ccy: dict[str, float] = {}
    for a in stmt.accounts:
        if a.balance is not None and a.currency:
            per_ccy[a.currency] = per_ccy.get(a.currency, 0.0) + a.balance

    by_type_ccy: dict[tuple[str, str], CurrencyTable] = {}
    for acc in stmt.accounts:
        atype = acc.account_type
        if atype in _NON_TXN_ACCOUNTS:
            continue
        bank = _account_institution(acc)
        for t in acc.transactions:
            if _skip_in_consolidated_table(t):
                continue
            wd = abs(t.amount) if t.amount < 0 else None
            dp = t.amount if t.amount > 0 else None
            ct = by_type_ccy.setdefault(
                (atype, t.currency), CurrencyTable(currency=t.currency)
            )
            ct.rows.append(
                TxnRow(
                    date=t.posted_date,
                    bank=bank,
                    account=acc.account_no,
                    description=t.description,
                    withdrawal=wd,
                    deposit=dp,
                    balance_after=t.balance_after,
                    txn_id=t.txn_id,
                    currency=t.currency,
                )
            )

    for ct in by_type_ccy.values():
        ct.rows.sort(key=lambda r: (r.date, r.txn_id))
        # Running net deposits (deposit - withdrawal) across the currency table.
        # The per-account balance_after is meaningless once rows from multiple
        # accounts are interleaved, so the consolidated view uses this instead.
        running = 0.0
        for r in ct.rows:
            running += (r.deposit or 0.0) - (r.withdrawal or 0.0)
            r.net_deposits = running

    txn_tables_by_type: dict[str, list[CurrencyTable]] = {}
    for (atype, _ccy), ct in by_type_ccy.items():
        txn_tables_by_type.setdefault(atype, []).append(ct)
    for atype in txn_tables_by_type:
        txn_tables_by_type[atype].sort(key=lambda ct: ct.currency)

    return RenderModel(
        ir_version=stmt.ir_version,
        sources=sources,
        institutions=institutions,
        period_from=meta.period_from,
        period_to=meta.period_to,
        net_sgd=net_sgd,
        per_ccy_balances=per_ccy,
        fx_rates=effective_fx,
        txn_tables_by_type=txn_tables_by_type,
        accounts=stmt.accounts,
        warnings=stmt.warnings,
    )

"""detect_transfers.py — detect and link inter-bank and intra-bank transfers.

After consolidating IRs from multiple banks, these passes scan for transaction
pairs where money moved between accounts:

  * **Inter-bank**: accounts at *different* institutions (e.g.
    DBS FAST OUT $1,000 ←→ OCBC FAST IN $1,000).
  * **Intra-bank**: current accounts at the *same* institution (e.g.
    DBS Savings → DBS Current $500).

These are internal transfers that should be flagged to avoid double-counting in
net-worth calculations.

Detection rules (all must hold):
  1. Same ``posted_date``
  2. Opposite amounts: ``abs(A.amount + B.amount) < 1e-2``
  3. Neither transaction already flagged ``is_internal_transfer``
     (avoids interfering with FD↔CA linking handled by ``link_fd_to_ca``)
  4. Inter-bank: different institutions; intra-bank: same institution, different
     current accounts.

When a pair is matched:
  * ``is_internal_transfer = True`` on BOTH transactions
  * ``linked_txn_ids`` cross-linked bidirectionally
  * ``transfer_labels`` appended with ``"inter_bank"`` or ``"intra_bank"`` (deduped)
  * A warning emitted to ``statement.warnings``

Runs after ``consolidate_statements()`` and before ``verify_transfer_links()``.
Idempotent: already-matched transactions are skipped.
"""

from __future__ import annotations

from typing import Any


def detect_inter_bank_transfers(statement: Any) -> Any:
    """Detect and link inter-bank internal-transfer transaction pairs.

    Mutates and returns *statement*. Idempotent (skips already-linked txns).

    Parameters
    ----------
    statement : ParsedStatement
        The consolidated statement (post merge, pre verify_transfer_links).

    Returns
    -------
    ParsedStatement
        The same statement, mutated in place with links and warnings added.
    """
    # Build (account_no → institution) lookup from Account.institution.
    institution_by_account: dict[str, str] = {}
    for acct in statement.accounts:
        inst = (acct.institution or "").strip()
        if inst:
            institution_by_account[acct.account_no] = inst

    # Index every transaction by (posted_date, institution) for efficient grouping.
    # We group by posted_date first, then cross-check across institutions.
    by_date: dict[str, list[tuple[int, Any, Any]]] = {}
    for ai, acct in enumerate(statement.accounts):
        for _, txn in enumerate(acct.transactions or []):
            if not txn.posted_date:
                continue
            # Skip already-internal-transfer txns (preserve FD↔CA links).
            if txn.is_internal_transfer:
                continue
            by_date.setdefault(txn.posted_date, []).append((ai, acct, txn))

    matched_pairs = 0
    for posted_date, entries in by_date.items():
        n = len(entries)
        # Skip dates with only one unfrozen entry — no pairing possible.
        if n < 2:
            continue

        used: set[int] = set()

        for i in range(n):
            if i in used:
                continue
            _, acct_a, txn_a = entries[i]
            inst_a = institution_by_account.get(acct_a.account_no, "")
            if not inst_a:
                continue

            for j in range(i + 1, n):
                if j in used:
                    continue
                _, acct_b, txn_b = entries[j]
                inst_b = institution_by_account.get(acct_b.account_no, "")

                # Must be different institutions.
                if not inst_b or inst_a == inst_b:
                    continue

                # Must be opposite amounts (within tolerance).
                if abs(txn_a.amount + txn_b.amount) > 1e-2:
                    continue

                # Match found — cross-link.
                used.add(i)
                used.add(j)

                _cross_link(txn_a, txn_b)
                matched_pairs += 1

                # Emit warning.
                warn = (
                    f"Inter-bank transfer detected: {txn_a.txn_id!r} "
                    f"(account {acct_a.account_no}, {inst_a}) ←→ "
                    f"{txn_b.txn_id!r} "
                    f"(account {acct_b.account_no}, {inst_b}), "
                    f"amount {abs(txn_a.amount):,.2f}, date {posted_date}"
                )
                if warn not in statement.warnings:
                    statement.warnings.append(warn)
                break  # One match per txn_a; move to next txn_a.

    # Record detection stats in extras.
    extras = dict(statement.extras or {})
    cons = dict(extras.get("consolidation", {}) or {})
    transfers_extras = dict(cons.get("transfers", {}) or {})
    transfers_extras["inter_bank_detected"] = matched_pairs
    cons["transfers"] = transfers_extras
    extras["consolidation"] = cons
    statement.extras = extras

    return statement


def _cross_link(txn_a: Any, txn_b: Any, labels: tuple[str, ...] = ("inter_bank",)) -> None:
    """Set ``is_internal_transfer``, cross-link ``linked_txn_ids``, and
    append *labels* to ``transfer_labels`` on both transactions.
    """
    txn_a.is_internal_transfer = True
    txn_b.is_internal_transfer = True

    if txn_b.txn_id not in txn_a.linked_txn_ids:
        txn_a.linked_txn_ids = list(txn_a.linked_txn_ids) + [txn_b.txn_id]
    if txn_a.txn_id not in txn_b.linked_txn_ids:
        txn_b.linked_txn_ids = list(txn_b.linked_txn_ids) + [txn_a.txn_id]

    for lbl in labels:
        if lbl not in txn_a.transfer_labels:
            txn_a.transfer_labels = list(txn_a.transfer_labels) + [lbl]
        if lbl not in txn_b.transfer_labels:
            txn_b.transfer_labels = list(txn_b.transfer_labels) + [lbl]


def detect_intra_bank_transfers(statement: Any) -> Any:
    """Detect and link intra-bank current-account transfer transaction pairs.

    In a consolidated statement, a transfer between two current accounts at
    the **same** bank (e.g. DBS Savings → DBS Current) appears twice — once
    as a debit and once as a credit on the same day. This pass identifies
    those matched pairs, marks both as ``is_internal_transfer``, cross-links
    ``linked_txn_ids``, and labels them ``"intra_bank"``.

    Detection rules (all must hold):
      1. Same institution (intra-bank)
      2. Different current accounts (``account_type == "current"``)
      3. Same ``posted_date``
      4. Opposite amounts: ``abs(A.amount + B.amount) < 1e-2``
      5. Neither transaction already flagged ``is_internal_transfer``

    Mutates and returns *statement*. Idempotent (skips already-linked txns).

    Parameters
    ----------
    statement : ParsedStatement
        The consolidated statement (post merge, pre verify_transfer_links).

    Returns
    -------
    ParsedStatement
        The same statement, mutated in place with links and warnings added.
    """
    # Build (account_no → institution) lookup from Account.institution.
    institution_by_account: dict[str, str] = {}
    for acct in statement.accounts:
        inst = (acct.institution or "").strip()
        if inst:
            institution_by_account[acct.account_no] = inst

    # Index every non-frozen transaction from current accounts by (posted_date, institution).
    by_date: dict[str, list[tuple[int, Any, Any]]] = {}
    for ai, acct in enumerate(statement.accounts):
        if acct.account_type != "current":
            continue
        for _, txn in enumerate(acct.transactions or []):
            if not txn.posted_date:
                continue
            if txn.is_internal_transfer:
                continue
            by_date.setdefault(txn.posted_date, []).append((ai, acct, txn))

    matched_pairs = 0
    for posted_date, entries in by_date.items():
        n = len(entries)
        if n < 2:
            continue

        used: set[int] = set()

        for i in range(n):
            if i in used:
                continue
            _, acct_a, txn_a = entries[i]
            inst_a = institution_by_account.get(acct_a.account_no, "")
            if not inst_a:
                continue

            for j in range(i + 1, n):
                if j in used:
                    continue
                _, acct_b, txn_b = entries[j]
                inst_b = institution_by_account.get(acct_b.account_no, "")

                # Must be the SAME institution (intra-bank).
                if not inst_b or inst_a != inst_b:
                    continue
                # Must be DIFFERENT accounts.
                if acct_a.account_no == acct_b.account_no:
                    continue
                # Must be opposite amounts (within tolerance).
                if abs(txn_a.amount + txn_b.amount) > 1e-2:
                    continue

                # Match found — cross-link.
                used.add(i)
                used.add(j)

                _cross_link(txn_a, txn_b, labels=("intra_bank",))
                matched_pairs += 1

                warn = (
                    f"Intra-bank transfer detected: {txn_a.txn_id!r} "
                    f"(account {acct_a.account_no}, {inst_a}) ←→ "
                    f"{txn_b.txn_id!r} "
                    f"(account {acct_b.account_no}, {inst_b}), "
                    f"amount {abs(txn_a.amount):,.2f}, date {posted_date}"
                )
                if warn not in statement.warnings:
                    statement.warnings.append(warn)
                break  # One match per txn_a; move to next txn_a.

    # Record detection stats in extras.
    extras = dict(statement.extras or {})
    cons = dict(extras.get("consolidation", {}) or {})
    transfers_extras = dict(cons.get("transfers", {}) or {})
    transfers_extras["intra_bank_detected"] = matched_pairs
    cons["transfers"] = transfers_extras
    extras["consolidation"] = cons
    statement.extras = extras

    return statement

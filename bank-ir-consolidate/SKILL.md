---
name: bank-ir-consolidate
description: Consolidate multiple sg-bank-to-md IR JSON files (*.ir.json) into a single consolidated IR and render it as a human-readable cross-bank markdown summary. Use when the user has IR JSON from multiple bank statements (DBS/OCBC/UOB/ICBC) and wants them merged into one file and/or summarized in markdown.
---

# Bank IR Consolidate

Merges the `*.ir.json` intermediate representations produced by the
`sg-bank-to-md` skill into one consolidated `ParsedStatement`, then renders a
cross-bank, multi-account, multi-currency markdown report.

## Prerequisites

- `sg-bank-to-md` skill (provides the IR schema + masking helpers via
  `sg_bank_pdf_parser`). The scripts resolve `sg_bank_pdf_parser` automatically
  from the sibling `../sg-bank-to-md` directory, from `--parser-dir`, or from an
  installed `sg_bank_pdf_parser` package (PyPI). No heavy parser dependencies
  (pdfplumber etc.) are imported — only the schema + masking helpers.

## Workflow

1. **Consolidate** the IR JSON files into one:

   ```bash
   python scripts/consolidate.py a.ir.json b.ir.json c.ir.json -o consolidated.ir.json
   ```

   - De-duplicates transactions by `txn_id` within each
     `(institution, account_no, name)` group (handles overlapping statement
     periods).
   - Carries forward the **minimum** `ir_version` and refuses IR older than
     `2026.3` (the `from_json` gate).
   - Stores provenance in `extras.consolidation.sources` (per-source file,
     parser, parsed_at, ir_version, institution, account/txn counts) plus the
     dedup count.

2. **Render** the consolidated IR to markdown:

   ```bash
   python scripts/render_md.py consolidated.ir.json -o consolidated.md
   ```

   - Net Position (SGD-equivalent via FX rates, plus per-currency
     native balances).
   - Per-bank, per-account transaction tables, FD records, and investment
     holdings.
   - Masking is on by default (matches `sg-bank-to-md`); use `--no-mask` to
     disable.

   **FX rates (on-demand, cached).** FX rates are no longer hardcoded. At render
   time the skill fetches live mid-market SGD-per-unit rates for the union of a
   built-in watch-list (`USD, JPY, CNY`) and every non-SGD currency present in
   the statement's accounts, then caches them.

   ```bash
   python scripts/render_md.py consolidated.ir.json -o consolidated.md \
       --fx-date 2026-06-30 \
       --fx-provider frankfurter \
       --fx-cache-dir bank-ir-consolidate/cache
   ```

   - Rates are fetched from the chosen provider (default **Frankfurter**,
     `https://api.frankfurter.dev`, free & keyless, supports historical dates)
     and stored as `1 SGD = X` inverted to **SGD per 1 unit** — the same shape
     `render_model.DEFAULT_FX_RATES` uses.
   - Caching is per `(provider, date)` under `--fx-cache-dir` (default
     `bank-ir-consolidate/cache/`, git-ignored). A repeated render with the same
     date reuses the cache (`source: cached`). `--fx-force-refresh` re-fetches.
   - If `as_of` falls on a weekend/holiday (provider 404s), the date steps back
     up to 5 calendar days to the last trading day.
   - Any network/parse failure degrades to the previous cache, then to the
     hardcoded `DEFAULT_FX_RATES` fallback — the render never crashes.
   - The FX provenance (`source`, `provider`, `as_of`, `fetched_at`, rates, and
     any `missing` symbols) is embedded into `extras.consolidation.fx` of the
     consolidated IR for full reproducibility (use `--fx-no-embed` to skip, or
     `--fx-embed-ir PATH` to write it elsewhere).
   - The markdown FX table shows whether rates are **live / cached / fallback**
     and the effective date; extra currencies (e.g. `EUR`) discovered in the
     statement are listed automatically.

## Public IR contract

The IR schema is defined publicly by `sg-bank-to-md`:
`references/ir.schema.json` (JSON Schema 2020-12) and
`sg_bank_pdf_parser/ir_schema.py`. Downstream consumers must require
`ir_version >= 2026.3`.

## Options

- `consolidate.py`: `--parser-dir DIR`, `--min-ir-version VER`, `--no-dedup`,
  `--indent N`.
- `render_md.py`: `--parser-dir DIR`, `--no-mask`, plus FX options:
  `--fx-date YYYY-MM-DD`, `--fx-cache-dir DIR`, `--fx-provider NAME`
  (default `frankfurter`), `--fx-offline`, `--fx-force-refresh`,
  `--fx-no-embed`, `--fx-embed-ir PATH`.

#!/usr/bin/env python3
"""
Unit tests for ``_wrap_inline`` in docx2md/scripts/docx2md.py.

    These tests do NOT require a .docx file — they exercise the inline emphasis
    wrapping logic directly, including the "add a space after punctuation" scheme
    where bordering punctuation is kept *inside* the emphasis and a single space
    is added *outside* the markers only when the border character could break
    CommonMark flanking.

Run with:
    python test_wrap_inline.py          # plain asserts, prints summary
    python -m pytest test_wrap_inline.py  # if pytest is installed
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONVERTER = HERE.parent / "scripts" / "docx2md.py"


def _load():
    spec = importlib.util.spec_from_file_location("docx2md", CONVERTER)
    if spec is None or spec.loader is None:
        sys.exit(f"Failed to load converter: {CONVERTER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load()
_wrap_inline = _mod._wrap_inline


def _cases():
    """Return (description, args, expected) tuples."""
    # scheme B: punctuation kept inside, space added outside only on flanking risk
    return [
        # (desc, (text, bold, italic, code, href), expected)
        ("punct-bordered bold (full-width paren)", ("（重要）", True, False, False, None), " **（重要）** "),
        ("punct-bordered bold (full-width quote)", ("“引用”", True, False, False, None), " **“引用”** "),
        ("leading punct only", ("。结尾", True, False, False, None), " **。结尾**"),
        ("plain letter borders, no space", ("重要", True, False, False, None), "**重要**"),
        ("plain letter borders italic", ("abc", False, True, False, None), "*abc*"),
        ("plain letter borders bold+italic", ("xyz", True, True, False, None), "***xyz***"),
        ("ascii punct borders", ("(note)", True, False, False, None), " **(note)** "),
        ("empty text", ("", True, False, False, None), ""),
        ("no emphasis", ("普通", False, False, False, None), "普通"),
        ("code style ignores punct", ("（代码）", False, False, True, None), "`（代码）`"),
        ("href suppresses space", ("（重要）", True, False, False, "http://e.x"), "[**（重要）**](http://e.x)"),
        ("href plain", ("link", False, True, False, "http://e.x"), "[*link*](http://e.x)"),
        ("space-bordered text adds outer spaces", (" 两边空格 ", True, False, False, None), " ** 两边空格 ** "),
    ]


def test_wrap_inline_cases():
    for desc, args, expected in _cases():
        got = _wrap_inline(*args)
        assert got == expected, f"[{desc}] expected {expected!r}, got {got!r}"


if __name__ == "__main__":
    test_wrap_inline_cases()
    print(f"✅ all {len(_cases())} _wrap_inline cases passed")

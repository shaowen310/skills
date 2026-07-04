#!/usr/bin/env python3
"""Unit tests for ``_heading_level``.

Run with:  python test_heading_level.py
(or via pytest, which will discover the ``test_*`` functions).
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

from lxml import etree  # pyright: ignore[reportAttributeAccessIssue, reportMissingTypeStubs]

HERE = Path(__file__).resolve().parent
CONVERTER = HERE.parent / "scripts" / "docx2md.py"

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _load_converter() -> Any:
    spec = importlib.util.spec_from_file_location("docx2md", CONVERTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _paragraph_with_outline(val: str | None) -> Any:
    """Build a minimal ``w:p`` element carrying an optional ``w:outlineLvl``."""
    el = etree.Element(f"{{{_W}}}p")
    pPr = etree.SubElement(el, f"{{{_W}}}pPr")
    if val is not None:
        outline = etree.SubElement(pPr, f"{{{_W}}}outlineLvl")
        outline.set(f"{{{_W}}}val", val)
    return el


def test_english_heading():
    conv = _load_converter()
    assert conv._heading_level("Heading 1") == 1
    assert conv._heading_level("Heading 3", None) == 3
    assert conv._heading_level("HEADING 2") == 2


def test_chinese_heading():
    conv = _load_converter()
    assert conv._heading_level("标题 1") == 1
    assert conv._heading_level("标题 4") == 4


def test_title_subtitle():
    conv = _load_converter()
    assert conv._heading_level("Title") == 1
    assert conv._heading_level("Subtitle") == 2


def test_none_and_unknown():
    conv = _load_converter()
    assert conv._heading_level(None) == 0
    assert conv._heading_level("Normal") == 0
    assert conv._heading_level("Body Text") == 0


def test_outline_fallback():
    conv = _load_converter()
    # outlineLvl 0 => H1, even with no style name
    el = _paragraph_with_outline("0")
    assert conv._heading_level(None, el) == 1
    el = _paragraph_with_outline("5")
    assert conv._heading_level(None, el) == 6


def test_outline_body_text_ignored():
    conv = _load_converter()
    # val 9 means "Body Text" in Word -> not a heading
    el = _paragraph_with_outline("9")
    assert conv._heading_level(None, el) == 0
    # No outline element at all -> not a heading
    el = _paragraph_with_outline(None)
    assert conv._heading_level(None, el) == 0


def test_level_cap():
    conv = _load_converter()
    # Markdown only supports 6 levels; deeper headings are capped.
    assert conv._heading_level("标题 9") == 6
    el = _paragraph_with_outline("8")  # outline 8 => heading 9
    assert conv._heading_level(None, el) == 6


def test_heading_strips_bold_italic_but_keeps_code_and_link():
    conv = _load_converter()

    class _FakeRun:
        def __init__(self, text: str, *, bold: bool = False,
                     italic: bool = False, font_name: str | None = None,
                     href: str | None = None) -> None:
            self.text: str = text
            self.bold: bool = bold
            self.italic: bool = italic
            self.font: Any = types.SimpleNamespace(name=font_name)
            self.href: str | None = href

    # Patch the hyperlink resolver so we can inject href without real XML.
    original = conv._run_hyperlink_target

    def _resolve_href(run: _FakeRun) -> str | None:
        return run.href

    conv._run_hyperlink_target = _resolve_href

    try:
        bold_run = _FakeRun("文档说明", bold=True)
        assert conv._runs_markdown([bold_run], keep_emphasis=False) == "文档说明"

        italic_run = _FakeRun("注意", italic=True)
        assert conv._runs_markdown([italic_run], keep_emphasis=False) == "注意"

        # code span kept
        code_run = _FakeRun("foo()", font_name="Courier New")
        assert conv._runs_markdown([code_run], keep_emphasis=False) == "`foo()`"

        # hyperlink kept
        link_run = _FakeRun("说明", href="https://example.com")
        assert (
            conv._runs_markdown([link_run], keep_emphasis=False)
            == "[说明](https://example.com)"
        )

        # keep_emphasis=True (default) still adds emphasis for body text
        assert conv._runs_markdown([bold_run]) == "**文档说明**"
    finally:
        conv._run_hyperlink_target = original


if __name__ == "__main__":
    functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in functions:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {fn.__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print(f"\nAll {len(functions)} tests passed")

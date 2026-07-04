"""
Shared pytest fixtures and configuration for pptx-translate tests.

This conftest.py:
- Sets up mocked dependencies (lxml, pptx) before any test module is imported
- Ensures the scripts directory is on sys.path
- Provides reusable fixtures for font detection tests
"""

import sys
import os
from unittest.mock import MagicMock
from collections.abc import Generator

import pytest

# ---------------------------------------------------------------------------
# Module-level setup: mock external dependencies before any test import
# This runs when pytest loads conftest.py (before any test module).
# ---------------------------------------------------------------------------
sys.modules['lxml'] = MagicMock()
sys.modules['lxml.etree'] = MagicMock()
sys.modules['pptx'] = MagicMock()
sys.modules['pptx.enum'] = MagicMock()
sys.modules['pptx.enum.text'] = MagicMock()  # requires pptx.enum first (MSO_AUTO_SIZE)
sys.modules['pptx.util'] = MagicMock()
sys.modules['pptx.util.Inches'] = MagicMock()
sys.modules['pptx.util.Pt'] = MagicMock()
sys.modules['pptx.enum.shapes'] = MagicMock()

# Add scripts directory to sys.path (used by test modules importing translate_pptx)
_scripts_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def scripts_dir() -> str:
    """Return the absolute path to the pptx-translate scripts directory."""
    return _scripts_dir


@pytest.fixture(scope="session")
def translate_module():
    """Import and return the translate_pptx module (lazy import via fixture)."""
    from translate_pptx import (
        is_sans_serif_font,
        is_serif_font,
        set_font_explicit,
        normalize_quotes,
        normalize_text_for_matching,
        SANS_SERIF_FONTS,
        SERIF_FONTS,
    )
    return {
        "is_sans_serif_font": is_sans_serif_font,
        "is_serif_font": is_serif_font,
        "set_font_explicit": set_font_explicit,
        "normalize_quotes": normalize_quotes,
        "normalize_text_for_matching": normalize_text_for_matching,
        "SANS_SERIF_FONTS": SANS_SERIF_FONTS,
        "SERIF_FONTS": SERIF_FONTS,
    }


@pytest.fixture
def sample_sans_serif_fonts() -> list[str]:
    """Return a list of known sans-serif font names for testing."""
    return [
        "微软雅黑", "Microsoft YaHei", "黑体", "SimHei", "等线", "DengXian",
        "Arial", "Helvetica", "Calibri", "Verdana", "Tahoma", "Segoe UI",
    ]


@pytest.fixture
def sample_serif_fonts() -> list[str]:
    """Return a list of known serif font names for testing."""
    return [
        "宋体", "SimSun", "明体", "MS Mincho", "仿宋", "FangSong", "楷体", "KaiTi",
        "Times New Roman", "Georgia", "Garamond", "Baskerville", "Palatino",
        "Cambria",
    ]

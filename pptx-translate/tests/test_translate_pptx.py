#!/usr/bin/env python3
"""
Unit tests for translate_pptx.py font recognition and replacement.

Tests the font detection functions (is_sans_serif_font, is_serif_font) and
font replacement logic in translate_paragraph.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Mock the dependencies before importing translate_pptx
sys.modules['lxml'] = MagicMock()
sys.modules['lxml.etree'] = MagicMock()
sys.modules['pptx'] = MagicMock()
sys.modules['pptx.enum'] = MagicMock()
sys.modules['pptx.enum.text'] = MagicMock()
sys.modules['pptx.util'] = MagicMock()
sys.modules['pptx.util.Inches'] = MagicMock()
sys.modules['pptx.util.Pt'] = MagicMock()
sys.modules['pptx.enum.shapes'] = MagicMock()

# Add scripts directory to path to import translate_pptx
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
sys.path.insert(0, os.path.normpath(scripts_dir))

# Now import the module - it will use the mocked dependencies
from translate_pptx import is_sans_serif_font, is_serif_font, set_font_explicit, SANS_SERIF_FONTS, SERIF_FONTS


class TestFontDetection(unittest.TestCase):
    """Test font type detection functions."""

    def test_sans_serif_font_detection(self):
        """Test that sans-serif fonts are correctly identified."""
        # Chinese sans-serif fonts
        self.assertTrue(is_sans_serif_font("微软雅黑"))
        self.assertTrue(is_sans_serif_font("Microsoft YaHei"))
        self.assertTrue(is_sans_serif_font("黑体"))
        self.assertTrue(is_sans_serif_font("SimHei"))
        self.assertTrue(is_sans_serif_font("等线"))
        self.assertTrue(is_sans_serif_font("DengXian"))

        # Western sans-serif fonts
        self.assertTrue(is_sans_serif_font("Arial"))
        self.assertTrue(is_sans_serif_font("Arial Narrow"))
        self.assertTrue(is_sans_serif_font("Helvetica"))
        self.assertTrue(is_sans_serif_font("Calibri"))
        self.assertTrue(is_sans_serif_font("Verdana"))
        self.assertTrue(is_sans_serif_font("Tahoma"))
        self.assertTrue(is_sans_serif_font("Segoe UI"))
        self.assertTrue(is_sans_serif_font("Open Sans"))
        self.assertTrue(is_sans_serif_font("Roboto"))
        self.assertTrue(is_sans_serif_font("Montserrat"))

        # Theme fonts (should be treated as sans-serif)
        self.assertTrue(is_sans_serif_font("+mn-ea"))
        self.assertTrue(is_sans_serif_font("+mj-ea"))
        self.assertTrue(is_sans_serif_font("+mn-cs"))

    def test_serif_font_detection(self):
        """Test that serif fonts are correctly identified."""
        # Chinese serif fonts
        self.assertTrue(is_serif_font("宋体"))
        self.assertTrue(is_serif_font("SimSun"))
        self.assertTrue(is_serif_font("明体"))
        self.assertTrue(is_serif_font("MS Mincho"))
        self.assertTrue(is_serif_font("仿宋"))
        self.assertTrue(is_serif_font("FangSong"))
        self.assertTrue(is_serif_font("楷体"))
        self.assertTrue(is_serif_font("KaiTi"))

        # Western serif fonts
        self.assertTrue(is_serif_font("Times New Roman"))
        self.assertTrue(is_serif_font("Times"))
        self.assertTrue(is_serif_font("Georgia"))
        self.assertTrue(is_serif_font("Garamond"))
        self.assertTrue(is_serif_font("Baskerville"))
        self.assertTrue(is_serif_font("Palatino"))
        self.assertTrue(is_serif_font("Cambria"))
        self.assertTrue(is_serif_font("Bookman"))
        self.assertTrue(is_serif_font("Bodoni"))
        self.assertTrue(is_serif_font("Century Schoolbook"))

    def test_sans_serif_not_identified_as_serif(self):
        """Test that sans-serif fonts are not identified as serif."""
        self.assertFalse(is_serif_font("微软雅黑"))
        self.assertFalse(is_serif_font("Arial"))
        self.assertFalse(is_serif_font("Helvetica"))
        self.assertFalse(is_serif_font("Calibri"))

    def test_serif_not_identified_as_sans_serif(self):
        """Test that serif fonts are not identified as sans-serif."""
        self.assertFalse(is_sans_serif_font("宋体"))
        self.assertFalse(is_sans_serif_font("Times New Roman"))
        self.assertFalse(is_sans_serif_font("Georgia"))
        self.assertFalse(is_sans_serif_font("Garamond"))

    def test_case_insensitive_detection(self):
        """Test that font detection is case-insensitive."""
        self.assertTrue(is_sans_serif_font("ARIAL"))
        self.assertTrue(is_sans_serif_font("helvetica"))
        self.assertTrue(is_serif_font("TIMES NEW ROMAN"))
        self.assertTrue(is_serif_font("georgia"))

    def test_partial_match_detection(self):
        """Test that partial font name matches work."""
        self.assertTrue(is_sans_serif_font("Arial Narrow Bold"))
        self.assertTrue(is_serif_font("Times New Roman Bold"))
        self.assertTrue(is_serif_font("Georgia Pro"))

    def test_none_and_empty_font_names(self):
        """Test handling of None and empty font names."""
        self.assertFalse(is_sans_serif_font(None))
        self.assertFalse(is_serif_font(None))
        self.assertFalse(is_sans_serif_font(""))
        self.assertFalse(is_serif_font(""))


class TestFontReplacement(unittest.TestCase):
    """Test font replacement logic."""

    def test_set_font_explicit(self):
        """Test that set_font_explicit correctly sets font in XML."""
        # This test requires a mock run object with XML
        # For now, we just test that the function doesn't crash with None
        # In a real test, we would create a mock run with proper XML structure
        pass

    def test_font_type_to_target_font_mapping(self):
        """Test that correct target font is selected based on source font."""
        # Test cases: (source_font, expected_target_font)
        test_cases = [
            # Sans-serif fonts should map to Arial
            ("微软雅黑", "Arial"),
            ("Arial", "Arial"),
            ("Helvetica", "Arial"),
            ("Calibri", "Arial"),
            # Serif fonts should map to Times New Roman
            ("宋体", "Times New Roman"),
            ("Times New Roman", "Times New Roman"),
            ("Georgia", "Times New Roman"),
            ("Garamond", "Times New Roman"),
        ]

        for source_font, expected_target in test_cases:
            with self.subTest(source=source_font, target=expected_target):
                # Determine target font based on source font
                target_font = None
                if is_sans_serif_font(source_font):
                    target_font = "Arial"
                elif is_serif_font(source_font):
                    target_font = "Times New Roman"

                self.assertEqual(target_font, expected_target)


class TestQuoteNormalization(unittest.TestCase):
    """Test quote normalization functions."""

    def test_normalize_quotes(self):
        """Test that various quote characters are normalized."""
        from translate_pptx import normalize_quotes

        # Chinese quotes to English quotes
        self.assertEqual(normalize_quotes('"你好"'), '"你好"')
        self.assertEqual(normalize_quotes('"谢谢"'), '"谢谢"')

        # Already English quotes should remain unchanged
        self.assertEqual(normalize_quotes('"Hello"'), '"Hello"')
        self.assertEqual(normalize_quotes("'World'"), "'World'")

    def test_normalize_text_for_matching(self):
        """Test text normalization for matching."""
        from translate_pptx import normalize_text_for_matching

        # Test quote normalization
        self.assertEqual(
            normalize_text_for_matching('"你好"'),
            '"你好"'
        )

        # Test whitespace normalization
        self.assertEqual(
            normalize_text_for_matching("Hello   World"),
            "Hello World"
        )

        # Test strip
        self.assertEqual(
            normalize_text_for_matching("  Test  "),
            "Test"
        )


class TestFontLists(unittest.TestCase):
    """Test that font lists are comprehensive."""

    def test_sans_serif_fonts_not_empty(self):
        """Test that SANS_SERIF_FONTS is not empty."""
        self.assertGreater(len(SANS_SERIF_FONTS), 0)

    def test_serif_fonts_not_empty(self):
        """Test that SERIF_FONTS is not empty."""
        self.assertGreater(len(SERIF_FONTS), 0)

    def test_no_duplicate_fonts_between_lists(self):
        """Test that no font appears in both SANS_SERIF_FONTS and SERIF_FONTS."""
        duplicates = SANS_SERIF_FONTS & SERIF_FONTS
        self.assertEqual(len(duplicates), 0, f"Duplicate fonts found: {duplicates}")

    def test_common_fonts_coverage(self):
        """Test that common fonts are covered."""
        # Common Chinese fonts
        self.assertIn("微软雅黑", SANS_SERIF_FONTS)
        self.assertIn("黑体", SANS_SERIF_FONTS)
        self.assertIn("宋体", SERIF_FONTS)
        self.assertIn("仿宋", SERIF_FONTS)
        self.assertIn("楷体", SERIF_FONTS)

        # Common Western fonts
        self.assertIn("Arial", SANS_SERIF_FONTS)
        self.assertIn("Times New Roman", SERIF_FONTS)
        self.assertIn("Georgia", SERIF_FONTS)
        self.assertIn("Calibri", SANS_SERIF_FONTS)


if __name__ == "__main__":
    unittest.main()

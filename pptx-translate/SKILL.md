---
name: pptx-translate
description: 'Chinese-to-English PPT/PPTX slide translation while preserving all formatting. Automatically changes sans-serif fonts to Arial for better English readability. Use when the user asks to translate a PowerPoint document from Chinese to English (or vice versa), convert presentation language, or localize slide content. Triggers on: "翻译PPT", "translate PPT/slides/presentation", "PPT英文化", "PPT翻译成英文". Features: paragraph-level translation with context awareness, concise business-appropriate wording, structure and styling preservation.'
agent_created: true
---

# PPT Translation Skill

Two-step workflow for translating PPTX files while preserving all formatting (layout, fonts, colors, images, tables, shapes).

## Overview

This skill translates Chinese PowerPoint presentations to English (or vice versa) at the paragraph level:

1. **Extract** all text into a JSON mapping
2. **Translate** each text segment (manually or via AI)
3. **Apply** translations back to the PPTX

**Key Features:**
- **Formatting Preservation**: All visual elements intact (fonts, colors, sizes, bold/italic, shapes, images, tables, slide notes)
- **Automatic Font Optimization**: Sans-serif fonts (e.g., 微软雅黑, Arial) automatically switch to **Arial** for better English readability; serif fonts preserved
- **Smart Line Spacing**: Automatically adjusts line spacing to ≤1.5x for professional layouts
- **Font Size Limit**: Automatically caps font size at 48pt for English text containing words (numbers/symbols only are preserved) to prevent overly large text
- **AutoFit Text Boxes**: Automatically sets text boxes to "Resize shape to fit text" to accommodate longer translated text
- **Handles Complex Layouts**: Group shapes, tables, notes, connectors all supported

## ⚠️ File Format Requirements

**Supported:** Only `.pptx` files (PowerPoint 2007+)

**NOT Supported:** `.ppt` files (PowerPoint 97-2003)

This skill uses `python-pptx`, which only supports `.pptx` format.

### Converting .ppt to .pptx

1. Open `.ppt` in Microsoft PowerPoint
2. **File** → **Save As** → **PowerPoint Presentation (*.pptx)**
3. Save and use the converted file

## Workflow

### File Organization Rules

- **Input PPTX**: Read-only source.
- **Generated files (JSON, output PPTX)**: Always save to **current working directory (CWD)**

---

### Step 1: Extract Text from PPTX

```bash
python scripts/extract_text.py <input.pptx> <output.json>
```

**Recommended** (saves to workspace):
```bash
python scripts/extract_text.py "<input.pptx>" "./<basename>_translations.json"
```

**Output**: JSON file with original texts as keys and empty strings as values. Includes all text from shapes, tables, group shapes, and notes.

---

### Step 2: Fill in Translations

Open the JSON file and add translations. **Follow these guidelines:**

**Translation Quality:**
- **Be concise**: Use as few words as possible. Prefer "Follow these steps" over "Please follow the steps below to perform operations"
- **Business professional tone**: Use strong verbs, active voice; avoid filler words (e.g., "In order to", "It should be noted that")
- **Maintain context**: Consider surrounding paragraphs for consistency
- **Preserve brackets**: `【二维码管理】` → `[QR Code Management]`
- **Keep technical terms consistent** across all slides
- **Don't merge/split paragraphs**: Match the original granularity

**CRITICAL — Key Preservation:**
Translation matching uses exact-string comparison. **Always copy the original key unchanged** — only edit the value (right side). A single typo in the key causes that paragraph to stay untranslated.

**Quote Handling**: Script auto-normalizes Chinese quotes (`''`, `""`) to English quotes, so minor differences won't cause failures.

---

### Step 2.5: Polish Translations (Recommended)

AI-generated translations may have an "AI taste" — formulaic expressions, monotonous sentence structures, and unnaturally formal wording. After filling in translations, polish them to sound natural and human-like.

**Option A — Use the Humanizer Skill (if available):**
If a **humanizer** skill is installed and available, pass the translations JSON to it for automated polishing. This can batch-process all translations to sound more natural while preserving meaning, business tone, and key-value structure. Activate it by running the humanizer skill with the translations JSON file.

**Option B — Manual polishing:**
- **Read aloud**: If it sounds robotic, rewrite for natural flow
- **Shorten**: Aim for 60-80% of the original word count where possible
- **Vary sentence structure**: Avoid starting every bullet with the same verb
- **Watch for literal translations**: "发挥重要作用" → "Plays a key role" (not "Plays an important function role")

---

### Step 3: Apply Translations

```bash
python scripts/translate_pptx.py <input.pptx> <translations.json> <output.pptx>
```

**Recommended**:
```bash
python scripts/translate_pptx.py "<input.pptx>" "./<basename>_translations.json" "./<basename>_en.pptx"
```

---

### Step 3.5: Verify Translations (Recommended)

After applying translations, verify that all text has been translated. The script reports untranslated paragraphs as warnings with **slide numbers** for easy locating.

**Sample warning output:**
```
Warning: 3 paragraph(s) could not be translated (no matching key):
  Slide 5 [TextBox 1]: '未来发展规划'
  Slide 8 [Table 1]: '合计'
  Slide 12 [<notes>]: '备注内容'
```

**Check for untranslated text:**
- Review script output for warnings — each lists the slide number, shape name, and untranslated text
- Common causes of untranslated text:
  - **Key mismatch**: Original text in JSON key doesn't exactly match PPTX text (typos, extra spaces, different quotes)
  - **Partial translation**: Some paragraphs in a shape were translated but others weren't
  - **Dynamic content**: Text in shapes that were added/modified after extraction

**Fix untranslated text:**
1. Open the PPTX to the reported slide number to locate the untranslated text
2. Check the corresponding key in `translations.json` — ensure it matches exactly (copy from PPTX to avoid typos)
3. Re-run Step 3 after fixing the JSON

**Note:** The script preserves original formatting. If a paragraph is untranslated, it remains in the output with original text and formatting intact.

---

## Prerequisites

```bash
pip install python-pptx
```

## Scripts

### `scripts/extract_text.py`
Extracts all paragraph texts from a PPTX into a JSON mapping (see Step 1).

### `scripts/translate_pptx.py`
Applies translations from JSON to PPTX, preserving all formatting (see Step 3). Handles paragraph matching, formatting preservation, group shapes, tables, notes, and reports untranslated text as warnings.

## Font & Layout Handling

### Font Optimization
- **Sans-serif fonts** (微软雅黑, Arial, Helvetica, Calibri, etc.) → **Arial** (Chinese→English)
- **Serif fonts** (Times New Roman, 宋体, 楷体, Georgia, Garamond, etc.) → **Times New Roman** (Chinese→English)
- **All other formatting** (size, color, bold, italic, alignment) → **Preserved**

### Font Size Limit (Chinese→English)

When translating from Chinese to English, apply a maximum font size of **48pt** for text paragraphs that contain actual words (not numbers or symbols only):

- **Contains words** (e.g., "Revenue Growth", "市场份额"): Cap font size at 48pt
- **Numbers/symbols only** (e.g., "2024", "85%", "¥1.5M"): Preserve original font size
- **Mixed content** (e.g., "2024 Annual Report"): Apply the 48pt limit

This prevents overly large font sizes that can occur when short Chinese phrases expand into longer English text.

---

### AutoFit Text Boxes (Chinese→English)

When translating from Chinese to English, text boxes are automatically set to **"Resize shape to fit text"** mode:

- **Purpose**: English text is often longer than the original Chinese text, which can cause text overflow
- **Behavior**: The shape automatically resizes to accommodate the translated text
- **Applies to**: All text boxes, table cells, and shapes with text frames
- **Benefit**: Prevents text cutoff and ensures all translated content is visible

This feature is especially important for:
- Short Chinese phrases that expand significantly in English
- Tight layout designs where text overflow is likely
- Table cells with fixed widths

---

### Line Spacing Adjustment
- **> 1.5x spacing** → Adjusted to **1.5x**
- **≤ 1.5x spacing** → **Unchanged**
- Applies to all paragraphs (shapes, tables, notes)

This prevents overly spaced text while maintaining compact, professional layouts.

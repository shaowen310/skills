#!/usr/bin/env python3
"""
eddx_translate.py

Translate text inside an Edraw (.eddx) file between languages without touching
anything else. This script is bundled by the eddx-translate skill.

Usage:
    python eddx_translate.py <input.eddx> <mapping.json> [output.eddx]

If output is omitted, it defaults to <input>_translated.eddx.
The source file is never modified.

mapping.json format:
{
    "Old English Text 1": "新中文文本1",
    "Old English Text 2": "新中文文本2"
}

Or the reverse (中文 -> English). Keys are matched exactly against the trimmed
text content of <tp> elements in pages/page1.xml.
"""

import json
import re
import sys
import zipfile
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory


def extract_texts(content: str) -> list[str]:
    """Return all text contents found in <tp> elements."""
    return [t.strip() for t in re.findall(r'<tp[^>]*>([^<]*)</tp>', content)]


def replace_tp_text(content: str, mapping: dict[str, str]) -> tuple[str, int]:
    """Replace text inside <tp> elements according to mapping."""
    def replacer(m: re.Match[str]) -> str:
        opening = m.group(1)
        text = m.group(2)
        closing = m.group(3)
        if text in mapping:
            return f'{opening}{mapping[text]}{closing}'
        return m.group(0)

    new_content, count = re.subn(
        r'(<tp[^>]*>)([^<]*)(</tp>)', replacer, content, flags=re.DOTALL
    )
    return new_content, count


def translate_eddx(
    input_path: str | PathLike[str],
    mapping_path: str | PathLike[str],
    output_path: str | PathLike[str] | None = None,
) -> tuple[str, int]:
    input_path = Path(input_path)
    mapping_path = Path(mapping_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    with open(mapping_path, encoding='utf-8') as f:
        mapping = json.load(f)

    if not output_path:
        output_path = input_path.with_suffix('.translated.eddx')
    else:
        output_path = Path(output_path)

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        unpack_dir = tmp_path / 'unpacked'

        # Unpack source
        with zipfile.ZipFile(input_path, 'r') as z:
            z.extractall(unpack_dir)

        # Edit pages/page1.xml
        page1_path = unpack_dir / 'pages' / 'page1.xml'
        if not page1_path.exists():
            raise FileNotFoundError(
                "pages/page1.xml not found; this may not be a valid .eddx file."
            )

        content = page1_path.read_text(encoding='utf-8')
        new_content, count = replace_tp_text(content, mapping)

        if count == 0:
            print("Warning: no <tp> text matched the mapping keys.")

        page1_path.write_text(new_content, encoding='utf-8')

        # Repack with same order and compression as original
        with zipfile.ZipFile(input_path) as src_zip, \
             zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as dst_zip:
            for item in src_zip.infolist():
                data_path = unpack_dir / item.filename
                data = data_path.read_bytes()
                new_info = zipfile.ZipInfo(
                    filename=item.filename, date_time=item.date_time
                )
                new_info.compress_type = item.compress_type or zipfile.ZIP_DEFLATED
                new_info.external_attr = item.external_attr
                dst_zip.writestr(new_info, data)

    return str(output_path), count


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    input_file = sys.argv[1]
    mapping_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    out, count = translate_eddx(input_file, mapping_file, output_file)
    print(f"Translated {count} text node(s) -> {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

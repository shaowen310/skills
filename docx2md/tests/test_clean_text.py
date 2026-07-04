import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CONVERTER = _HERE.parent / "scripts" / "docx2md.py"


def _load_clean_text():
    """Import ``_clean_text`` from scripts/docx2md.py (mirrors run_all.py)."""
    spec = importlib.util.spec_from_file_location("docx2md", _CONVERTER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load converter: {_CONVERTER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._clean_text


_clean_text = _load_clean_text()


def main() -> None:
    cases = [
        ("cell soft wrap", "消息通知\n对象", "消息通知 对象"),
        ("crlf", "a\r\nb", "a b"),
        ("cr only", "a\rb", "a b"),
        ("trailing newline", "hello\n", "hello"),
        ("control + newline", "x\u0001\ny", "x y"),
        ("nested tabs/space collapse", "a  \n  b", "a b"),
    ]
    ok = True
    for name, src, exp in cases:
        got = _clean_text(src)
        status = "ok" if got == exp else "FAIL"
        if got != exp:
            ok = False
        print(f"[{status}] {name}: {src!r} -> {got!r} (expect {exp!r})")
    print("ALL PASS" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""极简测试运行器：python tests/run_all.py"""
from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

MODULES = [
    "test_tme",
    "test_googlenews",
    "test_detection",
    "test_llm",
    "test_cover",
    "test_db",
    "test_cookies",
    "test_webpublisher",
    "test_humanize",
    "test_article",
    "test_pipeline",
]


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    failed: list[str] = []
    passed = 0
    for m in MODULES:
        mod = importlib.import_module(m)
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"  PASS  {m}.{name}")
            except Exception:
                failed.append(f"{m}.{name}")
                print(f"  FAIL  {m}.{name}")
                traceback.print_exc()
    print(f"\n通过 {passed} 个，失败 {len(failed)} 个")
    if failed:
        print("失败列表:", failed)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

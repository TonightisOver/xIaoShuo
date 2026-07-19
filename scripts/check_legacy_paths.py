"""旧服务路径残留检查：断言废弃路径/符号不再出现于 src/ 内。

退出码 0 = 干净；非 0 = 发现残留，需人工清理。
用法：python scripts/check_legacy_paths.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

# 已废弃的模块路径片段/符号；一旦在 src/ 下命中即视为残留。
LEGACY_MARKERS: list[str] = [
    # 示例占位：按实际拆分历史填入真实废弃路径
    # "src.api.services.novel_generator",   # 已拆分到 long_form_generation_helpers
    # "src.api.routes.old",
]

# 已废弃的顶层文件名；存在即视为残留。
LEGACY_FILES: list[str] = [
    # "src/api/routes/old_routes.py",
]


def _scan_legacy_imports() -> list[str]:
    hits: list[str] = []
    for py in SRC_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for marker in LEGACY_MARKERS:
            if marker in text:
                hits.append(f"{py.relative_to(REPO_ROOT)}: 命中废弃标记 {marker!r}")
    return hits


def _scan_legacy_files() -> list[str]:
    hits: list[str] = []
    for f in LEGACY_FILES:
        if (REPO_ROOT / f).exists():
            hits.append(f"废弃文件仍存在: {f}")
    return hits


def main() -> int:
    hits = _scan_legacy_imports() + _scan_legacy_files()
    if not hits:
        print("legacy-paths: OK (无残留)")
        return 0
    print("legacy-paths: FAIL —— 发现旧路径残留：")
    for h in hits:
        print(f"  - {h}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

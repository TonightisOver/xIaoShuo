"""压测配置：从环境变量和 seed.json 加载参数"""

import json
import os
from pathlib import Path

HOST = os.environ.get("LOADTEST_HOST", "http://115.190.142.169:8000")

DATA_DIR = Path(__file__).parent / "data"
_seed_path = DATA_DIR / "seed.json"

if _seed_path.exists():
    with _seed_path.open(encoding="utf-8") as _f:
        _seed = json.load(_f)
else:
    _seed = {"novel_ids": [], "chapter_numbers": [], "task_ids": []}

NOVEL_IDS: list[str] = _seed.get("novel_ids", [])
CHAPTER_NUMBERS: list[int] = _seed.get("chapter_numbers", [])
TASK_IDS: list[str] = _seed.get("task_ids", [])

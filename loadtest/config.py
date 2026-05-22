"""压测配置：从环境变量和 seed.json 加载参数"""

import json
import os
from pathlib import Path

HOST = os.environ.get("LOADTEST_HOST", "http://localhost:8000")

_seed_path = Path(__file__).parent / "data" / "seed.json"
with _seed_path.open(encoding="utf-8") as _f:
    _seed = json.load(_f)

NOVEL_IDS: list[str] = _seed["novel_ids"]
CHAPTER_NUMBERS: list[int] = _seed["chapter_numbers"]

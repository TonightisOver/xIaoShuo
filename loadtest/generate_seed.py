"""从目标服务器拉取 seed 数据，生成 loadtest/data/seed.json

用法：
  python loadtest/generate_seed.py
  python loadtest/generate_seed.py --host http://115.190.142.169:8000
"""

import argparse
import json
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"


def main():
    parser = argparse.ArgumentParser(description="Generate seed data for load tests")
    parser.add_argument("--host", default="http://115.190.142.169:8000")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    seed = {"novel_ids": [], "chapter_numbers": [], "task_ids": []}

    # Fetch novels
    print(f"Fetching novels from {host}...")
    resp = requests.get(f"{host}/api/v1/projects", timeout=10)
    if resp.status_code != 200:
        print(f"Failed to fetch novels: {resp.status_code}")
        sys.exit(1)

    novels = resp.json().get("novels", [])
    if not novels:
        print("No novels found, seed will be empty")
    else:
        seed["novel_ids"] = [n["novel_id"] for n in novels]
        print(f"  Found {len(seed['novel_ids'])} novels")

    # Fetch chapters for first novel
    if seed["novel_ids"]:
        novel_id = seed["novel_ids"][0]
        resp = requests.get(f"{host}/api/v1/projects/{novel_id}/chapters", timeout=10)
        if resp.status_code == 200:
            chapters = resp.json() if isinstance(resp.json(), list) else resp.json().get("chapters", [])
            seed["chapter_numbers"] = sorted(set(
                ch["chapter_number"] for ch in chapters if ch.get("chapter_number")
            ))
            print(f"  Found {len(seed['chapter_numbers'])} chapters")

    # Fetch recent tasks
    resp = requests.get(f"{host}/api/v1/novels", params={"limit": 10}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        tasks = data.get("tasks", [])
        seed["task_ids"] = [t["task_id"] for t in tasks if t.get("task_id")]
        print(f"  Found {len(seed['task_ids'])} tasks")

    # Write seed
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed_path = DATA_DIR / "seed.json"
    seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSeed written to {seed_path}")


if __name__ == "__main__":
    main()

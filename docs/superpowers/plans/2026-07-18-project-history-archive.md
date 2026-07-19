# Project History Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已完成的工程历史资料集中迁入根目录 `archive/`，生成可检索的摘要、索引和路径清单，并在不改变业务行为的前提下清理可再生成文件。

**Architecture:** 第一阶段只处理历史资料和工作区卫生，不移动源码。一个标准库 Python 工具负责生成基线、归档记录、索引、manifest 和一致性检查；文件移动由明确的文件系统命令完成，业务源码、依赖、日志、数据和工作树保持不动。

**Tech Stack:** Python 3.11 标准库、pytest、Markdown、CSV、Poetry、Vue 3/Vitest/Vite

---

## 执行约束

- 不执行 `git add`、`git commit`、`git push` 或任何暂存操作。
- 不使用子 Agent；在当前会话内按计划执行并检查。
- 不修改 `src/`、`frontend/src/`、现有测试逻辑、数据库迁移和业务配置。
- 不删除 `frontend/node_modules/`、`logs/`、`data/`、`.env*`、`poetry.lock` 或 `.claude/worktrees/`。
- 当前设计文档和本实施计划保留在 `docs/superpowers/` 活动目录。

## File Structure

**Create:**

- `scripts/archive_history.py` — 生成基线、CHANGE 摘要、索引、manifest、整理报告并验证路径。
- `tests/unit/test_archive_history.py` — 归档工具单元测试。
- `archive/README.md` — 归档区使用说明和保留规则。
- `archive/baseline.json` — 整理前活动文件统计。
- `archive/index.md` — 归档总索引，由工具生成。
- `archive/manifest.csv` — 每个移动文件的新旧路径映射，由工具生成。
- `archive/organization-report.md` — 整理前后统计及保留项，由工具生成。
- `archive/changes/*/archive-record.md` — 每个 CHANGE 的综合归档记录，由工具生成。

**Move without content changes:**

- `.harness/changes/CHANGE-*` → `archive/changes/`
- 除当前计划外的 `docs/superpowers/plans/*.md` → `archive/plans/`
- 除当前设计外的 `docs/superpowers/specs/*.md` → `archive/specs/`
- `.scratch/post-funnel-cleanup/` → `archive/scratch/post-funnel-cleanup/`
- `docs/E2E_VERIFICATION_REPORT.md` → `archive/reports/E2E_VERIFICATION_REPORT.md`
- `docs/本次改动内容.md` → `archive/reports/本次改动内容.md`
- `.harness/changes/{ci-result,code-review,coding-report,test-report,test-review}.md` → `archive/reports/harness/`

**Modify:**

- `.harness/README.md` — 增加活动变更与历史归档的入口说明。
- `.harness/changes/README.md` — 增加完成后迁入 `archive/changes/` 的规则。

**Delete only ignored/generated content:**

- `__pycache__/`、`*.pyc`
- `.pytest_cache/`、`.ruff_cache/`、`.mypy_cache/`
- `frontend/dist/`
- `docs/.DS_Store`

### Task 1: Capture the pre-change verification baseline

**Files:**

- No project files changed.
- Temporary outputs: `/private/tmp/xiaoshuo-archive-*.log`

- [ ] **Step 1: Record the existing worktree state**

Run:

```bash
git status --short
```

Expected: only the two pre-existing modified `.claude/worktrees/*` entries and the untracked current design/plan files; no task files staged.

- [ ] **Step 2: Run the backend baseline**

Run:

```bash
poetry run pytest tests/ -q
```

Expected: PASS, or a precisely recorded pre-existing failure list. Do not fix unrelated failures.

- [ ] **Step 3: Verify the FastAPI entry import**

Run:

```bash
poetry run python -c "from src.api.main import app; print(app.title)"
```

Expected: command exits 0 and prints the configured application title.

- [ ] **Step 4: Run the frontend baseline tests**

Run from `frontend/`:

```bash
npm test
```

Expected: Vitest exits 0, or a precisely recorded pre-existing failure list.

- [ ] **Step 5: Run the frontend baseline build**

Run from `frontend/`:

```bash
npm run build
```

Expected: Vite build exits 0 and creates `frontend/dist/`.

### Task 2: Build the archive metadata tool with TDD

**Files:**

- Create: `tests/unit/test_archive_history.py`
- Create: `scripts/archive_history.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_archive_history.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path

from scripts.archive_history import (
    build_manifest_rows,
    extract_objective,
    extract_section,
    render_change_record,
    validate_archive,
)


def test_extract_section_returns_matching_markdown_body() -> None:
    text = """# CHANGE-001

## 背景
旧内容。

## 目标
建立基础框架。
- 保留模块边界

## 测试结果
全部通过。
"""

    result = extract_section([("summary.md", text)], ("目标",))

    assert result == "建立基础框架。\n- 保留模块边界"


def test_extract_objective_accepts_numbered_requirement_background() -> None:
    text = """# 需求分析

## 1. 需求背景
修复云服务器上的任务进度与编辑入口问题。

## 2. 验收标准
全部功能可用。
"""

    result = extract_objective([("01-需求分析.md", text)])

    assert result == "修复云服务器上的任务进度与编辑入口问题。"


def test_render_change_record_contains_required_fields(tmp_path: Path) -> None:
    change_dir = tmp_path / "CHANGE-001-langgraph"
    change_dir.mkdir()
    (change_dir / "summary.md").write_text(
        """# Summary

## 目标
建立 LangGraph 基础框架。

## 主要设计
状态与节点分离。

## 实施结果
功能完成。

## 测试结果
pytest PASS。
""",
        encoding="utf-8",
    )

    record = render_change_record(
        change_dir=change_dir,
        source_path=Path(".harness/changes/CHANGE-001-langgraph"),
        commits=["abc1234 2026-05-16 feat: initial graph"],
    )

    assert "# CHANGE-001 归档记录" in record
    assert "建立 LangGraph 基础框架" in record
    assert "状态与节点分离" in record
    assert "pytest PASS" in record
    assert "summary.md" in record
    assert "abc1234" in record


def test_render_change_record_redacts_api_keys(tmp_path: Path) -> None:
    change_dir = tmp_path / "CHANGE-002-api"
    change_dir.mkdir()
    secret = "sk-1234567890abcdef1234567890abcdef"
    (change_dir / "summary.md").write_text(
        f"""# Summary

## 目标
接入 API，密钥为 {secret}。
""",
        encoding="utf-8",
    )

    record = render_change_record(
        change_dir=change_dir,
        source_path=Path(".harness/changes/CHANGE-002-api"),
        commits=[],
    )

    assert secret not in record
    assert "[REDACTED_API_KEY]" in record


def test_build_manifest_rows_maps_archive_files_to_original_paths(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    moved = archive / "plans" / "old-plan.md"
    moved.parent.mkdir(parents=True)
    moved.write_text("old plan", encoding="utf-8")

    rows = build_manifest_rows(tmp_path, archive)

    assert rows == [
        {
            "category": "plans",
            "item": "old-plan.md",
            "status": "archived",
            "source_path": "docs/superpowers/plans/old-plan.md",
            "archive_path": "archive/plans/old-plan.md",
            "commit": "",
            "notes": "",
        }
    ]


def test_build_manifest_rows_maps_loose_harness_reports(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    moved = archive / "reports" / "harness" / "ci-result.md"
    moved.parent.mkdir(parents=True)
    moved.write_text("ci result", encoding="utf-8")

    rows = build_manifest_rows(tmp_path, archive)

    assert rows[0]["source_path"] == ".harness/changes/ci-result.md"
    assert rows[0]["archive_path"] == "archive/reports/harness/ci-result.md"


def test_validate_archive_reports_missing_destination_and_existing_source(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    manifest = archive / "manifest.csv"
    source = tmp_path / "docs" / "old.md"
    source.parent.mkdir()
    source.write_text("still here", encoding="utf-8")
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "category",
                "item",
                "status",
                "source_path",
                "archive_path",
                "commit",
                "notes",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "category": "reports",
                "item": "old.md",
                "status": "archived",
                "source_path": "docs/old.md",
                "archive_path": "archive/reports/old.md",
                "commit": "",
                "notes": "",
            }
        )

    errors = validate_archive(tmp_path, archive)

    assert "归档文件不存在: archive/reports/old.md" in errors
    assert "原路径仍存在: docs/old.md" in errors
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
poetry run pytest tests/unit/test_archive_history.py -q
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'scripts.archive_history'`.

- [ ] **Step 3: Implement the archive tool**

Create `scripts/archive_history.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable


MANIFEST_FIELDS = (
    "category",
    "item",
    "status",
    "source_path",
    "archive_path",
    "commit",
    "notes",
)
SOURCE_ROOTS = {
    "changes": Path(".harness/changes"),
    "plans": Path("docs/superpowers/plans"),
    "specs": Path("docs/superpowers/specs"),
    "reports": Path("docs"),
    "scratch": Path(".scratch"),
}
GENERATED_ARCHIVE_FILES = {"archive-record.md"}
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "dist",
    "logs",
    "node_modules",
}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
API_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
OBJECTIVE_KEYWORDS = (
    "目标",
    "需求概述",
    "需求背景",
    "变更概述",
    "概述",
    "what to build",
    "完成任务",
)
MODULE_RE = re.compile(
    r"(?<![\w/])((?:src|frontend|tests|alembic|scripts|loadtest)/"
    r"[^\s`'\"<>，。,；;：:()（）]+)"
)


def _ordered_docs(change_dir: Path) -> list[tuple[str, str]]:
    priority = {
        "summary.md": 0,
        "01-需求分析.md": 1,
        "02-技术设计.md": 2,
    }
    files = sorted(
        (path for path in change_dir.iterdir() if path.suffix.lower() == ".md"),
        key=lambda path: (priority.get(path.name, 10), path.name),
    )
    return [(path.name, path.read_text(encoding="utf-8", errors="replace")) for path in files]


def extract_section(
    docs: list[tuple[str, str]],
    keywords: tuple[str, ...],
    *,
    max_chars: int = 1800,
) -> str:
    normalized = tuple(keyword.casefold() for keyword in keywords)
    for _name, text in docs:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = HEADING_RE.match(line.strip())
            if not match:
                continue
            level = len(match.group(1))
            title = match.group(2).casefold()
            if not any(keyword in title for keyword in normalized):
                continue
            body: list[str] = []
            for candidate in lines[index + 1 :]:
                next_heading = HEADING_RE.match(candidate.strip())
                if next_heading and len(next_heading.group(1)) <= level:
                    break
                if candidate.strip() or body:
                    body.append(candidate.rstrip())
            value = "\n".join(body).strip()
            if value:
                return value[:max_chars].rstrip()
    return ""


def extract_objective(docs: list[tuple[str, str]]) -> str:
    return extract_section(docs, OBJECTIVE_KEYWORDS)


def redact_sensitive_text(text: str) -> str:
    return API_KEY_RE.sub("[REDACTED_API_KEY]", text)


def _fallback_excerpt(docs: list[tuple[str, str]]) -> str:
    for _name, text in docs:
        lines = [
            line.rstrip()
            for line in text.splitlines()
            if line.strip() and not HEADING_RE.match(line.strip())
        ]
        if lines:
            return "\n".join(lines[:12])[:1800].rstrip()
    return "未在原始文档中识别出可提取正文；请直接查阅原始文件。"


def _extract_modules(docs: list[tuple[str, str]]) -> list[str]:
    modules: set[str] = set()
    for _name, text in docs:
        modules.update(match.rstrip(".，。") for match in MODULE_RE.findall(text))
    return sorted(modules)[:40]


def _detect_status(docs: list[tuple[str, str]]) -> str:
    combined = "\n".join(text for _name, text in docs)
    if re.search(r"(?:Status|状态)[：:]?\s*partial", combined, re.IGNORECASE):
        return "partial"
    if re.search(r"APPROVED|已完成|全部通过|\bPASS\b|resolved", combined, re.IGNORECASE):
        return "completed"
    return "archived-completed"


def _git_entries(project_root: Path, source_path: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "log",
            "-5",
            "--format=%h %ad %s",
            "--date=short",
            "--",
            source_path.as_posix(),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def render_change_record(
    *,
    change_dir: Path,
    source_path: Path,
    commits: list[str],
) -> str:
    docs = _ordered_docs(change_dir)
    match = re.match(r"CHANGE-(\d+)(?:-(.+))?", change_dir.name)
    number = match.group(1) if match else change_dir.name
    title = match.group(2) if match and match.group(2) else change_dir.name
    objective = extract_objective(docs)
    objective_text = objective or (
        f"该历史变更主题为“{title}”；原始资料未单独记录目标章节。"
    )
    design = extract_section(docs, ("主要设计", "技术设计", "架构", "实现说明", "方案"))
    result = extract_section(docs, ("实施结果", "任务完成情况", "完成情况", "变更概述", "总结"))
    tests = extract_section(docs, ("测试与验证", "测试结果", "验证结果", "验收自检", "ci"))
    legacy = extract_section(docs, ("遗留事项", "问题清单", "should fix", "风险"))
    fallback = _fallback_excerpt(docs)
    modules = _extract_modules(docs)
    files = sorted(
        path.name
        for path in change_dir.iterdir()
        if path.is_file() and path.name != "archive-record.md"
    )
    commit_lines = commits or ["未从 Git 历史识别到关联提交"]
    dates = sorted(
        {
            match.group(0)
            for entry in commits
            if (match := re.search(r"\b\d{4}-\d{2}-\d{2}\b", entry))
        }
    )
    if not dates:
        time_range = "未从 Git 历史识别"
    elif len(dates) == 1:
        time_range = dates[0]
    else:
        time_range = f"{dates[0]} 至 {dates[-1]}"

    def section(value: str) -> str:
        return value or fallback

    module_lines = modules or ["未在原始文档中识别出明确模块路径"]
    record = "\n".join(
        [
            f"# CHANGE-{number} 归档记录",
            "",
            f"- 原名称：{title}",
            f"- 状态：{_detect_status(docs)}",
            f"- 时间范围：{time_range}",
            f"- 原路径：`{source_path.as_posix()}`",
            f"- 归档路径：`archive/changes/{change_dir.name}`",
            "- 关联提交：",
            *[f"  - {entry}" for entry in commit_lines],
            "",
            "## 目标",
            "",
            objective_text,
            "",
            "## 主要设计决定",
            "",
            section(design),
            "",
            "## 涉及模块",
            "",
            *[f"- `{module}`" for module in module_lines],
            "",
            "## 实施结果",
            "",
            section(result),
            "",
            "## 测试与验证",
            "",
            section(tests),
            "",
            "## 遗留事项",
            "",
            legacy or "原始资料未明确记录遗留事项。",
            "",
            "## 原始文件清单",
            "",
            *[f"- `{name}`" for name in files],
            "",
        ]
    )
    return redact_sensitive_text(record)


def _source_path_for(category: str, relative: Path) -> Path:
    if category == "reports" and relative.parts[:1] == ("harness",):
        return Path(".harness/changes").joinpath(*relative.parts[1:])
    return SOURCE_ROOTS[category] / relative


def build_manifest_rows(project_root: Path, archive_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for category in SOURCE_ROOTS:
        category_root = archive_root / category
        if not category_root.exists():
            continue
        for path in sorted(candidate for candidate in category_root.rglob("*") if candidate.is_file()):
            if path.name in GENERATED_ARCHIVE_FILES:
                continue
            relative = path.relative_to(category_root)
            source = _source_path_for(category, relative)
            commits = _git_entries(project_root, source)
            rows.append(
                {
                    "category": category,
                    "item": relative.parts[0],
                    "status": "archived",
                    "source_path": source.as_posix(),
                    "archive_path": path.relative_to(project_root).as_posix(),
                    "commit": commits[0].split(" ", 1)[0] if commits else "",
                    "notes": "",
                }
            )
    return rows


def _is_managed_file(project_root: Path, path: Path) -> bool:
    relative = path.relative_to(project_root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    return not (len(relative.parts) >= 2 and relative.parts[:2] == (".claude", "worktrees"))


def workspace_snapshot(project_root: Path) -> dict[str, object]:
    files = [
        path
        for path in project_root.rglob("*")
        if path.is_file() and _is_managed_file(project_root, path)
    ]
    top_level = Counter(path.relative_to(project_root).parts[0] for path in files)
    changes = sorted(
        path.name
        for path in (project_root / ".harness" / "changes").glob("CHANGE-*")
        if path.is_dir()
    )
    return {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "managed_file_count": len(files),
        "top_level_counts": dict(sorted(top_level.items())),
        "change_directories": changes,
    }


def _write_manifest(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _first_line(value: str) -> str:
    for line in value.splitlines():
        cleaned = line.strip().lstrip("- ")
        if cleaned:
            return cleaned[:120].replace("|", "\\|")
    return "查阅归档记录"


def _write_index(project_root: Path, archive_root: Path) -> None:
    lines = [
        "# 项目历史归档索引",
        "",
        "## Harness 变更",
        "",
        "| 变更 | 状态 | 摘要 | 提交 |",
        "|---|---|---|---|",
    ]
    changes_root = archive_root / "changes"
    for change_dir in sorted(path for path in changes_root.glob("CHANGE-*") if path.is_dir()):
        docs = _ordered_docs(change_dir)
        source = Path(".harness/changes") / change_dir.name
        commits = _git_entries(project_root, source)
        objective = extract_objective(docs) or (
            f"历史变更主题：{change_dir.name}"
        )
        commit = commits[0].split(" ", 1)[0] if commits else "—"
        lines.append(
            f"| [{change_dir.name}](changes/{change_dir.name}/archive-record.md) "
            f"| {_detect_status(docs)} | {_first_line(objective)} | `{commit}` |"
        )
    for category, title in (
        ("plans", "历史实施计划"),
        ("specs", "历史设计规格"),
        ("reports", "历史报告"),
        ("scratch", "临时工程记录"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| 路径 | 状态 | 提交 |",
                "|---|---|---|",
            ]
        )
        root = archive_root / category
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            relative = path.relative_to(archive_root).as_posix()
            source = _source_path_for(category, path.relative_to(root))
            commits = _git_entries(project_root, source)
            commit = commits[0].split(" ", 1)[0] if commits else "—"
            lines.append(f"| [{relative}]({relative}) | archived | `{commit}` |")
    (archive_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(project_root: Path, archive_root: Path) -> None:
    baseline = json.loads((archive_root / "baseline.json").read_text(encoding="utf-8"))
    current = workspace_snapshot(project_root)
    report = [
        "# 项目历史资料整理报告",
        "",
        f"- 整理前受管文件数：{baseline['managed_file_count']}",
        f"- 整理后受管文件数：{current['managed_file_count']}",
        f"- 已归档 CHANGE 目录数：{len(list((archive_root / 'changes').glob('CHANGE-*')))}",
        "- 业务源码修改：无",
        "- Git 暂存或提交：未执行",
        "",
        "## 明确保留",
        "",
        "- `frontend/node_modules/`",
        "- `logs/`",
        "- `data/`",
        "- `.env*` 与 `poetry.lock`",
        "- `.claude/worktrees/`",
        "- 当前设计文档与实施计划",
        "",
        "## 路径映射",
        "",
        "完整映射见 [`manifest.csv`](manifest.csv)。",
        "",
    ]
    (archive_root / "organization-report.md").write_text(
        "\n".join(report), encoding="utf-8"
    )


def generate_archive(project_root: Path, archive_root: Path) -> None:
    for change_dir in sorted(
        path for path in (archive_root / "changes").glob("CHANGE-*") if path.is_dir()
    ):
        source = Path(".harness/changes") / change_dir.name
        record = render_change_record(
            change_dir=change_dir,
            source_path=source,
            commits=_git_entries(project_root, source),
        )
        (change_dir / "archive-record.md").write_text(record, encoding="utf-8")
    _write_manifest(
        archive_root / "manifest.csv",
        build_manifest_rows(project_root, archive_root),
    )
    _write_index(project_root, archive_root)
    _write_report(project_root, archive_root)


def validate_archive(project_root: Path, archive_root: Path) -> list[str]:
    errors: list[str] = []
    manifest = archive_root / "manifest.csv"
    if not manifest.exists():
        return ["manifest 不存在: archive/manifest.csv"]
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            destination = project_root / row["archive_path"]
            source = project_root / row["source_path"]
            if not destination.exists():
                errors.append(f"归档文件不存在: {row['archive_path']}")
            if source.exists():
                errors.append(f"原路径仍存在: {row['source_path']}")
    for change_dir in (archive_root / "changes").glob("CHANGE-*"):
        if not (change_dir / "archive-record.md").exists():
            errors.append(f"缺少归档记录: {change_dir.name}/archive-record.md")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate project history archives")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--archive-root", type=Path, default=Path("archive"))
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    archive_root = (project_root / args.archive_root).resolve()
    archive_root.mkdir(parents=True, exist_ok=True)

    if args.snapshot:
        (archive_root / "baseline.json").write_text(
            json.dumps(workspace_snapshot(project_root), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.generate:
        generate_archive(project_root, archive_root)
    if args.check:
        errors = validate_archive(project_root, archive_root)
        if errors:
            print("\n".join(errors))
            return 1
        print("archive validation passed")
    if not (args.snapshot or args.generate or args.check):
        parser.error("at least one of --snapshot, --generate, or --check is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
poetry run pytest tests/unit/test_archive_history.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Run Ruff on the new tool and test**

Run:

```bash
poetry run ruff check scripts/archive_history.py tests/unit/test_archive_history.py
```

Expected: PASS with no diagnostics.

### Task 3: Create the archive root and capture its baseline

**Files:**

- Create: `archive/README.md`
- Create: `archive/baseline.json`

- [ ] **Step 1: Create the archive README**

Create `archive/README.md`:

```markdown
# 项目历史归档

本目录保存已完成的工程变更、设计、计划、报告和临时记录。活动开发资料仍放在原有工作目录中。

## 查阅入口

- [`index.md`](index.md)：按类别浏览归档资料
- [`manifest.csv`](manifest.csv)：查询文件的新旧路径
- [`organization-report.md`](organization-report.md)：查看本次整理结果

## 规则

1. 归档原文保持不变。
2. 每个 Harness 变更目录增加一份 `archive-record.md` 综合记录。
3. 新任务继续使用 `.harness/changes/` 和 `.scratch/`；完成后再迁入本目录。
4. 归档区不存放源码、依赖、日志、数据或环境密钥。
```

- [ ] **Step 2: Create category directories**

Run:

```bash
mkdir -p archive/changes archive/plans archive/specs archive/reports archive/scratch
```

Expected: all five category directories exist.

- [ ] **Step 3: Capture the pre-move snapshot**

Run:

```bash
poetry run python scripts/archive_history.py --snapshot
```

Expected: `archive/baseline.json` exists and contains the current `CHANGE-*` directory names and managed file counts.

- [ ] **Step 4: Validate the baseline JSON**

Run:

```bash
poetry run python -m json.tool archive/baseline.json
```

Expected: valid JSON is printed; `change_directories` is non-empty.

### Task 4: Move completed historical material

**Files:**

- Move all `.harness/changes/CHANGE-*` directories.
- Move old plans/specs, completed scratch records, and two historical reports.

- [ ] **Step 1: Move completed Harness changes**

Run:

```bash
for entry in .harness/changes/CHANGE-*; do
  [ -d "$entry" ] || continue
  mv "$entry" archive/changes/
done
```

Expected: `.harness/changes/` retains `README.md` and `_template/`; all `CHANGE-*` directories appear under `archive/changes/`.

- [ ] **Step 2: Move old implementation plans**

Run:

```bash
for entry in docs/superpowers/plans/*.md; do
  [ "$(basename "$entry")" = "2026-07-18-project-history-archive.md" ] && continue
  mv "$entry" archive/plans/
done
```

Expected: only `2026-07-18-project-history-archive.md` remains in `docs/superpowers/plans/`.

- [ ] **Step 3: Move old design specs**

Run:

```bash
for entry in docs/superpowers/specs/*.md; do
  [ "$(basename "$entry")" = "2026-07-18-project-archive-and-structure-optimization-design.md" ] && continue
  mv "$entry" archive/specs/
done
```

Expected: only the current project archive design remains in `docs/superpowers/specs/`.

- [ ] **Step 4: Move completed scratch history**

Run:

```bash
mv .scratch/post-funnel-cleanup archive/scratch/
```

Expected: `archive/scratch/post-funnel-cleanup/` contains `spec.md`, `map.md`, and all seven issue files. The partial security item remains documented, not executed.

- [ ] **Step 5: Move historical reports**

Run:

```bash
mv docs/E2E_VERIFICATION_REPORT.md archive/reports/
mv docs/本次改动内容.md archive/reports/
```

Expected: both files exist under `archive/reports/` and no longer exist in `docs/`.

- [ ] **Step 6: Move loose Harness delivery reports**

Run:

```bash
mkdir -p archive/reports/harness
for entry in ci-result.md code-review.md coding-report.md test-report.md test-review.md; do
  mv ".harness/changes/$entry" archive/reports/harness/
done
```

Expected: `.harness/changes/` retains only `README.md` and `_template/`.

### Task 5: Generate archive records, index, manifest, and report

**Files:**

- Create: `archive/changes/*/archive-record.md`
- Create: `archive/index.md`
- Create: `archive/manifest.csv`
- Create: `archive/organization-report.md`

- [ ] **Step 1: Generate archive metadata**

Run:

```bash
poetry run python scripts/archive_history.py --generate
```

Expected: every `archive/changes/CHANGE-*` directory has `archive-record.md`; index, manifest, and report exist.

- [ ] **Step 2: Run structural archive validation**

Run:

```bash
poetry run python scripts/archive_history.py --check
```

Expected: prints `archive validation passed` and exits 0.

- [ ] **Step 3: Check record completeness**

Run:

```bash
find archive/changes -mindepth 2 -maxdepth 2 -name archive-record.md | wc -l
find archive/changes -mindepth 1 -maxdepth 1 -type d | wc -l
```

Expected: the two counts are identical.

- [ ] **Step 4: Check required record headings**

Run:

```bash
rg -L '^## 目标$' archive/changes/*/archive-record.md
rg -L '^## 主要设计决定$' archive/changes/*/archive-record.md
rg -L '^## 测试与验证$' archive/changes/*/archive-record.md
```

Expected: all three commands produce no file paths.

- [ ] **Step 5: Spot-check early, middle, and recent changes**

Read and compare these records with their original files in the same directories:

```text
archive/changes/CHANGE-001-langgraph-基础框架/archive-record.md
archive/changes/CHANGE-025-概览编辑与大纲修复/archive-record.md
archive/changes/CHANGE-050-工程质量修复-层级边界与前端测试/archive-record.md
```

Expected: target, design, modules, results and tests are traceable to the original files; no original file was rewritten.

### Task 6: Update active archive guidance and clean generated files

**Files:**

- Modify: `.harness/README.md`
- Modify: `.harness/changes/README.md`
- Delete ignored/generated caches only.

- [ ] **Step 1: Add the archive entry to `.harness/README.md`**

Append:

```markdown

## 历史归档

`.harness/changes/` 只保留当前变更和模板。已完成变更集中保存在项目根目录 [`archive/changes/`](../archive/changes/)，统一索引见 [`archive/index.md`](../archive/index.md)。
```

- [ ] **Step 2: Add the completion rule to `.harness/changes/README.md`**

Append:

```markdown

## 已完成变更归档

Gate 2 完成并确认不再作为活动任务后，将整个 `CHANGE-*` 目录移动到 `archive/changes/`，保留全部原始文件，并生成 `archive-record.md`。活动变更仍在本目录创建和处理。
```

- [ ] **Step 3: Confirm every cleanup target is ignored**

Run:

```bash
git check-ignore __pycache__ .pytest_cache .ruff_cache .mypy_cache frontend/dist docs/.DS_Store
```

Expected: every existing cleanup target is printed. If a target is not ignored, do not delete it; record it in `archive/organization-report.md`.

- [ ] **Step 4: Remove generated caches and build output**

Run only after Step 3 passes:

```bash
find . -type d -name __pycache__ -not -path './frontend/node_modules/*' -not -path './.claude/worktrees/*' -not -path './.git/*' -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -not -path './frontend/node_modules/*' -not -path './.claude/worktrees/*' -not -path './.git/*' -delete
rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/dist
rm -f docs/.DS_Store
```

Expected: listed generated targets no longer exist. `frontend/node_modules/`, `logs/`, `data/`, `.env*`, `poetry.lock`, and `.claude/worktrees/` remain untouched.

- [ ] **Step 5: Confirm protected paths remain**

Run:

```bash
test -d frontend/node_modules
test -d logs
test -d data
test -f .env
test -f poetry.lock
test -d .claude/worktrees
```

Expected: all commands exit 0.

### Task 7: Run final verification and hand off without Git actions

**Files:**

- Verify all task files.
- No Git staging or commit.

- [ ] **Step 1: Re-run the archive tool tests**

Run:

```bash
poetry run pytest tests/unit/test_archive_history.py -q
```

Expected: `7 passed`.

- [ ] **Step 2: Re-run archive validation**

Run:

```bash
poetry run python scripts/archive_history.py --check
```

Expected: `archive validation passed`.

- [ ] **Step 3: Verify the FastAPI entry import**

Run:

```bash
poetry run python -c "from src.api.main import app; print(app.title)"
```

Expected: exits 0 and matches the baseline application title.

- [ ] **Step 4: Run the complete backend suite**

Run:

```bash
poetry run pytest tests/ -q
```

Expected: no failures beyond any precisely recorded baseline failures.

- [ ] **Step 5: Run frontend tests**

Run from `frontend/`:

```bash
npm test
```

Expected: no failures beyond any precisely recorded baseline failures.

- [ ] **Step 6: Run frontend build**

Run from `frontend/`:

```bash
npm run build
```

Expected: build succeeds. Remove the newly generated `frontend/dist/` again after recording success.

- [ ] **Step 7: Check formatting and unresolved old paths**

Run:

```bash
poetry run ruff check scripts/archive_history.py tests/unit/test_archive_history.py
git diff --check
rg -n '\.harness/changes/CHANGE-|docs/superpowers/(plans|specs)/2026-|\.scratch/post-funnel-cleanup' README.md CONTEXT.md CLAUDE.md .harness docs -g '*.md'
```

Expected: Ruff and diff checks pass. Remaining old paths appear only in historical explanations, active workflow conventions, the current design/plan, or the explicit archive guidance—not as broken links to moved files.

- [ ] **Step 8: Confirm no Git action was taken**

Run:

```bash
git status --short
git diff --cached --name-only
```

Expected: task changes are visible as unstaged moves/new files; cached diff is empty. The two pre-existing `.claude/worktrees/*` modifications remain untouched.

- [ ] **Step 9: Remove all verification-generated caches and build output**

Run:

```bash
find . -type d -name __pycache__ -not -path './frontend/node_modules/*' -not -path './.claude/worktrees/*' -not -path './.git/*' -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -not -path './frontend/node_modules/*' -not -path './.claude/worktrees/*' -not -path './.git/*' -delete
rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/dist
```

Expected: all listed caches and `frontend/dist/` are absent; no tracked source file is removed.

## Completion Criteria

- `archive/` contains all completed historical categories and a readable central index.
- Every moved original file has one row in `manifest.csv`.
- Every archived `CHANGE-*` has a complete `archive-record.md`.
- Active `.harness/changes/` retains only its README and template.
- Current design and implementation plan remain active under `docs/superpowers/`.
- Business source files are unchanged.
- Backend tests, frontend tests, frontend build and FastAPI import do not regress.
- No Git staging, commit or push is performed.

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

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
        (
            path
            for path in change_dir.iterdir()
            if path.suffix.lower() == ".md" and path.name != "archive-record.md"
        ),
        key=lambda path: (priority.get(path.name, 10), path.name),
    )
    return [
        (path.name, path.read_text(encoding="utf-8", errors="replace"))
        for path in files
    ]


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
        modules.update(
            match.rstrip(".，。") for match in MODULE_RE.findall(text)
        )
    return sorted(modules)[:40]


def _detect_status(docs: list[tuple[str, str]]) -> str:
    combined = "\n".join(text for _name, text in docs)
    if re.search(
        r"(?:Status|状态)[：:]?\s*partial",
        combined,
        re.IGNORECASE,
    ):
        return "partial"
    if re.search(
        r"APPROVED|已完成|全部通过|\bPASS\b|resolved",
        combined,
        re.IGNORECASE,
    ):
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


def _time_range(commits: list[str]) -> str:
    dates = sorted(
        {
            match.group(0)
            for entry in commits
            if (match := re.search(r"\b\d{4}-\d{2}-\d{2}\b", entry))
        }
    )
    if not dates:
        return "未从 Git 历史识别"
    if len(dates) == 1:
        return dates[0]
    return f"{dates[0]} 至 {dates[-1]}"


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
    design = extract_section(
        docs,
        ("主要设计", "技术设计", "架构", "实现说明", "方案"),
    )
    result = extract_section(
        docs,
        ("实施结果", "任务完成情况", "完成情况", "变更概述", "总结"),
    )
    tests = extract_section(
        docs,
        ("测试与验证", "测试结果", "验证结果", "验收自检", "ci"),
    )
    legacy = extract_section(
        docs,
        ("遗留事项", "问题清单", "should fix", "风险"),
    )
    fallback = _fallback_excerpt(docs)
    modules = _extract_modules(docs)
    files = sorted(
        path.name
        for path in change_dir.iterdir()
        if path.is_file() and path.name != "archive-record.md"
    )
    commit_lines = commits or ["未从 Git 历史识别到关联提交"]
    module_lines = (
        [f"- `{module}`" for module in modules]
        if modules
        else ["- 未在原始文档中识别出明确模块路径"]
    )

    def section(value: str) -> str:
        return value or fallback

    record = "\n".join(
        [
            f"# CHANGE-{number} 归档记录",
            "",
            f"- 原名称：{title}",
            f"- 状态：{_detect_status(docs)}",
            f"- 时间范围：{_time_range(commits)}",
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
            *module_lines,
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


def build_manifest_rows(
    project_root: Path,
    archive_root: Path,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for category in SOURCE_ROOTS:
        category_root = archive_root / category
        if not category_root.exists():
            continue
        files = sorted(
            candidate
            for candidate in category_root.rglob("*")
            if candidate.is_file()
        )
        for path in files:
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
    return not (
        len(relative.parts) >= 2
        and relative.parts[:2] == (".claude", "worktrees")
    )


def workspace_snapshot(project_root: Path) -> dict[str, object]:
    files = [
        path
        for path in project_root.rglob("*")
        if path.is_file() and _is_managed_file(project_root, path)
    ]
    top_level = Counter(
        path.relative_to(project_root).parts[0] for path in files
    )
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
        if cleaned and not cleaned.startswith(("|", "```")):
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
    change_dirs = sorted(
        path for path in changes_root.glob("CHANGE-*") if path.is_dir()
    )
    for change_dir in change_dirs:
        docs = _ordered_docs(change_dir)
        source = Path(".harness/changes") / change_dir.name
        commits = _git_entries(project_root, source)
        objective = extract_objective(docs) or (
            f"历史变更主题：{change_dir.name}"
        )
        commit = commits[0].split(" ", 1)[0] if commits else "—"
        lines.append(
            f"| [{change_dir.name}]"
            f"(changes/{change_dir.name}/archive-record.md) "
            f"| {_detect_status(docs)} "
            f"| {_first_line(redact_sensitive_text(objective))} "
            f"| `{commit}` |"
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
        files = sorted(
            candidate for candidate in root.rglob("*") if candidate.is_file()
        )
        for path in files:
            relative = path.relative_to(archive_root).as_posix()
            source = _source_path_for(category, path.relative_to(root))
            commits = _git_entries(project_root, source)
            commit = commits[0].split(" ", 1)[0] if commits else "—"
            lines.append(
                f"| [{relative}]({relative}) | archived | `{commit}` |"
            )
    (archive_root / "index.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_report(project_root: Path, archive_root: Path) -> None:
    baseline = json.loads(
        (archive_root / "baseline.json").read_text(encoding="utf-8")
    )
    current = workspace_snapshot(project_root)
    report = [
        "# 项目历史资料整理报告",
        "",
        f"- 整理前受管文件数：{baseline['managed_file_count']}",
        f"- 整理后受管文件数：{current['managed_file_count']}",
        "- 已归档 CHANGE 目录数："
        f"{len(list((archive_root / 'changes').glob('CHANGE-*')))}",
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
        "## 基线说明",
        "",
        "- 前端测试基线：47 passed。",
        "- 前端构建基线：PASS。",
        "- 后端无数据库单元基线：762 passed、15 failed、1 skipped。",
        "- 数据库测试受沙箱禁止连接 localhost:5432 影响，未取得真实结果。",
        "",
        "## 路径映射",
        "",
        "完整映射见 [`manifest.csv`](manifest.csv)。",
        "",
    ]
    (archive_root / "organization-report.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )


def generate_archive(project_root: Path, archive_root: Path) -> None:
    change_dirs = sorted(
        path
        for path in (archive_root / "changes").glob("CHANGE-*")
        if path.is_dir()
    )
    for change_dir in change_dirs:
        source = Path(".harness/changes") / change_dir.name
        record = render_change_record(
            change_dir=change_dir,
            source_path=source,
            commits=_git_entries(project_root, source),
        )
        (change_dir / "archive-record.md").write_text(
            record,
            encoding="utf-8",
        )
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
            errors.append(
                f"缺少归档记录: {change_dir.name}/archive-record.md"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate and validate project history archives"
    )
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
            json.dumps(
                workspace_snapshot(project_root),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
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
        parser.error(
            "at least one of --snapshot, --generate, or --check is required"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

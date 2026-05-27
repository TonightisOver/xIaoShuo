"""Unit tests for CHANGE-050: 工程质量修复 — 层级边界与前端测试。

覆盖模块:
- src/api/services/novel_context_service.py (NovelContextBuilder 实现)
- 层级边界静态检查（src/core/** 不允许任何 src.api import）
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _collect_imports(filepath: Path) -> list[str]:
    """解析 Python 文件，返回所有 import 语句中的模块名列表。"""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


# ---------------------------------------------------------------------------
# 1. 层级边界静态检查 — src/core 不得 import src.api
# ---------------------------------------------------------------------------


class TestLayerBoundary:
    """验证 core 层不向上依赖 api 层（任何子模块）。"""

    def test_core_context_package_does_not_exist(self):
        """src/core/context/ 包已删除，不再存在 re-export stub。"""
        context_dir = PROJECT_ROOT / "src" / "core" / "context"
        assert not context_dir.exists(), (
            f"src/core/context/ 应已删除，但仍存在: {context_dir}"
        )

    def test_core_has_no_api_imports(self):
        """src/core/ 下所有 .py 文件不得 import src.api（任何子路径）。"""
        core_dir = PROJECT_ROOT / "src" / "core"
        assert core_dir.exists(), f"目录不存在: {core_dir}"

        violations: list[str] = []
        for py_file in core_dir.glob("**/*.py"):
            for mod in _collect_imports(py_file):
                if mod.startswith("src.api"):
                    violations.append(
                        f"{py_file.relative_to(PROJECT_ROOT)}: imports {mod}"
                    )

        assert not violations, (
            "core 层不应导入 api 层（任何子路径），违规文件:\n"
            + "\n".join(violations)
        )

    def test_core_llm_files_do_not_import_api_models(self):
        """src/core/llm/ 下的文件不导入 src.api.models。"""
        llm_dir = PROJECT_ROOT / "src" / "core" / "llm"
        assert llm_dir.exists(), f"目录不存在: {llm_dir}"

        violations: list[str] = []
        for py_file in llm_dir.glob("**/*.py"):
            for mod in _collect_imports(py_file):
                if mod.startswith("src.api.models"):
                    violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: imports {mod}")

        assert not violations, (
            "core/llm 层不应导入 api.models，违规文件:\n" + "\n".join(violations)
        )

    def test_core_langgraph_nodes_do_not_import_api_services(self):
        """src/core/langgraph/nodes/ 下的文件不导入 src.api.services。"""
        nodes_dir = PROJECT_ROOT / "src" / "core" / "langgraph" / "nodes"
        assert nodes_dir.exists(), f"目录不存在: {nodes_dir}"

        violations: list[str] = []
        for py_file in nodes_dir.glob("**/*.py"):
            for mod in _collect_imports(py_file):
                if mod.startswith("src.api.services"):
                    violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: imports {mod}")

        assert not violations, (
            "core/langgraph/nodes 层不应导入 api.services，违规文件:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 2. NovelContextBuilder 导入路径测试
# ---------------------------------------------------------------------------


class TestNovelContextBuilderImport:
    """验证 NovelContextBuilder 只从 api.services 层导入。"""

    def test_import_from_api_services(self):
        """从 src.api.services.novel_context_service 导入 NovelContextBuilder 成功。"""
        from src.api.services.novel_context_service import NovelContextBuilder

        assert NovelContextBuilder is not None

    def test_import_context_dataclasses_from_api_services(self):
        """从 src.api.services.novel_context_service 导入三个 Context dataclass 成功。"""
        from src.api.services.novel_context_service import (
            BlueprintContext,
            GenerationContext,
            RewriteContext,
        )

        assert GenerationContext is not None
        assert RewriteContext is not None
        assert BlueprintContext is not None

    def test_core_context_package_not_importable(self):
        """src.core.context 包已删除，不可导入。"""
        import importlib

        spec = importlib.util.find_spec("src.core.context")
        assert spec is None, (
            "src.core.context 包应已删除，但仍可被 importlib 找到"
        )


# ---------------------------------------------------------------------------
# 3. NovelContextBuilder 基本功能测试（mock AsyncSession）
# ---------------------------------------------------------------------------


class TestNovelContextBuilderBasic:
    """NovelContextBuilder 基本接口验证（不需要真实 DB）。"""

    @pytest.fixture
    def builder(self):
        from src.api.services.novel_context_service import NovelContextBuilder

        return NovelContextBuilder()

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    def test_instantiation_succeeds(self, builder):
        """NovelContextBuilder 可以无参数实例化。"""
        assert builder is not None

    def test_build_generation_context_method_exists(self, builder):
        """build_generation_context 方法存在且可调用。"""
        assert hasattr(builder, "build_generation_context")
        assert callable(builder.build_generation_context)

    def test_build_rewrite_context_method_exists(self, builder):
        """build_rewrite_context 方法存在且可调用。"""
        assert hasattr(builder, "build_rewrite_context")
        assert callable(builder.build_rewrite_context)

    def test_build_blueprint_context_method_exists(self, builder):
        """build_blueprint_context 方法存在且可调用。"""
        assert hasattr(builder, "build_blueprint_context")
        assert callable(builder.build_blueprint_context)

    @pytest.mark.asyncio
    async def test_build_generation_context_returns_generation_context(
        self, builder, mock_session
    ):
        """build_generation_context 返回 GenerationContext 实例。"""
        from src.api.services.novel_context_service import GenerationContext

        none_result = MagicMock()
        none_result.scalar_one_or_none.return_value = None
        empty_list_result = MagicMock()
        empty_list_result.scalars.return_value.all.return_value = []

        call_count = {"n": 0}
        results = [none_result, none_result, empty_list_result, empty_list_result]

        async def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results[idx] if idx < len(results) else empty_list_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        ctx = await builder.build_generation_context(mock_session, "novel-test")
        assert isinstance(ctx, GenerationContext)

    @pytest.mark.asyncio
    async def test_build_generation_context_defaults_when_no_data(
        self, builder, mock_session
    ):
        """无数据时 GenerationContext 使用默认值。"""
        none_result = MagicMock()
        none_result.scalar_one_or_none.return_value = None
        empty_list_result = MagicMock()
        empty_list_result.scalars.return_value.all.return_value = []

        call_count = {"n": 0}
        results = [none_result, none_result, empty_list_result, empty_list_result]

        async def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results[idx] if idx < len(results) else empty_list_result

        mock_session.execute = AsyncMock(side_effect=side_effect)

        ctx = await builder.build_generation_context(mock_session, "novel-test")
        assert ctx.world_str == "暂无世界观"
        assert ctx.chars_str == "暂无人物"
        assert ctx.storylines_str == ""
        assert ctx.style_instruction == ""

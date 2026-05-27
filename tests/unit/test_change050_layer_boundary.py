"""Unit tests for CHANGE-050: 工程质量修复 — 层级边界与前端测试。

覆盖模块:
- src/core/context/novel_context.py (re-export stub)
- src/core/context/__init__.py (re-export chain)
- src/api/services/novel_context_service.py (NovelContextBuilder 实现)
- 层级边界静态检查（core 不导入 api.models / api.services）
"""

import ast
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# 工程根目录
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# 1. Re-export 链路测试
# ---------------------------------------------------------------------------


class TestReExportChain:
    """验证 re-export 链路：core.context → api.services.novel_context_service。"""

    def test_import_novel_context_builder_from_core_context(self):
        """从 src.core.context 导入 NovelContextBuilder 成功。"""
        from src.core.context import NovelContextBuilder

        assert NovelContextBuilder is not None

    def test_import_context_dataclasses_from_core_context(self):
        """从 src.core.context 导入三个 Context dataclass 成功。"""
        from src.core.context import BlueprintContext, GenerationContext, RewriteContext

        assert GenerationContext is not None
        assert RewriteContext is not None
        assert BlueprintContext is not None

    def test_import_novel_context_builder_from_api_service(self):
        """从 src.api.services.novel_context_service 导入 NovelContextBuilder 成功。"""
        from src.api.services.novel_context_service import NovelContextBuilder

        assert NovelContextBuilder is not None

    def test_both_paths_resolve_to_same_class(self):
        """两条导入路径指向同一个类（identity check）。"""
        from src.api.services.novel_context_service import (
            NovelContextBuilder as BuilderFromService,
        )
        from src.core.context import NovelContextBuilder as BuilderFromCore

        assert BuilderFromCore is BuilderFromService

    def test_core_context_novel_context_module_re_exports_all_symbols(self):
        """src.core.context.novel_context 的 __all__ 包含全部四个符号。"""
        import src.core.context.novel_context as mod

        expected = {"BlueprintContext", "GenerationContext", "NovelContextBuilder", "RewriteContext"}
        assert set(mod.__all__) == expected

    def test_core_context_init_re_exports_all_symbols(self):
        """src.core.context.__init__ 的 __all__ 包含全部四个符号。"""
        import src.core.context as pkg

        expected = {"BlueprintContext", "GenerationContext", "NovelContextBuilder", "RewriteContext"}
        assert set(pkg.__all__) == expected


# ---------------------------------------------------------------------------
# 2. 层级边界静态检查
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


class TestLayerBoundary:
    """验证 core 层不向上依赖 api 层。"""

    def test_core_context_novel_context_does_not_import_db_models_directly(self):
        """src/core/context/novel_context.py 是 re-export stub，不直接导入 db_models。

        该文件只做 re-export，不应包含对 src.api.models.db_models 的直接导入。
        """
        stub_path = PROJECT_ROOT / "src" / "core" / "context" / "novel_context.py"
        assert stub_path.exists(), f"文件不存在: {stub_path}"

        source = stub_path.read_text(encoding="utf-8")
        # The stub re-exports from novel_context_service; it must NOT directly
        # import db_models itself.
        assert "src.api.models.db_models" not in source, (
            "core/context/novel_context.py 不应直接导入 src.api.models.db_models，"
            "该文件应仅作为 re-export stub"
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
        """返回一个可配置的 mock AsyncSession。"""
        return AsyncMock()

    def test_instantiation_succeeds(self, builder):
        """NovelContextBuilder 可以无参数实例化。"""
        from src.api.services.novel_context_service import NovelContextBuilder

        instance = NovelContextBuilder()
        assert instance is not None

    def test_build_generation_context_method_exists_and_is_callable(self, builder):
        """build_generation_context 方法存在且可调用。"""
        assert hasattr(builder, "build_generation_context")
        assert callable(builder.build_generation_context)

    def test_build_rewrite_context_method_exists_and_is_callable(self, builder):
        """build_rewrite_context 方法存在且可调用。"""
        assert hasattr(builder, "build_rewrite_context")
        assert callable(builder.build_rewrite_context)

    def test_build_blueprint_context_method_exists_and_is_callable(self, builder):
        """build_blueprint_context 方法存在且可调用。"""
        assert hasattr(builder, "build_blueprint_context")
        assert callable(builder.build_blueprint_context)

    @pytest.mark.asyncio
    async def test_build_generation_context_returns_generation_context(
        self, builder, mock_session
    ):
        """build_generation_context 返回 GenerationContext 实例。"""
        from src.api.services.novel_context_service import GenerationContext

        # build_generation_context issues 4 execute() calls:
        #   1. _get_novel          → scalar_one_or_none → None
        #   2. _build_world_str    → scalar_one_or_none → None  (returns "暂无世界观")
        #   3. _build_chars_str    → scalars().all()    → []    (returns "暂无人物")
        #   4. _build_storylines_str → scalars().all()  → []    (returns "")
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

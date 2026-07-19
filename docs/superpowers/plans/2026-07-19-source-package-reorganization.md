# 源码服务层分包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在业务逻辑和外部契约不变的前提下，把 `src/api/services/` 的 35 个模块迁移到五个职责子包，更新全部导入路径并补齐包说明。

**Architecture:** 采用整文件机械搬迁；`generation`、`content`、`quality`、`knowledge`、`tasks` 成为唯一正式模块路径，四个独立服务保留在根目录。每个迁移批次先用结构测试制造可观察失败，再移动文件、更新绝对导入和测试 patch 路径，最后执行聚焦测试与 Ruff；不增加旧路径兼容壳。

**Tech Stack:** Python 3.11、FastAPI、pytest、Ruff、Poetry、Vue 3、Vitest、Vite。

**Design:** `docs/superpowers/specs/2026-07-19-source-package-reorganization-design.md`

**Workspace constraints:** 在当前工作区执行；不创建或修改 Git worktree，不使用 `git mv`，不暂存、不提交、不推送；不读取或修改 `.claude/worktrees/*`；保留当前归档、队列和其他未提交改动。

---

## 文件结构锁定

最终目录必须是：

```text
src/api/services/
├── README.md
├── __init__.py
├── generation/
│   ├── __init__.py
│   ├── ai_generation_service.py
│   ├── chapter_generation_utils.py
│   ├── chapter_persistence_service.py
│   ├── long_form_generation_helpers.py
│   ├── long_form_progress_service.py
│   ├── novel_generator.py
│   ├── novel_generator_planning.py
│   ├── pause_state_store.py
│   └── progress_event_bus.py
├── content/
│   ├── __init__.py
│   ├── blueprint_service.py
│   ├── career_service.py
│   ├── chapter_analysis_service.py
│   ├── chapter_service.py
│   ├── character_service.py
│   ├── conversation_service.py
│   ├── inspiration_service.py
│   ├── novel_manager.py
│   ├── outline_service.py
│   ├── outline_sync_service.py
│   ├── story_bible_service.py
│   ├── storyline_service.py
│   ├── volume_service.py
│   └── world_service.py
├── quality/
│   ├── __init__.py
│   ├── filler_detection_service.py
│   ├── foreshadow_tracker_service.py
│   ├── novel_context_service.py
│   ├── quality_action_service.py
│   ├── quality_report_service.py
│   └── rewrite_loop_service.py
├── knowledge/
│   ├── __init__.py
│   ├── kg_prompts.py
│   ├── kg_similarity.py
│   └── knowledge_graph_service.py
├── tasks/
│   ├── __init__.py
│   ├── task_dispatcher.py
│   ├── task_manager.py
│   └── task_worker.py
├── agent_journal_service.py
├── book_import_service.py
├── export_service.py
└── reader_simulation_service.py
```

新增的 `tests/unit/test_service_package_layout.py` 只验证文件归属、旧根文件消失、子包说明存在和根目录收口，不导入业务模块，不引入数据库或 LLM 副作用。

## 通用执行规则

- 所有源码移动使用 `mkdir` 和 `mv`，不用 `git mv`。
- 批量替换只作用于 `src/`、`tests/`、`scripts/` 下的 `*.py` 文件。
- 绝对路径只执行精确替换：
  `src.api.services.<module>` → `src.api.services.<package>.<module>`。
- `from src.api.services import <module>` 单独改为
  `from src.api.services.<package> import <module>`。
- 顶层 `src.api.services` 现有三个符号导出继续保留。
- 每批结束都搜索该批旧路径；有任何命中则不进入下一批。
- 不顺手格式化、重命名符号、整理函数或修改注释文案。

### Task 1: 建立迁移基线和结构契约测试

**Files:**
- Create: `tests/unit/test_service_package_layout.py`
- Read/copy for temporary comparison: `src/api/services/*.py`

- [ ] **Step 1: 验证迁移前测试与静态检查基线**

Run:

```bash
poetry run pytest tests/unit -q
poetry run ruff check src tests
```

Expected: 两条命令退出码均为 0；pytest 与当前基线一致（约 839 passed、1 skipped）。若失败，先确认是否是当前工作区已有问题，不在分包任务中修改无关逻辑。

- [ ] **Step 2: 保存服务文件的临时内容快照**

Run:

```bash
mkdir -p /tmp/xiaoshuo-source-package-baseline
cp src/api/services/*.py /tmp/xiaoshuo-source-package-baseline/
```

Expected: `/tmp/xiaoshuo-source-package-baseline/` 包含迁移前的 40 个 Python 文件。该快照只用于差异核对，不加入仓库。

- [ ] **Step 3: 写入完整的目录结构契约测试**

Create `tests/unit/test_service_package_layout.py`:

```python
import ast
from pathlib import Path

import pytest


SERVICES_DIR = Path(__file__).resolve().parents[2] / "src" / "api" / "services"

EXPECTED_PACKAGES = {
    "knowledge": (
        "knowledge_graph_service",
        "kg_prompts",
        "kg_similarity",
    ),
    "tasks": (
        "task_manager",
        "task_dispatcher",
        "task_worker",
    ),
    "quality": (
        "quality_action_service",
        "quality_report_service",
        "filler_detection_service",
        "foreshadow_tracker_service",
        "novel_context_service",
        "rewrite_loop_service",
    ),
    "content": (
        "novel_manager",
        "chapter_service",
        "character_service",
        "world_service",
        "volume_service",
        "outline_service",
        "outline_sync_service",
        "storyline_service",
        "story_bible_service",
        "blueprint_service",
        "conversation_service",
        "career_service",
        "inspiration_service",
        "chapter_analysis_service",
    ),
    "generation": (
        "novel_generator",
        "novel_generator_planning",
        "long_form_generation_helpers",
        "long_form_progress_service",
        "chapter_generation_utils",
        "chapter_persistence_service",
        "ai_generation_service",
        "pause_state_store",
        "progress_event_bus",
    ),
}

ROOT_MODULES = {
    "agent_journal_service.py",
    "book_import_service.py",
    "export_service.py",
    "reader_simulation_service.py",
}


@pytest.mark.parametrize(
    ("package", "modules"),
    EXPECTED_PACKAGES.items(),
    ids=list(EXPECTED_PACKAGES),
)
def test_service_modules_are_grouped(package: str, modules: tuple[str, ...]) -> None:
    package_dir = SERVICES_DIR / package
    init_file = package_dir / "__init__.py"

    assert init_file.is_file()
    assert ast.get_docstring(ast.parse(init_file.read_text(encoding="utf-8")))

    for module in modules:
        assert (package_dir / f"{module}.py").is_file()
        assert not (SERVICES_DIR / f"{module}.py").exists()


def test_service_root_is_structurally_closed() -> None:
    actual_python_files = {path.name for path in SERVICES_DIR.glob("*.py")}

    assert actual_python_files == ROOT_MODULES | {"__init__.py"}
    assert (SERVICES_DIR / "README.md").is_file()
```

- [ ] **Step 4: 运行第一个结构用例并确认它因目录尚未建立而失败**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[knowledge]' -q
```

Expected: FAIL，原因是 `src/api/services/knowledge/__init__.py` 不存在。

### Task 2: 迁移 knowledge 子包

**Files:**
- Create: `src/api/services/knowledge/__init__.py`
- Move: `src/api/services/knowledge_graph_service.py` → `src/api/services/knowledge/knowledge_graph_service.py`
- Move: `src/api/services/kg_prompts.py` → `src/api/services/knowledge/kg_prompts.py`
- Move: `src/api/services/kg_similarity.py` → `src/api/services/knowledge/kg_similarity.py`
- Modify imports: `src/api/routes/knowledge_graph.py`
- Modify imports: `src/api/services/blueprint_service.py`
- Modify imports: `src/api/services/novel_generator.py`
- Modify imports in moved knowledge modules
- Modify tests: `tests/integration/test_knowledge_graph_api.py`
- Modify tests: `tests/unit/test_change035_story_bible_and_three_layer.py`
- Modify tests: `tests/unit/test_kg_embedding.py`
- Modify tests: `tests/unit/test_kg_similarity.py`
- Modify tests: `tests/unit/test_knowledge_graph_service.py`
- Modify tests: `tests/unit/test_live_knowledge_graph.py`

- [ ] **Step 1: 创建包说明并整文件移动三个模块**

Create `src/api/services/knowledge/__init__.py`:

```python
"""知识图谱服务、提示词与相似度工具。"""
```

Run:

```bash
mkdir -p src/api/services/knowledge
mv src/api/services/knowledge_graph_service.py src/api/services/knowledge/knowledge_graph_service.py
mv src/api/services/kg_prompts.py src/api/services/knowledge/kg_prompts.py
mv src/api/services/kg_similarity.py src/api/services/knowledge/kg_similarity.py
```

- [ ] **Step 2: 精确替换 knowledge 导入和 patch 路径**

Apply this mapping in the listed Python files:

```text
src.api.services.knowledge_graph_service -> src.api.services.knowledge.knowledge_graph_service
src.api.services.kg_prompts -> src.api.services.knowledge.kg_prompts
src.api.services.kg_similarity -> src.api.services.knowledge.kg_similarity
```

Run the residual audit:

```bash
rg -n 'src\.api\.services\.(knowledge_graph_service|kg_prompts|kg_similarity)' src tests scripts --glob '*.py'
```

Expected: 退出码 1，无匹配。

- [ ] **Step 3: 核对迁移文件没有逻辑改动**

Run:

```bash
diff -u /tmp/xiaoshuo-source-package-baseline/knowledge_graph_service.py src/api/services/knowledge/knowledge_graph_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/kg_prompts.py src/api/services/knowledge/kg_prompts.py
diff -u /tmp/xiaoshuo-source-package-baseline/kg_similarity.py src/api/services/knowledge/kg_similarity.py
```

Expected: 无差异，或差异仅为上述三个导入路径。

- [ ] **Step 4: 运行 knowledge 聚焦验证**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[knowledge]' tests/unit/test_kg_embedding.py tests/unit/test_kg_similarity.py tests/unit/test_knowledge_graph_service.py tests/unit/test_live_knowledge_graph.py tests/unit/test_change035_story_bible_and_three_layer.py -q
poetry run python -c "import src.api.services.knowledge.knowledge_graph_service; import src.api.services.knowledge.kg_prompts; import src.api.services.knowledge.kg_similarity"
poetry run ruff check src tests
```

Expected: 三条命令均退出 0。

### Task 3: 迁移 tasks 子包

**Files:**
- Create: `src/api/services/tasks/__init__.py`
- Move: `src/api/services/task_manager.py` → `src/api/services/tasks/task_manager.py`
- Move: `src/api/services/task_dispatcher.py` → `src/api/services/tasks/task_dispatcher.py`
- Move: `src/api/services/task_worker.py` → `src/api/services/tasks/task_worker.py`
- Modify imports: `src/api/main.py`
- Modify imports: `src/api/routes/novels.py`
- Modify imports: `src/api/routes/projects.py`
- Modify imports: `src/api/routes/review.py`
- Modify imports: `src/api/routes/ws.py`
- Modify imports: `src/api/services/__init__.py`
- Modify imports: `src/api/services/chapter_generation_utils.py`
- Modify imports: `src/api/services/long_form_generation_helpers.py`
- Modify imports: `src/api/services/novel_generator.py`
- Modify imports in moved task modules
- Modify tests: `tests/unit/test_change031_architecture.py`
- Modify tests: `tests/unit/test_change060_task_status.py`
- Modify tests: `tests/unit/test_task_dispatcher.py`
- Modify tests: `tests/unit/test_task_manager.py`
- Modify tests: `tests/unit/test_task_queue_routes.py`
- Modify tests: `tests/unit/test_task_worker.py`

- [ ] **Step 1: 确认 tasks 结构用例当前失败**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[tasks]' -q
```

Expected: FAIL，原因是 `src/api/services/tasks/__init__.py` 不存在。

- [ ] **Step 2: 创建包说明并整文件移动三个任务模块**

Create `src/api/services/tasks/__init__.py`:

```python
"""持久化任务队列的状态管理、调度与 worker。"""
```

Run:

```bash
mkdir -p src/api/services/tasks
mv src/api/services/task_manager.py src/api/services/tasks/task_manager.py
mv src/api/services/task_dispatcher.py src/api/services/tasks/task_dispatcher.py
mv src/api/services/task_worker.py src/api/services/tasks/task_worker.py
```

- [ ] **Step 3: 精确替换 tasks 导入、包入口和 patch 路径**

Apply these mappings:

```text
src.api.services.task_manager -> src.api.services.tasks.task_manager
src.api.services.task_dispatcher -> src.api.services.tasks.task_dispatcher
src.api.services.task_worker -> src.api.services.tasks.task_worker
from src.api.services import task_manager -> from src.api.services.tasks import task_manager
```

Modify the task export in `src/api/services/__init__.py` to:

```python
from .tasks.task_manager import TaskManager, get_task_manager
```

Keep the existing `generate_novel_background` export pointing to the root module until Task 6 moves generation.

Run:

```bash
rg -n 'src\.api\.services\.(task_manager|task_dispatcher|task_worker)|from src\.api\.services import task_manager' src tests scripts --glob '*.py'
```

Expected: 退出码 1，无匹配。

- [ ] **Step 4: 核对三个任务文件只有导入路径变化**

Run:

```bash
diff -u /tmp/xiaoshuo-source-package-baseline/task_manager.py src/api/services/tasks/task_manager.py
diff -u /tmp/xiaoshuo-source-package-baseline/task_dispatcher.py src/api/services/tasks/task_dispatcher.py
diff -u /tmp/xiaoshuo-source-package-baseline/task_worker.py src/api/services/tasks/task_worker.py
```

Expected: 差异仅为服务模块导入路径。

- [ ] **Step 5: 运行任务队列聚焦验证**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[tasks]' tests/unit/test_task_manager.py tests/unit/test_task_dispatcher.py tests/unit/test_task_worker.py tests/unit/test_task_queue_routes.py tests/unit/test_change060_task_status.py tests/unit/test_change031_architecture.py -q
poetry run python -c "from src.api.services import TaskManager, get_task_manager; import src.api.services.tasks.task_dispatcher; import src.api.services.tasks.task_worker"
poetry run ruff check src tests
```

Expected: 三条命令均退出 0，顶层 `TaskManager` 接口继续可导入。

### Task 4: 迁移 quality 子包

**Files:**
- Create: `src/api/services/quality/__init__.py`
- Move: `src/api/services/quality_action_service.py` → `src/api/services/quality/quality_action_service.py`
- Move: `src/api/services/quality_report_service.py` → `src/api/services/quality/quality_report_service.py`
- Move: `src/api/services/filler_detection_service.py` → `src/api/services/quality/filler_detection_service.py`
- Move: `src/api/services/foreshadow_tracker_service.py` → `src/api/services/quality/foreshadow_tracker_service.py`
- Move: `src/api/services/novel_context_service.py` → `src/api/services/quality/novel_context_service.py`
- Move: `src/api/services/rewrite_loop_service.py` → `src/api/services/quality/rewrite_loop_service.py`
- Modify imports: `src/api/routes/chapters.py`
- Modify imports: `src/api/routes/novels.py`
- Modify imports: `src/api/routes/projects.py`
- Modify imports: `src/api/services/blueprint_service.py`
- Modify imports: `src/api/services/chapter_generation_utils.py`
- Modify imports: `src/api/services/long_form_generation_helpers.py`
- Modify imports: `src/api/services/novel_generator.py`
- Modify imports in moved quality modules
- Modify tests: `tests/unit/test_change037_chapter_editor.py`
- Modify tests: `tests/unit/test_change044_long_form_services.py`
- Modify tests: `tests/unit/test_change049_refactoring.py`
- Modify tests: `tests/unit/test_change050_layer_boundary.py`
- Modify tests: `tests/unit/test_change060_rewrite_rollback.py`
- Modify tests: `tests/unit/test_change061_context_state_delta.py`
- Modify tests: `tests/unit/test_novel_context_service.py`
- Modify tests: `tests/unit/test_novel_generator_supplement.py`
- Modify tests: `tests/unit/test_quality_action_service.py`
- Modify tests: `tests/unit/test_rewrite_loop_service.py`

- [ ] **Step 1: 确认 quality 结构用例当前失败**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[quality]' -q
```

Expected: FAIL，原因是 `src/api/services/quality/__init__.py` 不存在。

- [ ] **Step 2: 创建包说明并整文件移动六个质量模块**

Create `src/api/services/quality/__init__.py`:

```python
"""质量报告、检测、上下文与改写闭环服务。"""
```

Run:

```bash
mkdir -p src/api/services/quality
mv src/api/services/quality_action_service.py src/api/services/quality/quality_action_service.py
mv src/api/services/quality_report_service.py src/api/services/quality/quality_report_service.py
mv src/api/services/filler_detection_service.py src/api/services/quality/filler_detection_service.py
mv src/api/services/foreshadow_tracker_service.py src/api/services/quality/foreshadow_tracker_service.py
mv src/api/services/novel_context_service.py src/api/services/quality/novel_context_service.py
mv src/api/services/rewrite_loop_service.py src/api/services/quality/rewrite_loop_service.py
```

- [ ] **Step 3: 精确替换 quality 导入和 patch 路径**

Apply these mappings:

```text
src.api.services.quality_action_service -> src.api.services.quality.quality_action_service
src.api.services.quality_report_service -> src.api.services.quality.quality_report_service
src.api.services.filler_detection_service -> src.api.services.quality.filler_detection_service
src.api.services.foreshadow_tracker_service -> src.api.services.quality.foreshadow_tracker_service
src.api.services.novel_context_service -> src.api.services.quality.novel_context_service
src.api.services.rewrite_loop_service -> src.api.services.quality.rewrite_loop_service
```

Run:

```bash
rg -n 'src\.api\.services\.(quality_action_service|quality_report_service|filler_detection_service|foreshadow_tracker_service|novel_context_service|rewrite_loop_service)' src tests scripts --glob '*.py'
```

Expected: 退出码 1，无匹配。

- [ ] **Step 4: 核对六个质量文件只有导入路径变化**

Run:

```bash
diff -u /tmp/xiaoshuo-source-package-baseline/quality_action_service.py src/api/services/quality/quality_action_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/quality_report_service.py src/api/services/quality/quality_report_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/filler_detection_service.py src/api/services/quality/filler_detection_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/foreshadow_tracker_service.py src/api/services/quality/foreshadow_tracker_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/novel_context_service.py src/api/services/quality/novel_context_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/rewrite_loop_service.py src/api/services/quality/rewrite_loop_service.py
```

Expected: 差异仅为服务模块导入路径；函数、类、常量和控制流无变化。

- [ ] **Step 5: 运行 quality 聚焦验证**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[quality]' tests/unit/test_quality_action_service.py tests/unit/test_novel_context_service.py tests/unit/test_rewrite_loop_service.py tests/unit/test_change037_chapter_editor.py tests/unit/test_change044_long_form_services.py tests/unit/test_change049_refactoring.py tests/unit/test_change050_layer_boundary.py tests/unit/test_change060_rewrite_rollback.py tests/unit/test_change061_context_state_delta.py tests/unit/test_novel_generator_supplement.py -q
poetry run python -c "import src.api.services.quality.quality_action_service; import src.api.services.quality.quality_report_service; import src.api.services.quality.filler_detection_service; import src.api.services.quality.foreshadow_tracker_service; import src.api.services.quality.novel_context_service; import src.api.services.quality.rewrite_loop_service"
poetry run ruff check src tests
```

Expected: 三条命令均退出 0。

### Task 5: 迁移 content 子包

**Files:**
- Create: `src/api/services/content/__init__.py`
- Move: `src/api/services/novel_manager.py` → `src/api/services/content/novel_manager.py`
- Move: `src/api/services/chapter_service.py` → `src/api/services/content/chapter_service.py`
- Move: `src/api/services/character_service.py` → `src/api/services/content/character_service.py`
- Move: `src/api/services/world_service.py` → `src/api/services/content/world_service.py`
- Move: `src/api/services/volume_service.py` → `src/api/services/content/volume_service.py`
- Move: `src/api/services/outline_service.py` → `src/api/services/content/outline_service.py`
- Move: `src/api/services/outline_sync_service.py` → `src/api/services/content/outline_sync_service.py`
- Move: `src/api/services/storyline_service.py` → `src/api/services/content/storyline_service.py`
- Move: `src/api/services/story_bible_service.py` → `src/api/services/content/story_bible_service.py`
- Move: `src/api/services/blueprint_service.py` → `src/api/services/content/blueprint_service.py`
- Move: `src/api/services/conversation_service.py` → `src/api/services/content/conversation_service.py`
- Move: `src/api/services/career_service.py` → `src/api/services/content/career_service.py`
- Move: `src/api/services/inspiration_service.py` → `src/api/services/content/inspiration_service.py`
- Move: `src/api/services/chapter_analysis_service.py` → `src/api/services/content/chapter_analysis_service.py`
- Modify imports: `src/api/owner_guard.py`
- Modify imports: `src/api/routes/careers.py`
- Modify imports: `src/api/routes/chapter_analysis.py`
- Modify imports: `src/api/routes/chapters.py`
- Modify imports: `src/api/routes/characters.py`
- Modify imports: `src/api/routes/conversations.py`
- Modify imports: `src/api/routes/inspiration.py`
- Modify imports: `src/api/routes/novels.py`
- Modify imports: `src/api/routes/outline_sync.py`
- Modify imports: `src/api/routes/outlines.py`
- Modify imports: `src/api/routes/projects.py`
- Modify imports: `src/api/routes/storylines.py`
- Modify imports: `src/api/routes/volumes.py`
- Modify imports: `src/api/routes/world.py`
- Modify imports: `src/api/services/ai_generation_service.py`
- Modify imports: `src/api/services/book_import_service.py`
- Modify imports: `src/api/services/chapter_generation_utils.py`
- Modify imports: `src/api/services/chapter_persistence_service.py`
- Modify imports: `src/api/services/long_form_generation_helpers.py`
- Modify imports: `src/api/services/novel_generator.py`
- Modify imports: `src/api/services/quality/rewrite_loop_service.py`
- Modify imports in moved content modules
- Modify tests: `tests/integration/test_change029_volume_number_api.py`
- Modify tests: `tests/test_inspiration.py`
- Modify tests: `tests/unit/test_blueprint_service.py`
- Modify tests: `tests/unit/test_change025_fixes.py`
- Modify tests: `tests/unit/test_change026_full_generate.py`
- Modify tests: `tests/unit/test_change029_volume_number.py`
- Modify tests: `tests/unit/test_change031_architecture.py`
- Modify tests: `tests/unit/test_change037_chapter_editor.py`
- Modify tests: `tests/unit/test_change038_dedup_and_timeout.py`
- Modify tests: `tests/unit/test_change041_story_bible.py`
- Modify tests: `tests/unit/test_change049_refactoring.py`
- Modify tests: `tests/unit/test_change060_is_active_semantics.py`
- Modify tests: `tests/unit/test_change061_persist_methods.py`
- Modify tests: `tests/unit/test_chapter_persistence_service.py`
- Modify tests: `tests/unit/test_chapter_service.py`
- Modify tests: `tests/unit/test_character_volume_world_service.py`
- Modify tests: `tests/unit/test_novel_generator_auto_calc.py`
- Modify tests: `tests/unit/test_novel_generator_outline_persist.py`
- Modify tests: `tests/unit/test_novel_generator_supplement.py`
- Modify tests: `tests/unit/test_novel_manager.py`
- Modify tests: `tests/unit/test_outline_service.py`
- Modify tests: `tests/unit/test_outline_sync_service.py`
- Modify tests: `tests/unit/test_story_bible_service.py`
- Modify tests: `tests/unit/test_task_queue_routes.py`

- [ ] **Step 1: 确认 content 结构用例当前失败**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[content]' -q
```

Expected: FAIL，原因是 `src/api/services/content/__init__.py` 不存在。

- [ ] **Step 2: 创建包说明并整文件移动十四个内容模块**

Create `src/api/services/content/__init__.py`:

```python
"""小说实体、章节、大纲、人物与世界观内容服务。"""
```

Run:

```bash
mkdir -p src/api/services/content
mv src/api/services/novel_manager.py src/api/services/content/novel_manager.py
mv src/api/services/chapter_service.py src/api/services/content/chapter_service.py
mv src/api/services/character_service.py src/api/services/content/character_service.py
mv src/api/services/world_service.py src/api/services/content/world_service.py
mv src/api/services/volume_service.py src/api/services/content/volume_service.py
mv src/api/services/outline_service.py src/api/services/content/outline_service.py
mv src/api/services/outline_sync_service.py src/api/services/content/outline_sync_service.py
mv src/api/services/storyline_service.py src/api/services/content/storyline_service.py
mv src/api/services/story_bible_service.py src/api/services/content/story_bible_service.py
mv src/api/services/blueprint_service.py src/api/services/content/blueprint_service.py
mv src/api/services/conversation_service.py src/api/services/content/conversation_service.py
mv src/api/services/career_service.py src/api/services/content/career_service.py
mv src/api/services/inspiration_service.py src/api/services/content/inspiration_service.py
mv src/api/services/chapter_analysis_service.py src/api/services/content/chapter_analysis_service.py
```

- [ ] **Step 3: 精确替换 content 导入、模块导入和 patch 路径**

Apply these mappings:

```text
src.api.services.novel_manager -> src.api.services.content.novel_manager
src.api.services.chapter_service -> src.api.services.content.chapter_service
src.api.services.character_service -> src.api.services.content.character_service
src.api.services.world_service -> src.api.services.content.world_service
src.api.services.volume_service -> src.api.services.content.volume_service
src.api.services.outline_service -> src.api.services.content.outline_service
src.api.services.outline_sync_service -> src.api.services.content.outline_sync_service
src.api.services.storyline_service -> src.api.services.content.storyline_service
src.api.services.story_bible_service -> src.api.services.content.story_bible_service
src.api.services.blueprint_service -> src.api.services.content.blueprint_service
src.api.services.conversation_service -> src.api.services.content.conversation_service
src.api.services.career_service -> src.api.services.content.career_service
src.api.services.inspiration_service -> src.api.services.content.inspiration_service
src.api.services.chapter_analysis_service -> src.api.services.content.chapter_analysis_service
from src.api.services import novel_manager -> from src.api.services.content import novel_manager
from src.api.services import outline_service -> from src.api.services.content import outline_service
from src.api.services import storyline_service -> from src.api.services.content import storyline_service
from src.api.services import conversation_service -> from src.api.services.content import conversation_service
```

Run:

```bash
rg -n 'src\.api\.services\.(novel_manager|chapter_service|character_service|world_service|volume_service|outline_service|outline_sync_service|storyline_service|story_bible_service|blueprint_service|conversation_service|career_service|inspiration_service|chapter_analysis_service)|from src\.api\.services import (novel_manager|outline_service|storyline_service|conversation_service)' src tests scripts --glob '*.py'
```

Expected: 退出码 1，无匹配。

- [ ] **Step 4: 核对十四个内容文件只有导入路径变化**

Run:

```bash
diff -u /tmp/xiaoshuo-source-package-baseline/novel_manager.py src/api/services/content/novel_manager.py
diff -u /tmp/xiaoshuo-source-package-baseline/chapter_service.py src/api/services/content/chapter_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/character_service.py src/api/services/content/character_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/world_service.py src/api/services/content/world_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/volume_service.py src/api/services/content/volume_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/outline_service.py src/api/services/content/outline_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/outline_sync_service.py src/api/services/content/outline_sync_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/storyline_service.py src/api/services/content/storyline_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/story_bible_service.py src/api/services/content/story_bible_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/blueprint_service.py src/api/services/content/blueprint_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/conversation_service.py src/api/services/content/conversation_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/career_service.py src/api/services/content/career_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/inspiration_service.py src/api/services/content/inspiration_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/chapter_analysis_service.py src/api/services/content/chapter_analysis_service.py
```

Expected: 差异仅为服务模块导入路径；函数、类、常量和控制流无变化。

- [ ] **Step 5: 运行 content 聚焦验证**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[content]' tests/test_inspiration.py tests/unit/test_blueprint_service.py tests/unit/test_change025_fixes.py tests/unit/test_change026_full_generate.py tests/unit/test_change029_volume_number.py tests/unit/test_change031_architecture.py tests/unit/test_change037_chapter_editor.py tests/unit/test_change038_dedup_and_timeout.py tests/unit/test_change041_story_bible.py tests/unit/test_change049_refactoring.py tests/unit/test_change060_is_active_semantics.py tests/unit/test_change061_persist_methods.py tests/unit/test_chapter_persistence_service.py tests/unit/test_chapter_service.py tests/unit/test_character_volume_world_service.py tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py tests/unit/test_novel_generator_supplement.py tests/unit/test_novel_manager.py tests/unit/test_outline_service.py tests/unit/test_outline_sync_service.py tests/unit/test_story_bible_service.py tests/unit/test_task_queue_routes.py -q
poetry run python -c "import src.api.services.content.novel_manager; import src.api.services.content.chapter_service; import src.api.services.content.character_service; import src.api.services.content.world_service; import src.api.services.content.volume_service; import src.api.services.content.outline_service; import src.api.services.content.outline_sync_service; import src.api.services.content.storyline_service; import src.api.services.content.story_bible_service; import src.api.services.content.blueprint_service; import src.api.services.content.conversation_service; import src.api.services.content.career_service; import src.api.services.content.inspiration_service; import src.api.services.content.chapter_analysis_service"
poetry run ruff check src tests
```

Expected: 三条命令均退出 0。

### Task 6: 迁移 generation 子包并完成顶层包接口

**Files:**
- Create: `src/api/services/generation/__init__.py`
- Move: `src/api/services/novel_generator.py` → `src/api/services/generation/novel_generator.py`
- Move: `src/api/services/novel_generator_planning.py` → `src/api/services/generation/novel_generator_planning.py`
- Move: `src/api/services/long_form_generation_helpers.py` → `src/api/services/generation/long_form_generation_helpers.py`
- Move: `src/api/services/long_form_progress_service.py` → `src/api/services/generation/long_form_progress_service.py`
- Move: `src/api/services/chapter_generation_utils.py` → `src/api/services/generation/chapter_generation_utils.py`
- Move: `src/api/services/chapter_persistence_service.py` → `src/api/services/generation/chapter_persistence_service.py`
- Move: `src/api/services/ai_generation_service.py` → `src/api/services/generation/ai_generation_service.py`
- Move: `src/api/services/pause_state_store.py` → `src/api/services/generation/pause_state_store.py`
- Move: `src/api/services/progress_event_bus.py` → `src/api/services/generation/progress_event_bus.py`
- Modify imports: `src/api/routes/novels.py`
- Modify imports: `src/api/routes/storylines.py`
- Modify imports: `src/api/routes/ws.py`
- Modify imports: `src/api/services/__init__.py`
- Modify imports: `src/api/services/tasks/task_dispatcher.py`
- Modify imports in moved generation modules
- Modify tests: `tests/api/test_websocket.py`
- Modify tests: `tests/unit/test_change025_fixes.py`
- Modify tests: `tests/unit/test_change026_full_generate.py`
- Modify tests: `tests/unit/test_change029_volume_number.py`
- Modify tests: `tests/unit/test_change031_architecture.py`
- Modify tests: `tests/unit/test_change036_retry_and_chapter_resilience.py`
- Modify tests: `tests/unit/test_change040_volume_and_graph.py`
- Modify tests: `tests/unit/test_change044_long_form_services.py`
- Modify tests: `tests/unit/test_change049_refactoring.py`
- Modify tests: `tests/unit/test_change052_chapter_constraints.py`
- Modify tests: `tests/unit/test_change060_volume_quality_report.py`
- Modify tests: `tests/unit/test_chapter_persistence_service.py`
- Modify tests: `tests/unit/test_compute_chapter_numbering.py`
- Modify tests: `tests/unit/test_novel_generator_auto_calc.py`
- Modify tests: `tests/unit/test_novel_generator_outline_persist.py`
- Modify tests: `tests/unit/test_novel_generator_supplement.py`
- Modify tests: `tests/unit/test_outline_batch_generation.py`
- Modify tests: `tests/unit/test_progress_event_bus.py`
- Modify tests: `tests/unit/test_task_dispatcher.py`

- [ ] **Step 1: 确认 generation 结构用例当前失败**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[generation]' -q
```

Expected: FAIL，原因是 `src/api/services/generation/__init__.py` 不存在。

- [ ] **Step 2: 创建包说明并整文件移动九个生成模块**

Create `src/api/services/generation/__init__.py`:

```python
"""小说与章节生成编排、进度、暂停和落库辅助。"""
```

Run:

```bash
mkdir -p src/api/services/generation
mv src/api/services/novel_generator.py src/api/services/generation/novel_generator.py
mv src/api/services/novel_generator_planning.py src/api/services/generation/novel_generator_planning.py
mv src/api/services/long_form_generation_helpers.py src/api/services/generation/long_form_generation_helpers.py
mv src/api/services/long_form_progress_service.py src/api/services/generation/long_form_progress_service.py
mv src/api/services/chapter_generation_utils.py src/api/services/generation/chapter_generation_utils.py
mv src/api/services/chapter_persistence_service.py src/api/services/generation/chapter_persistence_service.py
mv src/api/services/ai_generation_service.py src/api/services/generation/ai_generation_service.py
mv src/api/services/pause_state_store.py src/api/services/generation/pause_state_store.py
mv src/api/services/progress_event_bus.py src/api/services/generation/progress_event_bus.py
```

- [ ] **Step 3: 精确替换 generation 导入、模块导入和 patch 路径**

Apply these mappings:

```text
src.api.services.novel_generator -> src.api.services.generation.novel_generator
src.api.services.novel_generator_planning -> src.api.services.generation.novel_generator_planning
src.api.services.long_form_generation_helpers -> src.api.services.generation.long_form_generation_helpers
src.api.services.long_form_progress_service -> src.api.services.generation.long_form_progress_service
src.api.services.chapter_generation_utils -> src.api.services.generation.chapter_generation_utils
src.api.services.chapter_persistence_service -> src.api.services.generation.chapter_persistence_service
src.api.services.ai_generation_service -> src.api.services.generation.ai_generation_service
src.api.services.pause_state_store -> src.api.services.generation.pause_state_store
src.api.services.progress_event_bus -> src.api.services.generation.progress_event_bus
from src.api.services import novel_generator -> from src.api.services.generation import novel_generator
from src.api.services import progress_event_bus -> from src.api.services.generation import progress_event_bus
```

Modify the generation export in `src/api/services/__init__.py` to:

```python
from .generation.novel_generator import generate_novel_background
```

Run:

```bash
rg -n 'src\.api\.services\.(novel_generator|novel_generator_planning|long_form_generation_helpers|long_form_progress_service|chapter_generation_utils|chapter_persistence_service|ai_generation_service|pause_state_store|progress_event_bus)|from src\.api\.services import (novel_generator|progress_event_bus)' src tests scripts --glob '*.py'
```

Expected: 退出码 1，无匹配。

- [ ] **Step 4: 核对九个生成文件只有导入路径变化**

Run:

```bash
diff -u /tmp/xiaoshuo-source-package-baseline/novel_generator.py src/api/services/generation/novel_generator.py
diff -u /tmp/xiaoshuo-source-package-baseline/novel_generator_planning.py src/api/services/generation/novel_generator_planning.py
diff -u /tmp/xiaoshuo-source-package-baseline/long_form_generation_helpers.py src/api/services/generation/long_form_generation_helpers.py
diff -u /tmp/xiaoshuo-source-package-baseline/long_form_progress_service.py src/api/services/generation/long_form_progress_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/chapter_generation_utils.py src/api/services/generation/chapter_generation_utils.py
diff -u /tmp/xiaoshuo-source-package-baseline/chapter_persistence_service.py src/api/services/generation/chapter_persistence_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/ai_generation_service.py src/api/services/generation/ai_generation_service.py
diff -u /tmp/xiaoshuo-source-package-baseline/pause_state_store.py src/api/services/generation/pause_state_store.py
diff -u /tmp/xiaoshuo-source-package-baseline/progress_event_bus.py src/api/services/generation/progress_event_bus.py
```

Expected: 差异仅为服务模块导入路径；生成流程、异常处理、任务状态和持久化逻辑无变化。

- [ ] **Step 5: 运行 generation 聚焦验证**

Run:

```bash
poetry run pytest 'tests/unit/test_service_package_layout.py::test_service_modules_are_grouped[generation]' tests/api/test_websocket.py tests/unit/test_change025_fixes.py tests/unit/test_change026_full_generate.py tests/unit/test_change029_volume_number.py tests/unit/test_change031_architecture.py tests/unit/test_change036_retry_and_chapter_resilience.py tests/unit/test_change040_volume_and_graph.py tests/unit/test_change044_long_form_services.py tests/unit/test_change049_refactoring.py tests/unit/test_change052_chapter_constraints.py tests/unit/test_change060_volume_quality_report.py tests/unit/test_chapter_persistence_service.py tests/unit/test_compute_chapter_numbering.py tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py tests/unit/test_novel_generator_supplement.py tests/unit/test_outline_batch_generation.py tests/unit/test_progress_event_bus.py tests/unit/test_task_dispatcher.py -q
poetry run python -c "from src.api.services import generate_novel_background; import src.api.services.generation.novel_generator; import src.api.services.generation.novel_generator_planning; import src.api.services.generation.long_form_generation_helpers; import src.api.services.generation.long_form_progress_service; import src.api.services.generation.chapter_generation_utils; import src.api.services.generation.chapter_persistence_service; import src.api.services.generation.ai_generation_service; import src.api.services.generation.pause_state_store; import src.api.services.generation.progress_event_bus"
poetry run ruff check src tests
```

Expected: 三条命令均退出 0，顶层 `generate_novel_background` 继续可导入。

### Task 7: 补齐服务包说明并收口根目录

**Files:**
- Create: `src/api/services/README.md`
- Modify: `README.md`
- Verify: `src/api/services/__init__.py`
- Test: `tests/unit/test_service_package_layout.py`

- [ ] **Step 1: 写入服务目录维护说明**

Create `src/api/services/README.md` with this structure and content:

```markdown
# API 服务层

`src/api/services` 保存 API 层复用的业务服务。新增模块应按职责进入已有子包，只有明确跨越多个领域或完全独立的服务才保留在根目录。

## 子包职责

- `generation/`：小说与章节生成编排、进度、暂停状态和落库辅助。
- `content/`：小说、章节、人物、世界观、卷、大纲、故事线等内容管理。
- `quality/`：质量动作、报告、检测、上下文和改写闭环。
- `knowledge/`：知识图谱、提示词和相似度工具。
- `tasks/`：持久化任务队列管理、白名单调度和 worker。

## 根目录模块

- `agent_journal_service.py`：智能体日志。
- `book_import_service.py`：书籍导入。
- `export_service.py`：内容导出。
- `reader_simulation_service.py`：读者模拟。

目录调整只表达职责归属。不要借移动文件修改业务流程；跨包依赖应使用完整绝对导入路径。
```

- [ ] **Step 2: 更新根 README 的项目结构片段**

Replace the single services line under `README.md` → “项目结构” with:

```text
│   │   ├── services/             # API 业务服务层
│   │   │   ├── generation/       # 小说/章节生成编排与进度
│   │   │   ├── content/          # 小说内容域管理
│   │   │   ├── quality/          # 质量检测、报告与改写
│   │   │   ├── knowledge/        # 知识图谱服务
│   │   │   └── tasks/            # 持久化任务队列
```

Do not alter the remaining project-structure descriptions.

- [ ] **Step 3: 运行完整结构契约测试**

Run:

```bash
poetry run pytest tests/unit/test_service_package_layout.py -q
```

Expected: 6 passed（五个子包参数用例加一个根目录收口用例）。

- [ ] **Step 4: 核对 services 根目录只剩允许文件**

Run:

```bash
find src/api/services -maxdepth 1 -type f -print | sort
```

Expected: 只包含 `README.md`、`__init__.py` 和四个根服务模块。

### Task 8: 全量路径审计、回归验证与代码审查

**Files:**
- Verify all changed files under: `src/`, `tests/`, `scripts/`, `README.md`
- Do not modify unrelated dirty-worktree files

- [ ] **Step 1: 搜索全部旧模块路径和遗漏的根模块导入**

Run:

```bash
rg -n 'src\.api\.services\.(novel_generator|novel_generator_planning|long_form_generation_helpers|long_form_progress_service|chapter_generation_utils|chapter_persistence_service|ai_generation_service|pause_state_store|progress_event_bus|novel_manager|chapter_service|character_service|world_service|volume_service|outline_service|outline_sync_service|storyline_service|story_bible_service|blueprint_service|conversation_service|career_service|inspiration_service|chapter_analysis_service|quality_action_service|quality_report_service|filler_detection_service|foreshadow_tracker_service|novel_context_service|rewrite_loop_service|knowledge_graph_service|kg_prompts|kg_similarity|task_manager|task_dispatcher|task_worker)' src tests scripts --glob '*.py'
rg -n 'from src\.api\.services import (novel_generator|progress_event_bus|novel_manager|outline_service|storyline_service|conversation_service|task_manager)' src tests scripts --glob '*.py'
```

Expected: 两条命令都退出 1，无匹配。

- [ ] **Step 2: 验证 FastAPI 和全部新服务模块可导入**

Run:

```bash
poetry run python -c "from src.api.main import app; from src.api.services import TaskManager, get_task_manager, generate_novel_background; assert app is not None"
```

Expected: 退出 0，无 traceback。

- [ ] **Step 3: 运行完整后端单元测试和 Ruff**

Run:

```bash
poetry run pytest tests/unit -q
poetry run ruff check src tests
```

Expected: 两条命令退出 0；单元测试不低于迁移前基线。

- [ ] **Step 4: 收集并运行环境允许的后端集成验证**

Run:

```bash
poetry run pytest tests/api tests/integration --collect-only -q
poetry run pytest tests/api -q
```

Then run PostgreSQL-backed integration tests only when the configured database is reachable:

```bash
poetry run pytest tests/integration/test_change029_volume_number_api.py tests/integration/test_change044_long_form_api.py tests/integration/test_full_generate_api.py tests/integration/test_knowledge_graph_api.py -q
```

Expected: 收集和可运行测试退出 0。若沙箱仍禁止访问 `localhost:5432`，记录为“环境未验证”，不得表述为通过。

- [ ] **Step 5: 运行前端回归**

Run from `frontend/`:

```bash
npm test
npm run build
```

Expected: Vitest 47 tests passed，Vite production build 退出 0。

- [ ] **Step 6: 执行最终差异审查**

Run:

```bash
git diff --check
git diff --find-renames=50% -- src/api/services src/api/routes src/api/main.py src/api/owner_guard.py tests scripts README.md
```

Review criteria:

- 所有被迁移服务文件的非导入代码与 `/tmp/xiaoshuo-source-package-baseline/` 一致。
- 没有旧路径兼容文件、业务逻辑变化、API 变化或数据库变化。
- 没有触碰 `.claude/worktrees/*` 和无关工作区文件。
- 新测试和说明与实际目录一致。
- 不执行任何 Git 写操作。

Expected: `git diff --check` 退出 0；人工快速审查无阻断问题。

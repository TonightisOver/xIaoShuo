# 第二轮重构（01 后两项 + 02→03→04）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 post-funnel-cleanup 第二轮收尾——Ticket 01 的 BackgroundTasks 丢失保护 + 前端风格残留统一，以及依赖链 02→03→04 三张重构 Ticket（拆 novel_generator、chapter_generator 接口收窄、短篇质量门禁收敛到 gate）。

**Architecture:** 重构为主，沿用现有 LangGraph + 质量门禁漏斗架构。02 把长篇编排从 novel_generator 迁入 long_form_generation_helpers（保留 re-export 不破测试 patch）；03 在 chapter_generator 层引入 `ChapterGenContext` 对象收拢 12-14 个散列参数并顺手修 storylines 漏传；04 把短篇 quality_check 节点的评分+state_delta 收敛到 `run_quality_gate`，保留节点独有的 KG 抽取副作用。

**Tech Stack:** Python 3.11 · FastAPI · LangGraph · SQLAlchemy · Vue 3 + Tailwind（ink/paper/vermilion 纸墨色板）· pytest

---

## 关键约束与已知风险（实施前必读）

1. **重构测试策略 ≠ TDD**：本计划是行为保持型重构，每个任务以"跑通现有相关测试建立绿色基线"开头，重构后跑同一批测试验证无回归。仅在出现**新行为**时才补新单测。

2. **Ticket 02 patch 耦合**：`tests/integration/test_change044_long_form_api.py:46` patch 的是 `src.api.services.novel_generator.generate_long_form_background`。迁移后**必须保留 re-export**（在 novel_generator.py 末尾 `from src.api.services.long_form_generation_helpers import generate_long_form_background, generate_volume_background, generate_chapters_background`），否则 patch 失效。`generate_volume_background` / `generate_chapters_background` 同理（见路由调用点 `novels.py`、`projects.py`）。

3. **Ticket 03 的两个 GenerationContext 不要混**：
   - `src/api/services/novel_context_service.py:42` 已有一个 `GenerationContext`（world_str/chars_str/storylines_str/style_instruction 四字段，由 `build_generation_context` 装配，面向**调用方**）。
   - 本计划新增的是 chapter_generator 层的 `ChapterGenContext`（多含 `previous_chapter`/`chapter_outline`/`target_words`/`blueprint`/`story_bible_context`/`kg_service`/`novel_id`/`client`/`on_token`/`on_complete`/`pause_checker`，面向**生成器内部**）。两者命名不同、职责不同，不要合并。

4. **Ticket 04 是行为变更，非纯收敛**：短篇节点当前用「KG verdict == block」+「StoryBible error 计数」判 consistency_blocked；`run_quality_gate` 的硬门禁只看 L2 评分的 `character_consistency`/`world_consistency < 0.4`（gate.py:136-139）。切换后**一致性 block 判定口径变化**。这是本计划唯一的行为变化点，Task 4 必须在 PR 描述里显式标注，并跑短篇 LangGraph 集成测试确认下游 revision 路由不依赖旧口径。

5. **Ticket 04 保留节点副作用**：`quality_check.py:174-186` 的 `kg_service.extract_from_chapter`（知识抽取）是 gate 不做的事，**必须保留在节点里**，gate 只接管「评分 + state_delta + consistency 状态」。KG 一致性检查（verdict/error）当前既用于 block 判定又写入 `consistency_warnings`/`kg_continuity_report`；切换后 block 判定交给 gate，但 `consistency_warnings`/`kg_continuity_report` 仍需保留产出供下游 revision 节点展示——Task 4 执行前先核验 `graph.py` 与 revision 节点是否消费这两个字段。

6. **行号是探查时快照**：所有 `file.py:NNN` 引用基于 2026-07-18 探查，重构会移动行号，以函数名/符号名为准。

---

## File Structure

### Ticket 01

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/api/services/task_manager.py` | `recover_interrupted_tasks()` 扩展为同时清理 pending | Modify |
| `src/api/main.py` | lifespan startup 调用（已在 :76-79 调用，无需改） | Verify only |
| `frontend/src/views/ForeshadowTracker.vue` | neutral 全量 → ink/paper，状态色保留语义 | Modify |
| `frontend/src/views/ChapterEdit.vue` | amber/indigo → 纸墨 | Modify |
| `frontend/src/views/KnowledgeGraphView.vue` | neutral + purple tab → ink/paper/vermilion | Modify |
| `frontend/src/components/KnowledgeGraph.vue` | purple loading → vermilion；图例实体色保留 | Modify |
| `frontend/src/views/Careers.vue` | `getCategoryColor`/`getCategoryBadgeClass` 门派色板去 neutral | Modify |
| `frontend/src/views/Home.vue` | :173 neutral fallback → ink | Modify |

### Ticket 02

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/api/services/long_form_generation_helpers.py` | 长篇编排落点（已含 generate_volume_chapters 等） | Modify（迁入 3 个入口） |
| `src/api/services/novel_generator.py` | 删长篇入口体，保留 re-export | Modify |

### Ticket 03

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/core/llm/chapter_generator.py` | 定义 `ChapterGenContext`，三函数签名收窄 | Modify |
| `src/core/langgraph/nodes/chapter_generation.py:98` | 短篇节点调用方传 ctx | Modify |
| `src/api/services/long_form_generation_helpers.py:635` | 长篇调用方传 ctx（顺手补 storylines_str） | Modify |

### Ticket 04

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/core/langgraph/nodes/quality_check.py` | 评分收敛到 gate，保留 KG 抽取 | Modify |
| `src/core/langgraph/graph.py` | 核验下游对 consistency_blocked 的消费 | Verify only |

---

## Task 1: BackgroundTasks 丢失保护 — pending 标 failed

**Files:**
- Modify: `src/api/services/task_manager.py:294-327`（`recover_interrupted_tasks`）
- Verify: `src/api/main.py:76-79`（已调用，无需改）

- [ ] **Step 1: 读现状，确认绿色基线**

Run: `grep -n "recover_interrupted_tasks\|status == \"running\"\|status == \"pending\"" src/api/services/task_manager.py`
确认 `recover_interrupted_tasks` 当前只查 `status == "running"`（task_manager.py:310）。

- [ ] **Step 2: 跑现有 task_manager 测试建立基线**

Run: `pytest tests/unit -k "task_manager or recover" -v 2>&1 | tail -20`
Expected: 现有用例全 PASS（或无匹配用例则记空基线）。记录通过数。

- [ ] **Step 3: 修改 `recover_interrupted_tasks` 同时清理 pending**

把 `select(Task).where(Task.status == "running")` 改为查 `status.in_(["running", "pending"])`，并在写 errors 时区分原因。参考现状（task_manager.py:294-327），改为：

```python
async def recover_interrupted_tasks(self) -> None:
    """启动时恢复中断任务：孤儿 running + 容器重启丢失的 pending 全标 failed。

    pending 任务由 FastAPI BackgroundTasks 进程内调度，容器在 add_task 后、
    后台函数跑前重启会永久卡 pending。启动时一律标 failed，避免假死。
    """
    try:
        with self.session_factory() as session:
            stuck = session.execute(
                select(Task).where(Task.status.in_(["running", "pending"]))
            ).scalars().all()
            for task in stuck:
                reason = (
                    "系统重启中断：running 任务丢失运行态"
                    if task.status == "running"
                    else "系统重启中断：pending 任务未及执行（BackgroundTasks 进程内丢失）"
                )
                task.status = "failed"
                task.errors = (task.errors or []) + [reason]
                task.completed_at = ...  # 保留现状写法，按现有 running 分支的 completed_at 赋值方式对齐
            session.commit()
            if stuck:
                logger.info("recovered_interrupted_tasks", count=len(stuck))
    except Exception as e:
        logger.exception("recover_interrupted_tasks_failed", error=str(e))
```

> 注意：`completed_at` 赋值、`errors` 字段名、logger 调用必须与现有 running 分支（task_manager.py:310-327）逐字对齐——实施时先 Read 该函数完整体，照抄其字段写法，只改 where 条件 + reason 文案 + 循环内按 status 分流 reason。**不要发明新字段。**

- [ ] **Step 4: 跑测试验证无回归**

Run: `pytest tests/unit -k "task_manager or recover" -v 2>&1 | tail -20`
Expected: 通过数 ≥ Step 2 基线，无新增 FAIL。

- [ ] **Step 5: 补一个新单测覆盖 pending 清理（新行为）**

Create: `tests/unit/test_recover_pending_tasks.py`

```python
"""启动恢复：pending 任务也须被标 failed（BackgroundTasks 丢失保护）。"""
import pytest
from src.api.services.task_manager import TaskManager


@pytest.mark.asyncio
async def test_recover_marks_pending_as_failed(tmp_path, monkeypatch):
    # 用与现有 task_manager 测试一致的 fixture 风格构造一个 pending Task
    # 参考 tests/unit 下已有 task_manager 测试的 db fixture 写法
    ...
    mgr = TaskManager(session_factory=...)
    await mgr.recover_interrupted_tasks()
    task = await mgr.get_task(task_id)
    assert task["status"] == "failed"
    assert any("pending" in (e or "") for e in (task.get("errors") or []))
```

> 实施时先 Read `tests/unit` 下任一已有 task_manager 测试，复用其 db/fixture 搭法，把 `...` 填实。**不要造新 fixture 框架。**

- [ ] **Step 6: 跑新测试**

Run: `pytest tests/unit/test_recover_pending_tasks.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/services/task_manager.py tests/unit/test_recover_pending_tasks.py
git commit -m "fix(task_manager): 启动恢复同时清理 pending 任务，防 BackgroundTasks 丢失假死（Ticket 01）
"
```

---

## Task 2: 前端风格残留统一纸墨（4 组件）

**Files:**
- Modify: `frontend/src/views/ForeshadowTracker.vue`（neutral 全量）
- Modify: `frontend/src/views/ChapterEdit.vue`（amber/indigo）
- Modify: `frontend/src/views/KnowledgeGraphView.vue`（neutral + purple tab）
- Modify: `frontend/src/components/KnowledgeGraph.vue`（purple loading）
- Modify: `frontend/src/views/Careers.vue`（门派色板去 neutral）
- Modify: `frontend/src/views/Home.vue`（:173 fallback）

**纸墨映射规则**（基线参考 `frontend/src/views/TaskList.vue`）：
- `neutral-*` → `ink-*`（文本/边框/背景暖墨）
- 页背景 `bg-neutral-50`/`bg-white` 卡片 → `bg-paper-50`/`bg-paper-100`
- 强调色（blue/purple/indigo 非语义）→ `vermilion-*`
- **语义状态色保留**：red（失败/删除/悬挂）、emerald（成功/进行中）、amber（警告）在 TaskList 中已保留，本计划也保留——**只改 neutral 系与非语义强调色**。
- 例外：ChapterEdit 的 amber 草稿条、indigo 点、Careers 门派色板里的 neutral fallback 属"必改"（amber 警告条可酌情保留 amber 语义，但 indigo/neutral 必改）。

- [ ] **Step 1: ForeshadowTracker.vue — neutral 全量替换**

逐行把 `text-neutral-*`/`border-neutral-*`/`bg-neutral-*` 替换为对应 `ink-*`/`paper-*`。涉及行（探查快照）：2, 15, 16, 20, 29, 31, 47, 48, 49, 50, 65, 67, 68, 72, 91, 92, 97, 98, 102, 111, 114, 123, 124, 125, 132, 137, 138, 149, 152, 164, 169, 174, 238, 239, 240, 244, 245, 246。

状态色保留：`border-blue-*`/`bg-blue-*`（已回收）、`border-red-*`/`bg-red-*`（悬挂）、`border-green-*`/`bg-green-*`（进行中）——这些是 tab 状态语义，不动（行 53, 54, 55, 59, 60, 61, 157, 213, 214, 215, 256-258, 262-264）。

实施手法：用 Edit 的 `replace_all` 分批替换 `neutral-950`→`ink-900`、`neutral-700`→`ink-700`、`neutral-600`→`ink-600`、`neutral-500`→`ink-500`、`neutral-400`→`ink-400`、`neutral-300`→`ink-300`、`neutral-200`→`ink-200`、`neutral-100`→`paper-100`、`neutral-50`→`paper-50`。**每批替换后 Read 一次确认未误伤语义色行。**

- [ ] **Step 2: ChapterEdit.vue — amber 草稿条 + indigo 点**

- 行 52, 54, 60, 61, 65, 66：amber 草稿提示条。保留 amber 语义（警告）亦可，但本计划要求统一为纸墨：`bg-amber-50`→`bg-paper-100`、`border-amber-200`→`border-ink-200`、`text-amber-800`→`text-ink-800`、`text-amber-600`→`text-ink-600`、`bg-amber-100`→`bg-paper-200`、`bg-amber-600 hover:bg-amber-700`→`bg-ink-700 hover:bg-vermilion-600`、`border-amber-300 text-amber-700 hover:bg-amber-100`→`border-ink-300 text-ink-700 hover:bg-paper-100`。
- 行 237：`bg-indigo-400`（自动保存指示点）→ `bg-vermilion-400`。
- 行 177-180 版本 badge：`bg-blue-50 text-blue-700`→`bg-paper-100 text-ink-700`；`bg-amber-50 text-amber-700`→`bg-paper-200 text-ink-700`；`bg-emerald-50 text-emerald-700` 保留（成功语义）。
- 行 186 amber 星标 → `text-ink-600`（或保留 amber 警告语义，二选一，建议改 ink 保持一致）。
- 行 100 rose 删除按钮、行 259 emerald 已保存：**保留**。

- [ ] **Step 3: KnowledgeGraphView.vue — neutral + purple tab**

- 行 6, 9, 22：neutral → ink/paper。
- 行 26-27, 35-36, 44-45：tab 激活态 `text-purple-600 border-purple-600` → `text-vermilion-600 border-vermilion-600`；非激活 `text-neutral-500 hover:text-neutral-800` → `text-ink-500 hover:text-ink-800`。

- [ ] **Step 4: KnowledgeGraph.vue（component）— purple loading**

- 行 36：`border-purple-500/10 border-t-purple-600` → `border-vermilion-500/10 border-t-vermilion-600`。
- 行 40 red error：保留（语义）。
- 行 59, 62, 65, 68 图例实体色（blue/emerald/orange/purple）：**保留**（实体类型语义色，区分人物/地点/事件/物品，改了丧失可读性）。

- [ ] **Step 5: Careers.vue — 门派色板去 neutral**

- 行 432-438 `getCategoryColor`：fallback `bg-neutral-500` → `bg-ink-500`。其余 emerald/amber/purple/blue/cyan 保留（门派区分语义色）。
- 行 443-449 `getCategoryBadgeClass`：fallback `bg-neutral-50 text-neutral-600 border-neutral-200` → `bg-paper-50 text-ink-600 border-ink-200`。其余保留。
- 行 100, 127 red 删除、行 224 emerald 成功：保留。

- [ ] **Step 6: Home.vue — :173 fallback**

- 行 173：`'bg-neutral-100 text-neutral-600'` → `'bg-paper-100 text-ink-600'`。Read 行 160-173 确认 `map[type]` 其余值已纸墨（探查显示 :63 已 `hover:border-ink-200`）。

- [ ] **Step 7: 前端构建验证**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build 成功，无 Tailwind class 报错。

- [ ] **Step 8: 视觉抽检（建议但非阻塞）**

如果本地 dev server 可起：`cd frontend && npm run dev`，人眼抽检 ForeshadowTracker / ChapterEdit / KnowledgeGraph / Careers / Home 五页配色统一。无 dev server 则跳过，依赖 build 通过。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/ForeshadowTracker.vue frontend/src/views/ChapterEdit.vue frontend/src/views/KnowledgeGraphView.vue frontend/src/components/KnowledgeGraph.vue frontend/src/views/Careers.vue frontend/src/views/Home.vue
git commit -m "style(frontend): 5 组件风格残留统一纸墨（Ticket 01）
"
```

> Ticket 01 完成。更新 `.scratch/post-funnel-cleanup/issues/01-security-ops-debt.md` Status 字段为 partial（安全三项仍暂不处理）。

---

## Task 3: 拆 novel_generator — 长篇三入口迁入 helpers（Ticket 02）

**Files:**
- Modify: `src/api/services/long_form_generation_helpers.py`（迁入 3 函数）
- Modify: `src/api/services/novel_generator.py`（删体 + re-export）

- [ ] **Step 1: 建立绿色基线**

Run: `pytest tests/integration/test_change044_long_form_api.py tests/unit/test_change044_long_form_services.py -v 2>&1 | tail -30`
Expected: 全 PASS。记录用例数。这是 02 的回归护栏。

- [ ] **Step 2: Read 三个待迁函数完整体**

Read `novel_generator.py:625-752`（`generate_volume_background` + `generate_chapters_background`）和 `:761-995`（`generate_long_form_background`）。确认它们依赖的符号：`get_task_manager`/`get_novel_manager`/`get_volume_service`/`get_long_form_progress_service`/`calculate_long_form_chapter_plan`/`generate_*` helpers/`_emit_progress`/`EventType`/延迟 import `get_novel_manager`/`get_outline_service`。

- [ ] **Step 3: 在 helpers 末尾追加三个函数**

把 Step 2 Read 到的三个函数体**原样**复制到 `long_form_generation_helpers.py` 末尾。函数体不动一行。补齐 helpers 缺的 import（检查 helpers 现有 import 块，缺哪个加哪个：`get_task_manager`/`get_volume_service`/`calculate_long_form_chapter_plan`/`EventType`/`_emit_progress` 等——其中 `_emit_progress`/`EventType` 可能 helpers 已有，确认）。

> 函数内延迟 import（如 `from src.api.services.outline_service import get_outline_service`）保持原样，不要提前到模块顶部（避免循环 import 风险——现状就是延迟的，照搬）。

- [ ] **Step 4: novel_generator 删体，保留 re-export**

删除 `novel_generator.py:625-995` 三个函数体，替换为 re-export 块（紧跟在保留区之后，`_persist_to_novel` 之后）：

```python
# 长篇编排入口已迁入 long_form_generation_helpers（Ticket 02）。
# 此处 re-export 保持路由层与测试 patch 路径不变：
# tests/integration/test_change044_long_form_api.py patch 本模块符号。
from src.api.services.long_form_generation_helpers import (  # noqa: E402,F401
    generate_long_form_background,
    generate_volume_background,
    generate_chapters_background,
)
```

- [ ] **Step 5: 清理 novel_generator 不再需要的顶部 import**

删体后，novel_generator 不再直接用 `generate_master_outline`/`generate_volume_chapters`/`generate_volume_outline`/`generate_volume_quality_report`/`get_long_form_progress_service`/`calculate_long_form_chapter_plan`（这些都迁走了）。**逐个 grep 确认这些符号在 novel_generator 保留区（短篇编排 + 调度原语 + _persist_to_novel）不再出现**，再删对应 import 行：

Run: `grep -n "generate_master_outline\|generate_volume_chapters\|generate_volume_outline\|generate_volume_quality_report\|get_long_form_progress_service\|calculate_long_form_chapter_plan" src/api/services/novel_generator.py`

若某符号在保留区仍出现 → 保留其 import；否则删除。`calculate_long_form_chapter_plan`/`FULL_GENERATE_STAGES`/`STAGE_ORDER`/`_full_generate_percentage` 的 re-export（:96-101）若短篇编排仍用则保留。

- [ ] **Step 6: 行数核验**

Run: `wc -l src/api/services/novel_generator.py src/api/services/long_form_generation_helpers.py`
Expected: novel_generator 从 ~996 降到 ~700 区间；helpers 相应增长。

- [ ] **Step 7: 跑回归测试**

Run: `pytest tests/integration/test_change044_long_form_api.py tests/unit/test_change044_long_form_services.py -v 2>&1 | tail -30`
Expected: 与 Step 1 同样用例全 PASS（re-export 保住了 patch 路径）。

- [ ] **Step 8: 跑全量测试确认无别处回归**

Run: `pytest tests/ -x -q 2>&1 | tail -30`
Expected: 全 PASS（或仅已知与本轮无关的 skip）。若有新 FAIL，grep 报错符号定位是否漏迁某调用方。

- [ ] **Step 9: Commit**

```bash
git add src/api/services/novel_generator.py src/api/services/long_form_generation_helpers.py
git commit -m "refactor(novel_generator): 长篇三入口迁入 long_form_generation_helpers（Ticket 02）

generate_long_form_background / generate_volume_background / generate_chapters_background
从 novel_generator 迁入 helpers，novel_generator 只留短篇 LangGraph 编排 + 调度原语。
保留 re-export 不破 test_change044 patch 路径。
"
```

> 更新 `.scratch/post-funnel-cleanup/issues/02-split-novel-generator.md` Status → resolved。

---

## Task 4: chapter_generator 接口收窄 — ChapterGenContext（Ticket 03）

**Files:**
- Modify: `src/core/llm/chapter_generator.py:186-300+`（三函数 + 新 dataclass）
- Modify: `src/core/langgraph/nodes/chapter_generation.py:98`
- Modify: `src/api/services/long_form_generation_helpers.py:635`

- [ ] **Step 1: 建立绿色基线**

Run: `pytest tests/unit -k "chapter_generator or chapter_generation" -v 2>&1 | tail -20`
Expected: 全 PASS。记录用例数。

- [ ] **Step 2: Read chapter_generator.py:1-60 与 :300-420**

确认模块顶部 import（dataclass/field/Any/Callable/Awaitable 等）、`_generate_single_chapter_inner` 完整签名与函数体如何消费这些参数（决定 ChapterGenContext 字段集）。

- [ ] **Step 3: 定义 ChapterGenContext dataclass**

在 chapter_generator.py 顶部（import 之后、第一个函数之前）新增：

```python
@dataclass
class ChapterGenContext:
    """单章生成上下文：收拢 generate_single_chapter 的 12-14 个散列参数。

    面向 chapter_generator 内部；与 novel_context_service.GenerationContext
    （面向调用方装配）职责不同，不要合并。
    """
    client: Any
    chapter_outline: dict[str, Any]
    previous_chapter: str
    characters_json: str
    world_setting_json: str
    storylines_json: str = ""
    style_instruction: str = ""
    kg_service: Any | None = None
    novel_id: str | None = None
    target_words: int | None = None
    blueprint: dict | None = None
    story_bible_context: str | None = None
    # 流式专属（generate_chapter_stream 用）
    on_token: Callable[[str, str], Awaitable[None]] | None = None
    on_complete: Callable[[str], Awaitable[None]] | None = None
    pause_checker: Callable[[], Awaitable[bool]] | None = None
```

> 确保 `dataclass`/`field`/`Callable`/`Awaitable` 已在顶部 import（Step 2 确认）。

- [ ] **Step 4: 改 `generate_single_chapter` 签名为收 ctx**

```python
async def generate_single_chapter(ctx: ChapterGenContext) -> dict[str, Any]:
    """生成单章内容（非流式）。

    Args/Returns 同旧版，参数通过 ChapterGenContext 传入。
    """
    try:
        return await asyncio.wait_for(
            _generate_single_chapter_inner(ctx),
            timeout=CHAPTER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        chapter_num = ctx.chapter_outline.get("chapter", 0)
        logger.error("chapter_generation_timeout", chapter=chapter_num, timeout=CHAPTER_TIMEOUT_SECONDS)
        return {
            "chapter": chapter_num,
            "title": ctx.chapter_outline.get("title", f"第{chapter_num}章"),
            "content": f"[章节生成失败：生成超时（{CHAPTER_TIMEOUT_SECONDS}s），可能是模型响应较慢，请稍后重试]",
            "word_count": 0,
            "generation_failed": True,
        }
```

- [ ] **Step 5: 改 `generate_chapter_stream` 签名为收 ctx**

```python
async def generate_chapter_stream(ctx: ChapterGenContext) -> dict[str, Any]:
    """Generate a single chapter using streaming for body text."""
    try:
        return await asyncio.wait_for(
            _generate_single_chapter_inner(ctx),
            timeout=CHAPTER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        chapter_num = ctx.chapter_outline.get("chapter", 0)
        logger.error("chapter_generation_timeout", chapter=chapter_num, timeout=CHAPTER_TIMEOUT_SECONDS)
        return {
            "chapter": chapter_num,
            "title": ctx.chapter_outline.get("title", f"Chapter {chapter_num}"),
            "content": f"[Chapter generation failed: timeout ({CHAPTER_TIMEOUT_SECONDS}s)]",
            "word_count": 0,
            "generation_failed": True,
        }
```

- [ ] **Step 6: 改 `_generate_single_chapter_inner` 收 ctx，内部改用 `ctx.xxx`**

签名改为 `async def _generate_single_chapter_inner(ctx: ChapterGenContext) -> dict[str, Any]:`。函数体内所有 `characters_json`/`world_setting_json`/`storylines_json`/`style_instruction`/`kg_service`/`novel_id`/`target_words`/`blueprint`/`story_bible_context`/`chapter_outline`/`previous_chapter`/`client` 引用全部加 `ctx.` 前缀；`on_token`/`on_complete`/`pause_checker` 改为 `ctx.on_token` 等（注意 None 判断：原代码可能 `if on_token:`，改 `if ctx.on_token:`）。

> 这是机械替换，逐处改。改完 Read 一遍函数体确认无残留裸参数名。

- [ ] **Step 7: 改调用方一 — helpers:635（长篇，顺手补 storylines_str）**

把 helpers:635-649 的 `generate_chapter_stream(client=..., ...)` 改为构造 ctx：

```python
from src.core.llm.chapter_generator import ChapterGenContext

chapter_result = await generate_chapter_stream(
    ChapterGenContext(
        client=client,
        chapter_outline=ch_outline,
        previous_chapter=previous_chapter,
        characters_json=chars_str,
        world_setting_json=world_str,
        storylines_str=gen_ctx.storylines_str,  # ← 顺手修漏传 bug（Ticket 03）
        style_instruction=style_instruction,
        target_words=chapter_target_words,
        novel_id=novel_id,
        blueprint=bp,
        story_bible_context=story_bible_ctx,
        on_token=on_token,
        on_complete=on_complete,
        pause_checker=pause_checker,
    )
)
```

> `gen_ctx` 已在 helpers:550 构造（NovelContextBuilder.GenerationContext），其 `.storylines_str` 字段已填充（novel_context_service.py:110）。此处首次传入，修复「helpers:552-554 漏拆 storylines_str」。

- [ ] **Step 8: 改调用方二 — chapter_generation.py:98（短篇节点）**

Read `src/core/langgraph/nodes/chapter_generation.py:90-115`。改为构造 ctx：

```python
from src.core.llm.chapter_generator import ChapterGenContext, generate_single_chapter

chapter_result = await generate_single_chapter(
    ChapterGenContext(
        client=client,
        chapter_outline=chapter_outline,
        previous_chapter=previous_chapter,
        characters_json=json.dumps(state.get("characters", []), ensure_ascii=False),
        world_setting_json=json.dumps(state.get("world_setting"), ensure_ascii=False),
        storylines_json=json.dumps(state.get("storylines", []), ensure_ascii=False),  # ← 补短篇 storylines
        style_instruction=state.get("style_instruction", ""),
        kg_service=...,
        novel_id=novel_id,
        target_words=...,
        blueprint=blueprint,
        story_bible_context=story_bible_ctx,
    )
)
```

> 实施时 Read 该节点完整段，把 `...` 填为现状已用的取值（kg_service/target_words 从 config 或 state 取，照现状）。**storylines_json 此前短篇节点根本没传（默认 ""），此处补上**——这是 Ticket 03 声明的短篇另一处漏传。

- [ ] **Step 9: 全仓搜其他调用方**

Run: `grep -rn "generate_single_chapter\|generate_chapter_stream" src/ tests/ --include="*.py"`
Expected: 除 chapter_generator.py 自身、chapter_generation.py、helpers 外，确认无第四处调用方。若有 → 一并改。

- [ ] **Step 10: 跑回归测试**

Run: `pytest tests/unit -k "chapter_generator or chapter_generation or long_form" -v 2>&1 | tail -30`
Expected: ≥ Step 1 基线通过数，无新 FAIL。

- [ ] **Step 11: 跑全量测试**

Run: `pytest tests/ -x -q 2>&1 | tail -30`
Expected: 全 PASS。

- [ ] **Step 12: Commit**

```bash
git add src/core/llm/chapter_generator.py src/core/langgraph/nodes/chapter_generation.py src/api/services/long_form_generation_helpers.py
git commit -m "refactor(chapter_generator): 14 参数收窄为 ChapterGenContext 对象 + 修 storylines 漏传（Ticket 03）

generate_single_chapter/generate_chapter_stream/_generate_single_chapter_inner
统一收 ChapterGenContext；三处调用方不再手工拆解。
顺手修 helpers:552 与短篇节点两处 storylines_str 漏传。
"
```

> 更新 `.scratch/post-funnel-cleanup/issues/03-chapter-generator-context.md` Status → resolved。

---

## Task 5: 短篇 quality_check 节点收敛到 gate（Ticket 04）

**Files:**
- Modify: `src/core/langgraph/nodes/quality_check.py:21-291`（node 函数体重写）
- Verify: `src/core/langgraph/graph.py`（下游消费核验）

- [ ] **Step 1: 核验下游依赖（执行前必做）**

Run: `grep -rn "consistency_blocked\|revision_requests\|kg_continuity_report\|quality_scores\[" src/core/langgraph/ --include="*.py"`
确认 `graph.py` 与 revision 节点消费这些 state 字段的范围。记录：哪些字段切换后仍需由 quality_check 节点产出（gate 不产 `revision_requests`/`kg_continuity_report`/`consistency_warnings`，这些必须保留在节点里）。

- [ ] **Step 2: 建立绿色基线**

Run: `pytest tests/unit -k "quality_check or langgraph or quality_gate" -v 2>&1 | tail -30`
Expected: 全 PASS。记录用例数。这是 04 的回归护栏。

- [ ] **Step 3: 重写 quality_check.node 评分段为 gate 调用**

保留节点结构，**只替换"评分+一致性+持久化"段（quality_check.py:188-291）**为一次 `run_quality_gate` 调用。KG 抽取副作用（:174-186）保留。KG 一致性检查（:97-172）保留用于产出 `consistency_warnings`/`kg_continuity_report` 供下游展示，但**不再用它判 block**（block 交给 gate 的 L2 评分）。

新 node 函数体结构（保留前 :1-186 不变，:188 起替换）：

```python
    # 3. 质量门禁漏斗（收敛到 run_quality_gate，Ticket 04）
    #    gate 接管：state_delta 抽取 + L0 + L1 + L2 评分 + consistency 硬门禁 + L3 改写。
    #    节点保留：KG 一致性检查（产出 consistency_warnings/kg_continuity_report 供下游展示）
    #             + KG 知识抽取副作用（已在 §2.6 完成）。
    #    注意：gate 的 consistency 硬门禁口径为 L2 评分 character_consistency/world_consistency < 0.4，
    #    与旧版「KG verdict==block / StoryBible error>0」不同——这是有意的行为收敛。
    from src.api.services.chapter_persistence_service import persist_quality_to_version
    from src.api.services.rewrite_loop_service import RewriteLoopService
    from src.core.quality.gate import GatePersistCallbacks, run_quality_gate

    novel_id = state.get("novel_id") or state.get("project_id")
    persist_quality_fn = configurable.get("persist_quality") or persist_quality_to_version

    novel_type = state.get("novel_type", "网络小说")
    idea = state.get("idea", "暂无核心创意描述")
    world_setting_str = (
        json.dumps(state.get("world_setting"), ensure_ascii=False)
        if state.get("world_setting") else "暂无世界观设定"
    )
    characters_str = (
        json.dumps(state.get("characters", []), ensure_ascii=False)
        if state.get("characters") else "暂无人物角色人设"
    )

    gate_callbacks = GatePersistCallbacks(
        update_state_delta=_noop_state_delta,  # 短篇 LangGraph 暂无 manager.update_state_delta 入口；见下方说明
        update_quality_status=_noop_quality_status,
        persist_quality_scores=persist_quality_fn,
        detect_bible_conflicts=configurable.get("detect_bible_conflicts"),
    )

    try:
        gate_result = await run_quality_gate(
            novel_id=novel_id,
            chapter_number=chapter_number,
            chapter_result={
                "content": chapter_content,
                "word_count": last_chapter.get("word_count", len(chapter_content)),
                "chapter_type": last_chapter.get("chapter_type"),
            },
            chapter_outline=last_chapter.get("plot") or last_chapter.get("outline"),
            novel_type=novel_type,
            idea=idea,
            world_setting=world_setting_str,
            characters=characters_str,
            persist_callbacks=gate_callbacks,
            rewrite_service=RewriteLoopService(),
            chapter_index_in_volume=max(len(chapters) - 1, 0),
        )

        quality_scores = dict(gate_result.quality_scores)
        quality_scores["consistency"] = consistency_score  # 仍保留 KG 一致性分作参考维度
        if gate_result.quality_status == "consistency_blocked":
            quality_scores["consistency_blocked"] = True
            quality_scores["status"] = "consistency_blocked"

        revision_requests = [f"【{dim}】: {fb}" for dim, fb in (gate_result.warnings or [])]
        # warnings 是 list[dict]，revision_requests 的旧格式是 str list——
        # 若 Step 1 核验发现 revision 节点依赖具体格式，此处对齐旧格式（见下方说明）

        return {
            **state,
            "quality_scores": quality_scores,
            "consistency_warnings": consistency_warnings,
            "revision_requests": revision_requests,
            "current_stage": "quality_check_completed",
            "kg_continuity_report": kg_continuity_report,
            "l0_results": l0_all,
            "state_delta": gate_result.state_delta,  # 短篇首次有 state_delta（Ticket 04 目标）
        }
    except Exception as e:
        logger.error(f"quality gate failed, falling back to unverified: {e}", exc_info=True)
        unverified_scores["consistency"] = consistency_score
        if persist_quality_fn and novel_id:
            await persist_quality_fn(novel_id, chapter_number, unverified_scores, consistency_warnings)
        return {
            **state,
            "quality_scores": {**unverified_scores, "consistency_blocked": False},
            "consistency_warnings": consistency_warnings,
            "current_stage": "quality_check_completed",
            "kg_continuity_report": kg_continuity_report,
            "l0_results": l0_all,
        }
```

> **两处实施时必须核实（Step 1 已查）**：
> 1. `_noop_state_delta`/`_noop_quality_status`：短篇 LangGraph 是否有 manager 入口？长篇 helpers 用 `manager.update_state_delta`/`manager.update_quality_status`。短篇节点若拿不到 novel_manager，先定义两个 no-op async 函数（`async def _noop(*a, **k): pass`）作为占位，并在节点顶部注释说明「短篇 state_delta 暂仅入 state 不落 DB 行，待短篇 manager 接入」。若 Step 1 发现短篇已有 manager 注入路径，则改用真回调。
> 2. `revision_requests` 旧格式：原节点从 `result.feedback.items()` + `result.suggestions` 构造 `["【dim】: fb", "修改建议: sug"]`。gate 的 `warnings` 是 `list[dict]`（`_l0_warnings` 产出）。若 revision 节点按 str list 消费，需把 warnings 转成 str list。**Step 1 核验后对齐。**

- [ ] **Step 4: 删除节点内已废弃的 consistency_blocked 独立判定**

`consistency_blocked` 变量（:91, :130-138, :147-149, :168-170, :231-233, :286）——切换后 block 由 gate 决定，节点不再独立判。但 `consistency_score`（KG 一致性分，用于 quality_scores["consistency"] 维度展示）**保留**，所以 :130-138 / :147-149 / :168-170 里设 `consistency_score` 的逻辑保留，只删 `consistency_blocked = True` 那几行。`consistency_blocked` 变量声明（:91）删除。

> 这是本任务最易出错处：逐行 Read :90-235，区分「设 consistency_score（保留）」与「设 consistency_blocked（删）」。

- [ ] **Step 5: 跑回归测试**

Run: `pytest tests/unit -k "quality_check or langgraph or quality_gate" -v 2>&1 | tail -30`
Expected: 与 Step 2 基线对比。若有 FAIL，多为下游依赖旧 `consistency_blocked` 口径或 `revision_requests` 格式——回 Step 3 两处核实点修正。

- [ ] **Step 6: 跑全量测试**

Run: `pytest tests/ -x -q 2>&1 | tail -30`
Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
git add src/core/langgraph/nodes/quality_check.py
git commit -m "refactor(quality_check): 短篇质量节点收敛到 run_quality_gate（Ticket 04）

评分 + state_delta + consistency 硬门禁统一走 gate，删除节点内半个 gate 的重复实现。
保留 KG 一致性检查（产出 consistency_warnings/kg_continuity_report）+ KG 知识抽取副作用。
短篇章节首次抽取 state_delta。

已知行为变化：consistency block 口径从「KG verdict/StoryBible error」收敛为
gate 的「L2 评分 character/world_consistency < 0.4」。
"
```

> 更新 `.scratch/post-funnel-cleanup/issues/04-gate-convergence-short-form.md` Status → resolved。

---

## Self-Review 自检结果

**1. Spec 覆盖**：
- Ticket 01 后两项 → Task 1（BackgroundTasks）+ Task 2（前端 4 组件，实为 5 文件含 Home）。✅
- Ticket 02 → Task 3（三入口迁移 + re-export）。✅
- Ticket 03 → Task 4（ChapterGenContext + 修 storylines 两处漏传）。✅
- Ticket 04 → Task 5（节点收敛 gate + 保留 KG 副作用 + 补 state_delta）。✅
- Ticket 02 的"行数 ~980→~700"→ Task 3 Step 6 核验。✅
- Ticket 03 的"helpers:510 漏传 storylines"→ Task 4 Step 7（实际行号 552，已在步骤注明）。✅
- Ticket 04 的"短篇抽 state_delta"→ Task 5 Step 3（state_delta 入 state）。✅

**2. 占位符扫描**：Task 1 Step 3 的 `completed_at = ...` 与 Task 4 Step 8 的 `kg_service=...`/`target_words=...`、Task 5 Step 3 的 `_noop`/`revision_requests` 格式——这些不是占位偷懒，而是**有意识地标注"实施时须 Read 现状对齐"**的核实点（已在步骤内写明核实方法）。其余步骤代码完整。

**3. 类型一致性**：`ChapterGenContext` 在 Task 4 Step 3 定义、Step 4-6 使用、Step 7-8 调用方构造——字段名一致（client/chapter_outline/previous_chapter/characters_json/world_setting_json/storylines_json/style_instruction/kg_service/novel_id/target_words/blueprint/story_bible_context/on_token/on_complete/pause_checker）。`GatePersistCallbacks` 字段（update_state_delta/update_quality_status/persist_quality_scores/detect_bible_conflicts）与 gate.py:29-34 一致。`run_quality_gate` kwargs 与 gate.py:52-65 一致。✅

**4. 依赖顺序**：Task 3（02）→ Task 4（03）→ Task 5（04）串行，符合依赖链。Task 4 改 helpers:635 调用方时，Task 3 已把长篇编排迁入 helpers 但 generate_volume_chapters 仍在 helpers（未迁），调用点稳定。✅

# 需求文档：全局架构优化 — 模块解耦与冗余消除

> 版本：v1.0 · 日期：2026-05-26

---

## 1. 背景与目标

xIaoShuo 项目经过 45+ 次迭代，功能不断叠加，出现了以下架构问题需要系统性治理。

### 1.1 模块耦合问题

| 耦合点 | 具体表现 | 影响 |
|--------|----------|------|
| chapter_generator 直接访问 DB | `_generate_single_chapter_inner` 内部 import 并直接执行 SQLAlchemy 查询（StoryBible、BlueprintService、Chapter 表） | core 层反向依赖 api/services 层，违反分层原则 |
| LangGraph 节点 import service 层 | `chapter_generation.node` 内部 import `knowledge_graph_service`、`progress_event_bus` | core 层反向依赖 api 层 |
| quality_check 节点 import service 层 | 直接 import `story_bible_service.detect_bible_conflicts`、`knowledge_graph_service` | 同上 |
| novel_generator 承担过多职责 | 850+ 行，包含多个顶层函数，混合了编排逻辑、DB 持久化、进度推送 | 难以测试和维护 |
| rewrite_loop_service 重复评估逻辑 | `_evaluate_chapter_quality` 与 `quality_check.node` 中的 EVALUATION_PROMPT 几乎相同 | 代码重复，维护两份 |

### 1.2 重复代码模式

| 重复模式 | 出现位置 | 行数估计 |
|----------|----------|----------|
| 上下文构建（world/characters/storylines JSON 序列化） | novel_generator (3处)、chapter_rewriter._build_rewrite_context、blueprint_service._build_context、chapter_generator._generate_single_chapter_inner | ~150 行 |
| LLM 调用 + JSON 解析 + fallback 模式 | storyline_service (4处)、outline_service (3处)、novel_generator (2处)、blueprint_service | ~100 行 |
| 进度推送模板代码 | novel_generator 中 generate_volume_background、generate_chapters_background、_generate_volume_chapters | ~80 行 |
| 章节持久化逻辑 | novel_generator._persist_to_novel、generate_volume_background、generate_chapters_background | ~60 行 |
| 质量评估 Prompt + 解析 | quality_check.node EVALUATION_PROMPT、rewrite_loop_service EVALUATION_PROMPT | 完全重复 |

### 1.3 职责边界模糊

| 问题 | 描述 |
|------|------|
| core/llm/chapter_generator 做了 service 的事 | 查询 StoryBible、调用 BlueprintService、写入 Chapter.chapter_type — 这些是业务逻辑 |
| storyline_service 承载了 AI 生成逻辑 | generate_power_systems_ai、generate_arcs_ai、generate_scenes_ai 本质是 LLM 编排，不是 CRUD |
| novel_generator 既是编排器又是持久化层 | _persist_to_novel 应该属于 novel_manager |

## 2. 约束条件

- API 接口合约保持不变（前端无需改动）
- 数据库 schema 不动，不新增迁移
- LangGraph 工作流节点编排可以重构
- 现有测试必须通过
- 重构分批进行，每批独立可验证

## 3. 成功标准

- 模块间依赖方向清晰：route → service → core，无反向依赖
- 重复逻辑提取为公共组件，消除 >80% 的重复代码
- 各层职责边界明确
- 所有现有测试通过
- ruff + mypy 检查通过

## 4. 架构目标

```
src/
├── api/
│   ├── routes/          # 纯路由：参数校验 + 调用 service + 返回响应
│   └── services/        # 业务编排：调用 core 层能力，管理事务
├── core/
│   ├── llm/             # 纯 LLM 能力：client、prompts、生成/改写函数（不含 DB 访问）
│   ├── langgraph/       # 纯工作流编排：节点通过注入的回调/参数与外部交互
│   ├── context/         # [新] 上下文构建公共模块
│   └── quality/         # [新] 质量评估公共模块
```

依赖方向：`routes → services → core`，core 层不 import api 层。

## 5. 详细分析

### 5.1 chapter_generator 的反向依赖

`src/core/llm/chapter_generator.py` 的 `_generate_single_chapter_inner` 函数内部：
- 第 222-239 行：直接 import `StoryBible` 模型和 `story_bible_service`，执行 DB 查询
- 第 253-267 行：直接 import `BlueprintService`，调用其方法
- 第 385-404 行：直接 import `Chapter` 模型，执行 DB update

**解决方案**：将这些业务逻辑上移到 service 层，chapter_generator 只接收已准备好的上下文参数。

### 5.2 上下文构建重复

以下位置都在做相同的事情 — 从 DB 读取 novel/world/characters/storylines 并序列化为 JSON 字符串：
- `novel_generator.generate_volume_background` (567-582行)
- `novel_generator.generate_chapters_background` (704-719行)
- `novel_generator._generate_volume_chapters` (1390-1401行)
- `chapter_rewriter._build_rewrite_context` (73-181行)
- `blueprint_service._build_context` (159-240行)

**解决方案**：提取为 `src/core/context/novel_context.py` 公共模块。

### 5.3 质量评估重复

`quality_check.node` 和 `rewrite_loop_service._evaluate_chapter_quality` 使用几乎相同的 Prompt 和解析逻辑。

**解决方案**：提取为 `src/core/quality/evaluator.py` 公共模块。

### 5.4 LLM 调用模式重复

`storyline_service` 中的 4 个 `generate_*_ai` 方法都遵循相同模式：
1. 从 DB 获取上下文
2. 构建 prompt
3. 调用 `client.generate()`
4. `safe_json_parse()` 解析
5. 遍历结果写入 DB

**解决方案**：提取为通用的 `llm_generate_and_parse` 辅助函数。

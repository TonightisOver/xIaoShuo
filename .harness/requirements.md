# 需求文档：章节节奏控制与定向改写闭环

> 版本：v1.0 · 日期：2026-05-25

---

## 需求概述

在现有章节生成 + 八维质量评估基础上，建设"章节蓝图规划 → 定向改写 → 评分闭环"三层能力，使平台从"自动生成内容"升级为"辅助作者持续生产、检查、修改和管理百万字长篇网文的创作工作台"。

## 核心目标

1. 每章生成前产出结构化"章节蓝图"(Chapter Blueprint)，明确功能类型、剧情目标、爽点设计、伏笔处理和章末钩子
2. 生成后将八维质量评估低分项自动转化为具体改写动作指令
3. 提供定向改写 API，支持局部重写、节奏压缩、爽点增强、人物一致性修复和水文删减
4. 改写后重新评分，验证改善效果，支持多轮迭代直到达标

---

## 功能需求

### FR-1: 章节蓝图 (Chapter Blueprint)

**描述**: 在章节正文生成前，为每章创建结构化蓝图，作为生成约束注入 prompt。

**蓝图字段**:
| 字段 | 类型 | 说明 |
|------|------|------|
| chapter_type | enum | 章节功能类型: main_advance / climax / aftermath / daily / setup |
| plot_goal | string | 本章剧情推进目标 |
| hook_design | string | 爽点/冲突设计 |
| foreshadow_actions | list[dict] | 伏笔操作: {action: plant/callback/advance, name, detail} |
| cliffhanger | string | 章末钩子描述 |
| pacing_target | enum | 节奏定位: fast / medium / slow |
| key_characters | list[string] | 本章核心出场人物 |
| word_target | int | 本章目标字数 |

**行为**:
- 蓝图由 LLM 根据卷纲/章纲 + 前章上下文 + StoryBible 自动生成
- 蓝图持久化到数据库 (新增 ChapterBlueprint model)
- 蓝图注入章节生成 prompt，替代现有 CHAPTER_PLANNING_PROMPT 的非结构化输出
- 支持用户手动编辑蓝图后再触发生成

**与现有系统的关系**:
- 替代 `chapter_generator.py` 中的 `CHAPTER_PLANNING_PROMPT` 非结构化规划
- 复用 `Chapter.chapter_type` 字段
- 复用 StoryBible 约束抽取逻辑

### FR-2: 质量→改写动作转化 (Quality-to-Action Mapping)

**描述**: 将八维评分低分项自动映射为具体的改写动作指令。

**映射规则**:
| 维度 | 阈值 | 改写动作 | 动作类型 |
|------|------|----------|----------|
| advancement < 0.5 | 低 | "主线停滞，需增加推进事件" | enhance_plot |
| pacing < 0.5 | 低 | "节奏拖沓，需压缩/删减" | compress_pacing |
| conflict < 0.5 | 低 | "缺乏爽点，需增强冲突" | enhance_hook |
| character_consistency < 0.5 | 低 | "人物漂移，需修复对话/行为" | fix_character |
| readability < 0.5 | 低 | "水文过多，需精简" | trim_filler |
| foreshadowing < 0.5 | 低 | "伏笔缺失，需补充伏笔" | add_foreshadow |
| world_consistency < 0.5 | 低 | "设定冲突，需修正" | fix_world |
| trope_alignment < 0.5 | 低 | "爽感不足，需强化套路" | enhance_trope |

**行为**:
- 质量评估完成后自动生成 rewrite_actions 列表
- 每个 action 包含: {action_type, dimension, score, instruction, priority}
- 按 priority 排序（分数越低优先级越高）
- 持久化到 ChapterBlueprint 或独立表

### FR-3: 定向改写 API (Targeted Rewrite)

**描述**: 在现有 `rewrite_chapter_segment` 基础上，新增按改写类型的批量定向改写能力。

**改写类型**:
| 类型 | 说明 | 改写策略 |
|------|------|----------|
| rewrite_section | 局部重写 | 对指定段落按指令重写 |
| compress_pacing | 节奏压缩 | 删减冗余描写，压缩对话，加快叙事 |
| enhance_hook | 爽点增强 | 增加冲突、悬念、反转 |
| fix_character | 人物一致性修复 | 修正不符合人设的对话/行为 |
| trim_filler | 水文删减 | 删除重复描写、车轱辘话、无意义段落 |
| enhance_plot | 主线推进增强 | 增加推进主线的事件/信息 |
| add_foreshadow | 伏笔补充 | 在合适位置植入伏笔 |
| fix_world | 设定修正 | 修正违反世界观的内容 |

**API 设计**:
- `POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/targeted-rewrite`
- 请求体: `{rewrite_type, instruction?, auto_actions?: bool}`
- 当 `auto_actions=true` 时，自动执行 FR-2 生成的所有改写动作
- 改写后自动创建新版本 (复用 ChapterVersion)

**与现有系统的关系**:
- 扩展现有 `chapter_rewriter.py`，新增按类型的 prompt 模板
- 复用 `_build_rewrite_context` 上下文构建
- 复用 ChapterVersion 版本管理

### FR-4: 改写闭环 (Rewrite Loop)

**描述**: 改写后重新评分，验证改善效果，支持多轮迭代。

**行为**:
- 定向改写完成后，自动触发八维质量重评
- 对比改写前后分数，记录改善幅度
- 若仍有低分项（< 0.5），生成新一轮改写动作
- 最多迭代 N 轮（默认 3 轮），防止无限循环
- 每轮结果记录到 rewrite_history

**API 设计**:
- `POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/auto-improve`
- 请求体: `{max_iterations?: int, target_score?: float, dimensions?: list[str]}`
- 返回: `{iterations_done, final_scores, improvement_history}`

---

## 非功能需求

### NFR-1: 性能
- 单章蓝图生成 < 15s
- 单次定向改写 < 60s
- 自动改善闭环（3轮）< 5min

### NFR-2: 数据完整性
- 每次改写创建新版本，不覆盖原文
- 蓝图与章节一一对应，支持历史查询

### NFR-3: 可观测性
- 改写闭环每轮进度通过 SSE/WebSocket 推送
- 蓝图生成和改写动作记录日志

---

## 技术约束

- 复用现有 LLM client (`src/core/llm/client.py`)
- 复用现有 ChapterVersion 版本管理
- 复用现有八维质量评估 (`quality_check.py`)
- 新增 DB model 需提供 Alembic migration
- API 路由挂载到现有 projects router
- 测试覆盖: 每个 service 函数至少 1 个 unit test

---

## 影响范围

| 模块 | 变更类型 |
|------|----------|
| `src/api/models/db_models.py` | 新增 ChapterBlueprint model |
| `src/core/llm/prompts.py` | 新增蓝图生成 prompt、定向改写 prompt 模板 |
| `src/core/llm/chapter_generator.py` | 改造：使用结构化蓝图替代非结构化规划 |
| `src/core/llm/chapter_rewriter.py` | 扩展：新增按类型的定向改写函数 |
| `src/api/services/` | 新增 blueprint_service.py、rewrite_loop_service.py |
| `src/api/routes/projects.py` | 新增 3 个 API endpoint |
| `src/core/langgraph/nodes/quality_check.py` | 扩展：输出 rewrite_actions |
| `tests/` | 新增对应 unit tests |
| `alembic/` | 新增 migration |

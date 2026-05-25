# 任务清单：章节节奏控制与定向改写闭环

> 对应需求：`.harness/requirements.md` v1.0
> 日期：2026-05-25

---

## 任务总览
- 总任务数：11
- 预估复杂度：高
- 预估工时：3-4 天

## 任务依赖图

```
T1 (DB Model) ──┬──> T3 (Blueprint Service)
                │         │
                │         ├──> T5 (章节生成改造)
                │         │
T2 (Prompts) ──┘         └──> T7 (Blueprint API)
                │
                ├──> T4 (Quality-to-Action)
                │         │
                │         └──> T6 (定向改写引擎)
                │                   │
                │                   ├──> T8 (改写 API)
                │                   │
                │                   └──> T9 (改写闭环)
                │
                └──> T10 (Migration)

T11 (Unit Tests) 依赖 T3-T9 全部完成
```

---

## T1: 新增 ChapterBlueprint 数据模型

**文件**: `src/api/models/db_models.py`
**依赖**: 无
**变更**:
- 新增 `ChapterBlueprint` SQLAlchemy model
- 字段: novel_id, chapter_number, chapter_type, plot_goal, hook_design, foreshadow_actions(JSON), cliffhanger, pacing_target, key_characters(JSON), word_target, rewrite_actions(JSON), is_active(bool), created_at, updated_at
- 唯一约束: (novel_id, chapter_number, is_active) 或 (novel_id, chapter_number) + version

**验收标准**:
- `python -c "from src.api.models.db_models import ChapterBlueprint"` 无报错
- model 字段与 requirements FR-1 蓝图字段一一对应

---

## T2: 新增蓝图生成与定向改写 Prompt 模板

**文件**: `src/core/llm/prompts.py`
**依赖**: 无
**变更**:
- 新增 `BLUEPRINT_GENERATION_PROMPT`: 输入卷纲/章纲 + 前章摘要 + StoryBible + KG上下文，输出结构化 JSON 蓝图
- 新增 `TARGETED_REWRITE_PROMPTS`: dict，按 rewrite_type 索引，每种类型一个专用 prompt 模板
  - compress_pacing: 指导 LLM 压缩节奏
  - enhance_hook: 指导 LLM 增强爽点
  - fix_character: 指导 LLM 修复人物一致性
  - trim_filler: 指导 LLM 删减水文
  - enhance_plot: 指导 LLM 增强主线推进
  - add_foreshadow: 指导 LLM 补充伏笔
  - fix_world: 指导 LLM 修正设定

**验收标准**:
- `python -c "from src.core.llm.prompts import BLUEPRINT_GENERATION_PROMPT, TARGETED_REWRITE_PROMPTS"` 无报错
- BLUEPRINT_GENERATION_PROMPT 输出格式为 JSON，包含 FR-1 定义的所有字段
- TARGETED_REWRITE_PROMPTS 包含 7 种改写类型的 key

---

## T3: 实现 Blueprint Service

**文件**: `src/api/services/blueprint_service.py` (新建)
**依赖**: T1, T2
**变更**:
- `generate_blueprint(novel_id, chapter_number, chapter_outline, volume_context)` → ChapterBlueprint
  - 调用 LLM 生成结构化蓝图
  - 解析 JSON 响应
  - 持久化到 DB
- `get_blueprint(novel_id, chapter_number)` → ChapterBlueprint | None
- `update_blueprint(novel_id, chapter_number, updates: dict)` → ChapterBlueprint
  - 支持用户手动编辑蓝图字段

**验收标准**:
- `pytest tests/unit/test_blueprint_service.py` 通过
- generate_blueprint 返回包含所有蓝图字段的对象
- 蓝图持久化后可通过 get_blueprint 查询

---

## T4: 实现 Quality-to-Action 映射逻辑

**文件**: `src/api/services/quality_action_service.py` (新建)
**依赖**: T1
**变更**:
- `generate_rewrite_actions(quality_scores: dict, threshold: float = 0.5)` → list[RewriteAction]
  - 遍历八维评分，低于阈值的维度生成对应 RewriteAction
  - RewriteAction: {action_type, dimension, score, instruction, priority}
  - priority = 1.0 - score（分数越低优先级越高）
  - 按 priority 降序排列
- `persist_actions(novel_id, chapter_number, actions)` → None
  - 将 actions 写入 ChapterBlueprint.rewrite_actions

**验收标准**:
- `pytest tests/unit/test_quality_action_service.py` 通过
- 输入 `{"advancement": 0.3, "pacing": 0.4, "conflict": 0.8}` 时，生成 2 个 action（advancement 和 pacing），conflict 不生成
- actions 按 priority 正确排序

---

## T5: 改造章节生成流程使用结构化蓝图

**文件**: `src/core/llm/chapter_generator.py`
**依赖**: T3
**变更**:
- 在 `_generate_single_chapter_inner` 中：
  - 将现有"双级联第1阶段"（CHAPTER_PLANNING_PROMPT 调用）替换为调用 `blueprint_service.generate_blueprint`
  - 将蓝图 JSON 格式化后注入正文生成 prompt（替代现有非结构化 chapter_plan 文本）
  - 保留 StoryBible 和 KG 上下文检索逻辑不变
- 蓝图注入格式: 将蓝图各字段以结构化方式嵌入 prompt

**验收标准**:
- `pytest tests/unit/test_chapter_generator.py` 通过（如有）
- 生成流程调用 blueprint_service 而非直接调用 CHAPTER_PLANNING_PROMPT
- 生成的章节 prompt 中包含蓝图的 chapter_type、plot_goal、hook_design 等字段

---

## T6: 扩展定向改写引擎

**文件**: `src/core/llm/chapter_rewriter.py`
**依赖**: T2
**变更**:
- 新增 `targeted_rewrite(novel_id, chapter_number, rewrite_type, instruction?)` → str
  - 根据 rewrite_type 选择对应 prompt 模板
  - 复用 `_build_rewrite_context` 获取上下文
  - 对整章内容执行定向改写（非片段级）
  - 返回改写后的完整章节内容
- 新增 `batch_targeted_rewrite(novel_id, chapter_number, actions: list[RewriteAction])` → str
  - 按 priority 顺序依次执行多个改写动作
  - 每次改写基于上一次的输出
  - 返回最终内容

**验收标准**:
- `pytest tests/unit/test_chapter_rewriter.py` 通过
- targeted_rewrite 对 compress_pacing 类型使用对应 prompt
- batch_targeted_rewrite 按顺序执行多个 action

---

## T7: 新增蓝图 API Endpoint

**文件**: `src/api/routes/projects.py`
**依赖**: T3
**变更**:
- `GET /api/v1/projects/{novel_id}/chapters/{chapter_number}/blueprint`
  - 返回当前章节蓝图
- `PUT /api/v1/projects/{novel_id}/chapters/{chapter_number}/blueprint`
  - 用户手动编辑蓝图
- `POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/blueprint/generate`
  - 触发 LLM 生成蓝图（不触发章节生成）

**验收标准**:
- 三个 endpoint 可正常响应（200/201）
- GET 返回蓝图 JSON 包含所有字段
- PUT 更新后 GET 返回更新值

---

## T8: 新增定向改写 API Endpoint

**文件**: `src/api/routes/projects.py`
**依赖**: T4, T6
**变更**:
- `POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/targeted-rewrite`
  - 请求体: `{rewrite_type: str, instruction?: str, auto_actions?: bool}`
  - 当 auto_actions=true: 读取 ChapterBlueprint.rewrite_actions 并批量执行
  - 当指定 rewrite_type: 执行单次定向改写
  - 改写后自动创建 ChapterVersion (source="ai_rewrite")
  - 返回: `{new_version_number, word_count, rewrite_type}`

**验收标准**:
- endpoint 可正常响应
- 改写后 ChapterVersion 表新增一条记录
- 返回体包含 new_version_number

---

## T9: 实现改写闭环 Service + API

**文件**: `src/api/services/rewrite_loop_service.py` (新建), `src/api/routes/projects.py`
**依赖**: T4, T6
**变更**:
- `auto_improve_chapter(novel_id, chapter_number, max_iterations=3, target_score=0.6, dimensions=None)` → dict
  - 循环逻辑:
    1. 调用质量评估获取当前分数
    2. 调用 generate_rewrite_actions 生成改写动作
    3. 调用 batch_targeted_rewrite 执行改写
    4. 创建新版本
    5. 重新评估质量
    6. 若所有维度 >= target_score 或达到 max_iterations，停止
  - 返回: {iterations_done, final_scores, improvement_history: [{iteration, scores_before, scores_after, actions_taken}]}
- 新增 API endpoint:
  - `POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/auto-improve`
  - 请求体: `{max_iterations?: int, target_score?: float, dimensions?: list[str]}`

**验收标准**:
- `pytest tests/unit/test_rewrite_loop_service.py` 通过
- 当所有维度 >= target_score 时，循环在第 1 轮停止
- 当达到 max_iterations 时强制停止
- improvement_history 记录每轮分数变化

---

## T10: Alembic Migration

**文件**: `alembic/versions/xxx_add_chapter_blueprint.py` (新建)
**依赖**: T1
**变更**:
- 创建 `chapter_blueprints` 表
- 添加索引: (novel_id, chapter_number)

**验收标准**:
- `alembic upgrade head` 无报错
- `alembic downgrade -1` 可回滚

---

## T11: Unit Tests

**文件**: `tests/unit/test_blueprint_service.py`, `tests/unit/test_quality_action_service.py`, `tests/unit/test_rewrite_loop_service.py` (新建)
**依赖**: T3, T4, T6, T9
**变更**:
- test_blueprint_service: 测试蓝图生成、查询、更新
- test_quality_action_service: 测试评分→动作映射、阈值边界、排序
- test_rewrite_loop_service: 测试闭环迭代逻辑、停止条件

**验收标准**:
- `pytest tests/unit/test_blueprint_service.py tests/unit/test_quality_action_service.py tests/unit/test_rewrite_loop_service.py -v` 全部通过

---

## 执行顺序建议

**Phase 1 (基础层)**: T1 + T2 并行 → T10
**Phase 2 (服务层)**: T3 + T4 并行 → T5 + T6 并行
**Phase 3 (API 层)**: T7 + T8 并行 → T9
**Phase 4 (验证层)**: T11

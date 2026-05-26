# 编码实现报告 — CHANGE-045 章节节奏控制与定向改写闭环

**日期**: 2026-05-25
**阶段**: 3-编码实现

## 变更文件清单

### 新增文件 (4)
| 文件 | 行数 | 说明 |
|------|------|------|
| `src/api/services/blueprint_service.py` | 239 | 章节蓝图服务 |
| `src/api/services/quality_action_service.py` | 106 | 质量→改写动作映射 |
| `src/api/services/rewrite_loop_service.py` | 279 | 改写闭环服务 |
| `alembic/versions/20260525_add_chapter_blueprint.py` | 76 | DB Migration |

### 修改文件 (4)
| 文件 | +/- | 说明 |
|------|-----|------|
| `src/api/models/db_models.py` | +38 | 新增 ChapterBlueprint model |
| `src/core/llm/prompts.py` | +181 | 蓝图生成 + 8种改写 Prompt |
| `src/core/llm/chapter_generator.py` | +120/-10 | 蓝图集成 + 降级路径 |
| `src/core/llm/chapter_rewriter.py` | +148 | targeted_rewrite + batch |
| `src/api/routes/projects.py` | +200 | 5个新 API endpoint |

## 新增 API Endpoints (5)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/projects/{novel_id}/chapters/{ch}/blueprint` | 获取蓝图 |
| PUT | `/api/v1/projects/{novel_id}/chapters/{ch}/blueprint` | 编辑蓝图 |
| POST | `/api/v1/projects/{novel_id}/chapters/{ch}/blueprint/generate` | 生成蓝图 |
| POST | `/api/v1/projects/{novel_id}/chapters/{ch}/targeted-rewrite` | 定向改写 |
| POST | `/api/v1/projects/{novel_id}/chapters/{ch}/auto-improve` | 自动改善闭环 |

## 架构决策

1. **蓝图降级路径**: 当 BlueprintService 不可用时，自动降级到原有 CHAPTER_PLANNING_PROMPT
2. **独立质量评估**: rewrite_loop_service 内置独立的 LLM 质量评估，不依赖 LangGraph pipeline
3. **版本管理复用**: 所有改写操作复用 ChapterVersion (source="ai_rewrite")
4. **批量改写链式执行**: batch_targeted_rewrite 按优先级顺序链式执行，每步输出作为下步输入

## 评审建议纳入情况

| 建议 | 状态 |
|------|------|
| Blueprint 保留降级路径 | 已实现 |
| 新旧改写 API 共存 | 已实现（现有 rewrite 保留） |
| auto-improve 终止条件 | 已实现（达标或无改善动作时停止） |
| Blueprint.chapter_type → Chapter.chapter_type 同步 | 已实现 |
| T10 Migration 提前执行 | 已完成 |

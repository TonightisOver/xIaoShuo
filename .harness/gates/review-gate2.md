# Gate 2 — 交付确认 | CHANGE-045 章节节奏控制与定向改写闭环

**日期**: 2026-05-26
**分支**: feature/change-044-long-form-generation
**提交**: 76a9dab, 99ecdb1

---

## 需求摘要

为长篇小说生成系统新增「章节蓝图」与「定向改写闭环」能力：
1. 章节蓝图（Blueprint）：在生成前规划节奏、伏笔、冲突点
2. 质量→动作映射：将质量评分自动转化为改写指令
3. 定向改写闭环：针对性改写 + 自动迭代直到达标

## 代码变更清单

### 新增文件 (7)
| 文件 | 说明 |
|------|------|
| `src/api/services/blueprint_service.py` | 章节蓝图服务 (239行) |
| `src/api/services/quality_action_service.py` | 质量→改写动作映射 (106行) |
| `src/api/services/rewrite_loop_service.py` | 改写闭环服务 (279行) |
| `alembic/versions/20260525_add_chapter_blueprint.py` | DB Migration |
| `tests/unit/test_blueprint_service.py` | 蓝图服务测试 (6 cases) |
| `tests/unit/test_quality_action_service.py` | 质量动作测试 (8 cases) |
| `tests/unit/test_rewrite_loop_service.py` | 改写闭环测试 (4 cases) |

### 修改文件 (5)
| 文件 | 说明 |
|------|------|
| `src/api/models/db_models.py` | +ChapterBlueprint model |
| `src/api/routes/projects.py` | +5 API endpoints |
| `src/core/llm/chapter_generator.py` | 蓝图集成 + 降级路径 |
| `src/core/llm/chapter_rewriter.py` | targeted_rewrite + batch |
| `src/core/llm/prompts.py` | 蓝图生成 + 8种改写 Prompt |

**总计**: +2205 行 / -51 行

## 新增 API Endpoints

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/projects/{id}/chapters/{ch}/blueprint` | 获取蓝图 |
| PUT | `/projects/{id}/chapters/{ch}/blueprint` | 编辑蓝图 |
| POST | `/projects/{id}/chapters/{ch}/blueprint/generate` | 生成蓝图 |
| POST | `/projects/{id}/chapters/{ch}/targeted-rewrite` | 定向改写 |
| POST | `/projects/{id}/chapters/{ch}/auto-improve` | 自动改善闭环 |

## 测试结果

- 18 个单元测试全部通过 (1.22s)
- ruff lint: import 排序已修复，E501 行长度为中文 prompt 字符串（不影响功能）

## 架构决策

1. Blueprint 降级路径：LLM 不可用时自动回退到原有 CHAPTER_PLANNING_PROMPT
2. 改写闭环独立质量评估：不依赖 LangGraph pipeline
3. 版本管理复用 ChapterVersion (source="ai_rewrite")
4. 批量改写链式执行：按优先级顺序，每步输出作为下步输入

## 部署注意事项

1. 执行 Alembic 迁移：`alembic upgrade head`（新增 chapter_blueprints 表）
2. 现有改写 API 保持不变，新旧共存

## 结论

**APPROVED** — 代码已推送，测试通过，功能完整。

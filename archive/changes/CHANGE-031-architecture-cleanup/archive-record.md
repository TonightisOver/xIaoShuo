# CHANGE-031 归档记录

- 原名称：architecture-cleanup
- 状态：completed
- 时间范围：2026-05-20
- 原路径：`.harness/changes/CHANGE-031-architecture-cleanup`
- 归档路径：`archive/changes/CHANGE-031-architecture-cleanup`
- 关联提交：
  - 1260a0f 2026-05-20 feat(CHANGE-028~031): knowledge graph, chapter display fix, architecture cleanup

## 目标

基于全项目架构审查，修复 3 个 Critical 和 5 个 High 级别问题。核心目标：消除重复代码、统一日志框架、补全数据完整性约束。

---

## 主要设计决定

## 修复顺序

1. H6 — 删除死代码配置项
2. C3 — 统一 structlog
3. C1 — 抽取 `_build_initial_state`
4. H4 — `generate_novel_background` 复用 `_run_langgraph_pipeline`
5. C2 — 抽取 `_generate_single_chapter`
6. H5 — 子资源归属校验
7. H7 + H8 — 唯一约束迁移

---

## H6. 删除死代码配置项

**文件：** `src/core/config.py`

**操作：** 删除第 34-37 行（含注释）：
```python

## 涉及模块

- `alembic/versions/20260520_add_chapter_volume_unique.py`
- `alembic/versions/20260520_add_chapter_volume_unique_constraints.py`
- `src/api/models/db_models.py`
- `src/api/routes/projects.py`
- `src/api/services/conversation_service.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `src/api/services/outline_service.py`
- `src/api/services/storyline_service.py`
- `src/api/services/task_manager.py`
- `src/core/chapter_utils.py`
- `src/core/config.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `src/core/llm/chapter_generator.py`
- `tests/integration/test_change031_architecture_api.py`
- `tests/unit/test_change031_architecture.py`
- `tests/unit/test_llm/`
- `tests/unit/test_progress_event_bus.py`

## 实施结果

基于全项目架构审查，修复 3 个 Critical 和 5 个 High 级别问题。核心目标：消除重复代码、统一日志框架、补全数据完整性约束。

---

## 测试与验证

## 1. Ruff 检查

**命令**: `ruff check <CHANGE-031 修改文件>`

**结果**: 仅 E501（行过长）警告，无逻辑错误、导入错误或安全问题。

| 文件 | E501 数量 | 说明 |
|------|-----------|------|
| `src/api/routes/projects.py` | 8 | 存量长行 + 本次新增路由参数 |
| `src/api/services/novel_generator.py` | ~15 | 存量长行为主 |
| `src/api/services/outline_service.py` | ~10 | 存量 prompt 模板 |
| `src/api/services/storyline_service.py` | 1 | 存量 |
| `src/core/llm/chapter_generator.py` | 0 | 新增文件，无警告 |
| `src/core/config.py` | 0 | 无警告 |
| `src/api/models/db_models.py` | 0 | 无警告 |

**结论**: 无 Blocker。E501 为存量代码风格问题，不影响功能。

## 2. Mypy 类型检查

**命令**: `mypy src/core/llm/chapter_generator.py src/api/services/novel_generator.py src/core/config.py src/api/models/db_models.py --ignore-missing-imports`

**结果**: 23 errors（6 files）

| 类别 | 数量 | 是否本次引入 |
|------|------|-------------|
| `no-untyped-def`（缺少类型注解） | 12 | 否，存量 |
| `no-any-return` | 2 | 否，存量 |
| `union-attr`（Optional 未 narrow） | 3 | 否，存量 |
| `call-overload`（LangGraph astream） | 1 | 否，LangGraph 类型定义问题 |
| `var-annotated`（generated_chapters） | 2 | 否，存量模式 |

**结论**: 无 Blocker。所有 mypy 错误均为存量问题，非本次变更引入。新增的 `chapter_generator.py` 无类型错误。

## 3. 专项测试

**命令**: `pytest tests/unit/test_change031_architecture.py tests/integration/test_change031_architecture_api.py -v`

**结果**: 33 passed in 6.19s

### 单元测试（23 项）
- TestBuildInitialState: 4/4 passed
- TestGenerateSingleChapter: 5/5 passed
- TestNovelIdOwnership: 4/4 passed
- TestUniqueConstraints: 2/2 passed
- TestStructlogImports: 7/7 passed
- (另有 1 项隐含在 TestGenerateSingleChapter 中)

### 集成测试（10 项）
- TestPowerSystemOwnership: 3/3 passed
- TestCharacterOwnership: 3/3 passed
- TestUniqueConstraintEnforcement: 4/4 passed

## 4. 安全检查 — H5 归属校验

已确认以下方法均包含 `novel_id` 归属校验（WHERE 条件同时匹配 id 和 novel_id）：

- `NovelManager.update_power_system(novel_id, ps_id, **kwargs)`
- `No

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `.gate1-approved`
- `.gate2-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`

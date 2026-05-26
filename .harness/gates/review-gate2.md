# Gate 2 — 交付确认 | CHANGE-048 读者视角模拟

**日期**: 2026-05-26
**分支**: feature/change-044-long-form-generation

---

## 需求摘要

读者视角模拟：模拟4种读者人设（核心粉丝、路人读者、专业评论家、网文老白）阅读章节后的结构化反馈，帮助作者预判读者反应。

## 功能实现

| 需求项 | 状态 |
|--------|------|
| FR-1: 4种读者人设定义（含差异化评价侧重） | 完成 |
| FR-2: 章节读者模拟执行（并行LLM + 结构化JSON输出） | 完成 |
| FR-3: 模拟结果存储（ReaderSimulation表） | 完成 |
| FR-4: 历史对比（同章多次模拟记录） | 完成 |
| FR-5: 前端交互（人设选择 + 结果卡片 + 历史记录） | 完成 |

## 代码变更清单

### 新增文件 (4)
| 文件 | 说明 |
|------|------|
| `src/api/services/reader_simulation_service.py` | 模拟服务核心 |
| `src/api/routes/reader_simulation.py` | 4个API端点 |
| `frontend/src/components/ReaderSimPanel.vue` | 读者模拟面板 |
| `tests/unit/test_reader_simulation_service.py` | 8个单元测试 |

### 修改文件 (4)
| 文件 | 说明 |
|------|------|
| `src/api/models/db_models.py` | +ReaderSimulation模型 |
| `src/api/routes/__init__.py` | 注册 reader_simulation_router |
| `src/api/main.py` | 挂载 reader_simulation_router |
| `frontend/src/views/ChapterEdit.vue` | 添加"读者模拟"按钮 + 引入组件 |

## 新增 API Endpoints

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{novel_id}/chapters/{ch}/reader-simulation` | 触发模拟(202) |
| GET | `/{novel_id}/chapters/{ch}/reader-simulations` | 历史列表 |
| GET | `/{novel_id}/reader-simulations/{id}` | 详细结果 |
| GET | `/{novel_id}/reader-simulation/personas` | 人设列表 |

## 测试结果

- 38 个单元测试全部通过 (1.44s)
- ruff lint: CHANGE-048 文件 0 errors
- 前端构建: 成功 (1.66s)

## 评审结论汇总

- 编码评审: APPROVED（无阻塞项）
- 测试评审: APPROVED（覆盖关键路径）
- CI验证: PASSED

## 结论

**APPROVED** — 功能完整，测试通过，代码评审无阻塞项。

**日期**: 2026-05-26
**分支**: feature/change-044-long-form-generation

---

## 需求摘要

大纲↔正文双向同步：大纲修改后自动分析影响范围，标记受影响章节，提供级联更新建议（非自动覆盖），支持用户选择性接受更新；正文生成后反向更新大纲状态（已完成/偏离标记）。

## 功能实现

| 需求项 | 状态 |
|--------|------|
| FR-1: 正向影响分析（LLM分析大纲修改对已生成章节的影响） | 完成 |
| FR-2: 建议管理（逐条/批量接受或拒绝，接受后标记章节needs_revision） | 完成 |
| FR-3: 反向偏离检测（正文与章纲偏离度评估，自动更新大纲状态） | 完成 |
| FR-4: 同步状态可视化（章节状态面板 + 建议管理UI） | 完成 |

## 代码变更清单

### 新增文件 (3)
| 文件 | 说明 |
|------|------|
| `src/api/services/outline_sync_service.py` | 同步服务核心（329行） |
| `src/api/routes/outline_sync.py` | 7个REST API端点（104行） |
| `tests/unit/test_outline_sync_service.py` | 9个单元测试（229行） |

### 修改文件 (4)
| 文件 | 说明 |
|------|------|
| `src/api/models/db_models.py` | +OutlineSyncSuggestion模型 +Outline.deviation_summary |
| `src/api/routes/__init__.py` | 注册 outline_sync_router |
| `src/api/main.py` | 挂载 outline_sync_router |
| `frontend/src/views/OutlineEditor.vue` | 同步状态面板 + 建议管理UI |

## 新增 API Endpoints

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{novel_id}/outlines/sync/analyze` | 分析大纲修改影响 |
| GET | `/{novel_id}/outlines/sync/suggestions` | 获取建议列表 |
| PUT | `/{novel_id}/outlines/sync/suggestions/{id}/accept` | 接受建议 |
| PUT | `/{novel_id}/outlines/sync/suggestions/{id}/reject` | 拒绝建议 |
| POST | `/{novel_id}/outlines/sync/suggestions/batch` | 批量操作 |
| POST | `/{novel_id}/outlines/sync/reverse` | 反向偏离检测 |
| GET | `/{novel_id}/outlines/sync/status` | 同步状态总览 |

## 测试结果

- 30 个单元测试全部通过 (1.41s)
- ruff lint: CHANGE-047 文件 0 errors
- 前端构建: 成功 (2.84s)

## 评审结论汇总

- 编码评审: APPROVED（5个Minor建议，无阻塞项）
- 测试评审: APPROVED（覆盖关键业务路径）
- CI验证: PASSED

## 技术决策

- LLM调用30s超时 + 优雅降级
- 重新分析时自动过期旧pending建议
- 数据库索引 ix_sync_novel_status 优化查询
- 单例服务模式，与项目现有模式一致

## 结论

**APPROVED** — 功能完整，测试通过，代码评审无阻塞项。建议交付。

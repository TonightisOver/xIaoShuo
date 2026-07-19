# CHANGE-030 归档记录

- 原名称：story-knowledge-graph
- 状态：completed
- 时间范围：2026-05-19 至 2026-05-20
- 原路径：`.harness/changes/CHANGE-030-story-knowledge-graph`
- 归档路径：`archive/changes/CHANGE-030-story-knowledge-graph`
- 关联提交：
  - 1260a0f 2026-05-20 feat(CHANGE-028~031): knowledge graph, chapter display fix, architecture cleanup
  - 0637259 2026-05-19 feat: improve chapter display and api robustness

## 目标

当前 xIaoShuo 平台在长篇小说生成中面临以下问题：

- **上下文遗忘**：LLM 上下文窗口有限，跨章节的人物关系、伏笔、世界观规则容易丢失
- **一致性缺陷**：角色性格突变、时间线矛盾、已死角色复活等问题频发
- **手动维护成本高**：现有 storylines/characters/world_setting 是静态设定数据，需要人工维护，无法自动跟踪章节内容的演变

现有系统已有：
- `Storyline` / `CharacterArc` / `Scene` — 手动或 AI 一次性生成的静态故事结构
- `RelationGraph.vue` — 基于上述静态数据的 D3 树形可视化
- `Character` / `WorldSetting` — 创作前设定的人物和世界观

**缺失能力**：从已生成章节文本中**自动、增量**地抽取结构化知识（实体+关系三元组），并在后续生成时**动态检索**相关上下文注入 prompt。

---

## 主要设计决定

- PostgreSQL 原生支持 JSON 字段，可存储三元组属性
- 使用关系型表（非图数据库）存储三元组，通过索引实现高效查询
- 预计单部小说三元组量级：100-2000 条（可控）

**不选择图数据库的原因**：
- 项目已有 PostgreSQL，引入 Neo4j 增加运维复杂度
- 三元组规模小（千级），关系型数据库 + 索引足够
- 查询模式固定（按实体/章节/类型），不需要复杂图遍历

## 涉及模块

- `alembic/versions/20260520_add_knowledge_graph_tables.py`
- `frontend/src/views/RelationGraph.vue`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/routes/`
- `src/api/routes/__init__.py`
- `src/api/routes/knowledge_graph.py`
- `src/api/services/`
- `src/api/services/knowledge_graph_service.py`
- `src/core/config.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `src/core/langgraph/nodes/quality_check.py`
- `src/core/langgraph/state.py`
- `src/core/llm/prompts/`
- `tests/conftest.py`
- `tests/integration/test_knowledge_graph_api.py`
- `tests/unit/test_knowledge_graph_service.py`

## 实施结果

| 类别 | 结论 |
|------|------|
| 安全性 | 通过（无 SQL 注入，prompt 注入风险低且可控） |
| 架构一致性 | 通过 |
| 代码质量 | 通过（有 P2/P3 改进建议，非阻塞） |
| 数据模型 | 通过 |
| 迁移脚本 | 通过 |

**评审结论: PASS — 可进入测试阶段**

## 测试与验证

## 变更: CHANGE-030-story-knowledge-graph
## 日期: 2026-05-19

---

## 1. Ruff 检查

| 文件 | 结果 |
|------|------|
| `src/api/services/knowledge_graph_service.py` | PASS |
| `src/api/routes/knowledge_graph.py` | PASS |
| `src/core/langgraph/nodes/chapter_generation.py` | PASS |
| `src/core/langgraph/nodes/quality_check.py` | PASS |

结论: 本次新增/修改文件无 ruff 问题。

## 2. Mypy 检查

| 文件 | 结果 | 备注 |
|------|------|------|
| `src/api/services/knowledge_graph_service.py` | PASS | 无类型错误 |
| `src/api/routes/knowledge_graph.py` | 14 warnings | `no-untyped-def` — 路由函数缺少返回类型注解 |

分析: `knowledge_graph.py` 的 14 个 `no-untyped-def` 警告与项目其他路由文件（`projects.py` 27处、`storylines.py` 18处、`outlines.py` 9处）保持一致的编码风格。这是项目存量模式，非本次引入的新问题。

结论: 本次新增文件未引入新类型错误（P3 改进建议：后续统一为路由添加返回类型注解）。

## 3. 测试执行

### 单元测试 (`tests/unit/test_knowledge_graph_service.py`)

```
22 passed in 3.91s
```

| 测试类 | 用例数 | 结果 |
|--------|--------|------|
| TestExtractFromChapter | 7 | ALL PASS |
| TestRetrieveContext | 6 | ALL PASS |
| TestCheckConsistency | 6 | ALL PASS |
| TestFormatContext | 3 | ALL PASS |

### 集成测试 (`tests/integration/test_knowledge_graph_api.py`)

```
17 passed in 8.83s
```

| 测试类 | 用例数 | 结果 |
|--------|--------|------|
| TestEntityCRUD | 7 | ALL PASS |
| TestTripleCRUD | 4 | ALL PASS |
| TestExtraction | 3 | ALL PASS |
| TestVisualization | 1 | ALL PASS |
| TestConsistencyCheck | 2 | ALL PASS |

## 4. 安全检查

### SQL 注入

- 所有数据库查询使用 SQLAlchemy ORM（`select()`, `where()`, `update()`, `delete()`），参数化查询，无原始 SQL 拼接。
- 路由层使用 Pydantic 模型验证输入，类型约束明确。
- `novel_id` 等路径参数通过 FastAPI 类型声明自动验证。

结论: 无 SQL 注入风险。

### Prompt 注入

- `chapter_text` 截断至 6000 字符（抽取）/ 3000 字符（一致性检查），限制了注入面。
- LLM prompt 使用 `.format()` 模板注入用户内容，用户内容位于明确的 `## 章节文本` 区域。
- `existing_entities_json` 通过 `json.dumps()` 序列化，不会破坏 prompt 结构。
- 风险评估: 低。用户内容（小说文本）本身就是要被

## 遗留事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 抽取准确率不足 | 图谱质量差，检索注入噪声 | 设计校验逻辑 + 人工修正 API |
| 抽取增加生成耗时 | 用户体验下降 | 异步抽取，不阻塞章节返回 |
| 三元组冲突判断误报 | 打断正常生成流程 | warning 不阻断，仅 error 阻断 |
| 与现有 storyline 数据重复 | 用户困惑 | UI 明确区分"规划数据"和"抽取数据" |

**外部依赖**：
- DeepSeek API（已有）
- PostgreSQL（已有）
- 无新增外部依赖

---

## 原始文件清单

- `.gate1-approved`
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

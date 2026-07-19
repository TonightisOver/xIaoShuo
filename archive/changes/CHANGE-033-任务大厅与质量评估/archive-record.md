# CHANGE-033 归档记录

- 原名称：任务大厅与质量评估
- 状态：completed
- 时间范围：2026-05-27
- 原路径：`.harness/changes/CHANGE-033-任务大厅与质量评估`
- 归档路径：`archive/changes/CHANGE-033-任务大厅与质量评估`
- 关联提交：
  - 413f7f0 2026-05-27 feat(CHANGE-050): 工程质量修复 — 层级边界修正与前端测试体系

## 目标

新增任务大厅页面（TaskList），支持按状态筛选所有生成任务；扩展质量检查节点为 8 维度 AI 评估系统；知识图谱服务支持实体别名匹配和状态继承。

## 主要设计决定

新增任务大厅页面（TaskList），支持按状态筛选所有生成任务；扩展质量检查节点为 8 维度 AI 评估系统；知识图谱服务支持实体别名匹配和状态继承。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/views/TaskList.vue` | 新增 | 任务大厅页面，卡片式布局，支持全部/生成中/已完成/失败筛选 |
| `frontend/src/router/index.js` | 修改 | 注册 /tasks 路由 |
| `frontend/src/App.vue` | 修改 | 导航栏增加"任务大厅"入口 |
| `src/core/langgraph/nodes/quality_check.py` | 修改 | 新增 8 维度评估 Prompt（advancement/conflict/character_consistency 等），AI 返回 JSON 评分 |
| `src/api/services/knowledge_graph_service.py` | 修改 | retrieve_context 支持实体别名匹配、状态继承合并、双向关系去重 |
| `src/api/models/db_models.py` | 修改 | 新增 KnowledgeEntityState 模型 |
| `src/api/routes/knowledge_graph.py` | 修改 | 新增实体状态相关端点 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调传递更多上下文 |
| `src/api/services/storyline_service.py` | 修改 | 写作风格纳入故事线摘要 |

## 涉及模块

- `alembic/versions/0dbde18317da_add_knowledge_entity_states.py`
- `frontend/src/App.vue`
- `frontend/src/router/index.js`
- `frontend/src/views/TaskList.vue`
- `src/api/models/db_models.py`
- `src/api/routes/knowledge_graph.py`
- `src/api/services/knowledge_graph_service.py`
- `src/api/services/novel_generator.py`
- `src/api/services/storyline_service.py`
- `src/core/langgraph/nodes/quality_check.py`
- `tests/unit/test_change033_task_list.py`
- `tests/unit/test_change034_quality_eval.py`
- `tests/unit/test_knowledge_graph_service.py`
- `tests/unit/test_live_knowledge_graph.py`

## 实施结果

新增任务大厅页面（TaskList），支持按状态筛选所有生成任务；扩展质量检查节点为 8 维度 AI 评估系统；知识图谱服务支持实体别名匹配和状态继承。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/views/TaskList.vue` | 新增 | 任务大厅页面，卡片式布局，支持全部/生成中/已完成/失败筛选 |
| `frontend/src/router/index.js` | 修改 | 注册 /tasks 路由 |
| `frontend/src/App.vue` | 修改 | 导航栏增加"任务大厅"入口 |
| `src/core/langgraph/nodes/quality_check.py` | 修改 | 新增 8 维度评估 Prompt（advancement/conflict/character_consistency 等），AI 返回 JSON 评分 |
| `src/api/services/knowledge_graph_service.py` | 修改 | retrieve_context 支持实体别名匹配、状态继承合并、双向关系去重 |
| `src/api/models/db_models.py` | 修改 | 新增 KnowledgeEntityState 模型 |
| `src/api/routes/knowledge_graph.py` | 修改 | 新增实体状态相关端点 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调传递更多上下文 |
| `src/api/services/storyline_service.py` | 修改 | 写作风格纳入故事线摘要 |

## 测试与验证

新增任务大厅页面（TaskList），支持按状态筛选所有生成任务；扩展质量检查节点为 8 维度 AI 评估系统；知识图谱服务支持实体别名匹配和状态继承。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/views/TaskList.vue` | 新增 | 任务大厅页面，卡片式布局，支持全部/生成中/已完成/失败筛选 |
| `frontend/src/router/index.js` | 修改 | 注册 /tasks 路由 |
| `frontend/src/App.vue` | 修改 | 导航栏增加"任务大厅"入口 |
| `src/core/langgraph/nodes/quality_check.py` | 修改 | 新增 8 维度评估 Prompt（advancement/conflict/character_consistency 等），AI 返回 JSON 评分 |
| `src/api/services/knowledge_graph_service.py` | 修改 | retrieve_context 支持实体别名匹配、状态继承合并、双向关系去重 |
| `src/api/models/db_models.py` | 修改 | 新增 KnowledgeEntityState 模型 |
| `src/api/routes/knowledge_graph.py` | 修改 | 新增实体状态相关端点 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调传递更多上下文 |
| `src/api/services/storyline_service.py` | 修改 | 写作风格纳入故事线摘要 |

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `summary.md`

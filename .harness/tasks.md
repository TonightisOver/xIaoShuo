# 任务清单：读者视角模拟 (CHANGE-048)

> 对应需求：`.harness/requirements.md` v1.0
> 日期：2026-05-26

---

## 任务总览
- 总任务数：7
- 预估复杂度：中
- 新增文件：5
- 修改文件：3

---

## Task-1: 新增 ReaderSimulation 数据模型

**复杂度**: S
**文件**: `src/api/models/db_models.py`
**描述**:
- 新增 `ReaderSimulation` ORM 模型
- 字段：id, novel_id(FK), chapter_number, personas_used(JSON), results(JSON), summary(Text), status(String), duration_ms(Integer), created_at
- 添加 `novel_id` + `chapter_number` 联合索引
**依赖**: 无
**验收标准**:
- `ruff check src/api/models/db_models.py` 无错误
- 模型类可正常导入
- 包含正确的索引定义

---

## Task-2: 数据库迁移脚本

**复杂度**: S
**文件**: `alembic/versions/20260526_add_reader_simulations.py`（新增）
**描述**:
- 创建 `reader_simulations` 表
- 包含所有字段和索引
**依赖**: Task-1
**验收标准**:
- 迁移脚本语法正确
- `alembic upgrade head` 可成功执行（本地验证）

---

## Task-3: 读者模拟服务层

**复杂度**: L
**文件**: `src/api/services/reader_simulation_service.py`（新增）
**描述**:
- 定义 `READER_PERSONAS` 常量字典（4 种人设，含 id/name/description/prompt_template）
- 实现 `ReaderSimulationService` 类：
  - `run_simulation(novel_id, chapter_number, personas)` — 主入口，协调整个模拟流程
  - `_build_context(novel_id, chapter_number)` — 获取章节内容 + 前章摘要 + 人物设定
  - `_simulate_single_persona(persona, context)` — 单个人设的 LLM 调用 + JSON 解析
  - `_generate_summary(results)` — 可选：生成综合摘要
- 使用 `asyncio.gather` 并行执行多人设模拟
- 单个人设失败不影响整体，标记为 error
- 提供 `get_reader_simulation_service()` 工厂函数
**依赖**: Task-1
**验收标准**:
- `ruff check` 通过
- 服务可正常实例化
- LLM prompt 包含人设注入和结构化输出要求
- 错误处理覆盖：LLM 超时、JSON 解析失败、章节为空

---

## Task-4: API 路由层

**复杂度**: M
**文件**: `src/api/routes/reader_simulation.py`（新增）
**描述**:
- `POST /{novel_id}/chapters/{chapter_number}/reader-simulation` — 触发模拟
  - 请求体：`ReaderSimulationRequest(personas: list[str] | None)`
  - 使用 BackgroundTasks 异步执行模拟
  - 返回 202 + simulation_id
- `GET /{novel_id}/chapters/{chapter_number}/reader-simulations` — 获取历史列表
- `GET /{novel_id}/reader-simulations/{simulation_id}` — 获取详细结果
- 路由前缀：`/api/v1/projects`
- Pydantic request/response 模型定义在路由文件内
**依赖**: Task-3
**验收标准**:
- `ruff check` 通过
- 路由可正常注册
- 请求/响应模型验证正确
- 章节不存在时返回 404

---

## Task-5: 路由注册

**复杂度**: S
**文件**: `src/api/routes/__init__.py`, `src/api/main.py`
**描述**:
- 在 `__init__.py` 中导出 `reader_simulation_router`
- 在 `main.py` 中注册路由
**依赖**: Task-4
**验收标准**:
- 应用启动无报错
- `/docs` 中可看到新增的 3 个端点

---

## Task-6: 前端读者模拟面板

**复杂度**: M
**文件**: `frontend/src/components/ReaderSimPanel.vue`（新增）
**描述**:
- 人设选择区：4 个 checkbox + 全选/取消
- "开始模拟"按钮，点击调用 POST API
- Loading 状态展示
- 结果展示：每个人设一张卡片
  - 卡片内容：engagement 分数、情感反应、节奏评价、爽点/痛点列表、总评
- 历史记录折叠区域
- API 调用使用 fetch/axios，轮询或 polling 获取结果（模拟完成后刷新）
**依赖**: Task-4
**验收标准**:
- 组件可正常渲染
- 人设选择交互正确
- Loading/结果/错误三种状态切换正常
- 样式符合项目 Tailwind 风格

---

## Task-7: 集成到章节编辑页 + 单元测试

**复杂度**: M
**文件**: `frontend/src/views/ChapterEdit.vue`（修改）, `tests/unit/test_change048_reader_simulation.py`（新增）
**描述**:
- 在 ChapterEdit.vue 中引入 ReaderSimPanel 组件，添加入口按钮
- 编写单元测试覆盖：
  - Service 层：模拟 LLM 返回，验证 JSON 解析和错误处理
  - Route 层：验证请求验证、404 处理、正常流程
  - 人设常量完整性检查
**依赖**: Task-5, Task-6
**验收标准**:
- `pytest tests/unit/test_change048_reader_simulation.py` 全部通过
- ChapterEdit 页面可正常显示读者模拟入口
- `ruff check` 全项目通过

---

## 依赖关系图

```
Task-1 (DB Model)
  ├── Task-2 (Migration)
  └── Task-3 (Service)
        └── Task-4 (Routes)
              ├── Task-5 (Registration)
              └── Task-6 (Frontend Panel)
                    └── Task-7 (Integration + Tests)
```

---

## 实现注意事项

1. **LLM Prompt 设计**是本功能的核心，Task-3 中需精心设计每个人设的 system prompt，确保输出稳定的 JSON 格式
2. **JSON 解析容错**：LLM 可能返回非标准 JSON，需用 `json_utils.py` 中已有的容错解析
3. **上下文长度控制**：章节内容 + 前章摘要 + 人设 prompt 需控制总 token 数，超长时截取
4. **前端轮询**：由于模拟是后台执行，前端需轮询 GET 接口直到 status=completed/failed

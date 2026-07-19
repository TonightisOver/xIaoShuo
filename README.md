# xIaoShuo — AI 网络小说多智能体共创平台

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue.js-3.4+-4fc08d.svg)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

基于 **LangGraph 多智能体协同流** 与 **活态时空知识图谱** 的 AI 网络小说创作平台。从创意输入到完整小说，覆盖大纲规划、角色设计、章节生成、一致性校验、质量评估的全流程闭环。

---

## 视觉预览

平台采用 Glassmorphism 渐变毛玻璃设计系统：

| 小说全景创作看板 | 异步任务监控 |
|---|---|
| ![创作看板](docs/images/media1.png) | ![任务监控](docs/images/media2.png) |

---

## 核心特性

1. **多智能体图流编排** — 基于 LangGraph StateGraph 实现非线性流程控制，支持任意步骤人工介入（Human-in-the-Loop），含 HITL 中断/恢复 + 持久化 checkpointer
2. **分级漏斗式质量门禁** — 规则做闸门、LLM 做裁判、成本由风险决定（详见下方「质量门禁架构」）：
   - **L0 零 Token 规则门禁**（每章）：字数 / 段落重复 / 句式复用 / 大纲覆盖率
   - **L1 风险分级**：基于 L0 + 结构化状态增量 + 章节类型决定是否调 LLM
   - **L2 LLM 全文评审**（仅高风险章）：8 维打分 + 人物/世界观一致性硬门禁
   - **L3 候选改写择优**（仅不达标章）：基线 vs 候选，改善且保护维度不下降才激活
   - 失败一律标记 `unverified`，绝不伪造合格分；支持 `QUALITY_MODE`（均衡 / 成本优先 / 质量优先）
3. **活态知识图谱** — 每章生成前自动抽取实体三元组，防范"吃设定"、"死人复活"、"战力崩溃"等常见顽疾
4. **故事圣经约束** — 精准注入本章相关人物/伏笔/时间线，生成后 LLM 反向更新圣经并检测性格漂移与设定矛盾
5. **结构化长期记忆** — 每章抽取 `state_delta`（关键事件 / 人物状态变化 / 伏笔 / 时间线 / 未解决冲突），替代正文截取作为衔接上下文，改善长篇连贯性
6. **章节版本管理** — 每次生成/重写自动创建快照，支持版本对比、激活、回滚；候选择优先存不激活、确认改善才激活
7. **实时 Web 前端** — Vue 3 + WebSocket 进度推送 + 三层图谱可视化 + 流式打字效果；质量面板诚实展示未评估章节

---

## LangGraph 执行流程

```mermaid
graph TD
    Start([开始创作]) --> Init[1. 初始化状态]
    Init --> Outline[2. 大纲与卷规划]
    Outline --> CheckGate{人机交互 / 自动}
    CheckGate -- 交互干预 --> Interactive[3. 人机共创]
    CheckGate -- 自动继续 --> ChapterGen[4. 章节精细生成]
    Interactive --> ChapterGen

    ChapterGen --> Gate[5. 质量门禁漏斗]
    Gate --> L0[L0 规则门禁 + 抽取 state_delta]
    L0 --> L1{L1 风险分级}
    L1 -- 高风险 --> L2[6. L2 LLM 全文评审]
    L1 -- 低风险 --> Output
    L2 --> Routing{达标 & 一致性通过?}
    Routing -- 不达标 --> Revision[7. L3 候选改写择优]
    Revision --> Output
    Routing -- 合格 --> Output[8. 落库 & 更新知识图谱]

    Output --> CheckMore{还有下一章?}
    CheckMore -- 有 --> ChapterGen
    CheckMore -- 无 --> Complete([生成完成])
```

---

## 快速启动

### 环境依赖

- Python `3.11+`
- Node.js `20+`
- PostgreSQL `15+`

### 方案 A：Docker Compose（推荐）

```bash
cp .env.example .env          # 填入 DEEPSEEK_API_KEY
docker-compose up -d --build
```

访问 [http://localhost:8080](http://localhost:8080)

### 方案 B：本地开发

**后端**

```bash
poetry install
cp .env.example .env          # 配置环境变量（见下方说明）
poetry run alembic upgrade head
poetry run uvicorn run_api:app --host 127.0.0.1 --port 8000 --reload
```

**前端**

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

**最小 `.env` 配置**

```env
DEEPSEEK_API_KEY=sk-your-key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/xiaoshuo
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro
```

数据库详细配置见 [DATABASE_SETUP.md](DATABASE_SETUP.md)。

---

## API 路由一览

| 模块 | 端点前缀 | 说明 |
|------|----------|------|
| 项目管理 | `POST/GET /api/v1/projects` | 创建、列表、详情、更新、删除 |
| 全流程生成 | `POST /api/v1/projects/{id}/generate-full` | 触发 LangGraph 完整流水线 |
| 卷管理 | `/api/v1/projects/{id}/volumes` | 卷结构与卷级生成 |
| 章节管理 | `/api/v1/projects/{id}/chapters` | CRUD、批量生成、AI 片段重写 |
| 章节版本 | `/api/v1/projects/{id}/chapters/{n}/versions` | 历史、对比、回滚、激活 |
| 大纲管理 | `/api/v1/projects/{id}/outlines` | 总纲 / 卷纲 / 章纲树 |
| 故事线 | `/api/v1/projects/{id}/storylines` | 主线 / 支线 / 人物弧光 / 场景 |
| 世界设定 | `/api/v1/projects/{id}/world` | 世界观、力量体系、人物库 |
| 知识图谱 | `/api/v1/projects/{id}/knowledge-graph` | 实体、三元组、一致性校验 |
| 故事圣经 | `/api/v1/projects/{id}/story-bible` | 约束管理（时间线 / 悬念 / 目标） |
| 对话协作 | `/api/v1/projects/{id}/conversations` | 人机对话共创 |
| 任务管理 | `/api/v1/novels` | 异步任务状态、取消、清理 |
| WebSocket | `/api/v1/ws` | 实时进度事件推送 |
| 健康检查 | `GET /api/v1/health` | 服务状态与 API Key 校验 |

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看完整交互式文档。

**快速示例**

```bash
# 创建项目
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"title":"大荒武神","novel_type":"玄幻修真","idea":"天生石脉的凡人少年逆天改命","target_words":500000}'

# 启动全流程生成
curl -X POST http://localhost:8000/api/v1/projects/{id}/generate-full
```

---

## 质量评估维度

| 维度 | 说明 |
|------|------|
| `advancement` 主线推进度 | 严防注水，判定本章是否切实推进大纲锁定的剧情 |
| `conflict` 冲突与悬念 | 爽点、危机、打脸、章末悬念钩子 |
| `character_consistency` 角色一致性 | 比对图谱中登记的性格、语调与身份 |
| `world_consistency` 世界观一致性 | 对照力量体系上限与规则设定 |
| `foreshadowing` 伏笔与回收 | 识别暗线埋设与旧引线回收 |
| `pacing` 叙事节奏 | 排查拖沓、废话、强行水字数 |
| `readability` 语言精炼度 | 通顺程度，排查错别字与车轱辘话 |
| `trope_alignment` 题材契合度 | 匹配玄幻 / 都市 / 仙侠等题材套路表现力 |

> 评估失败（网络抖动 / JSON 解析失败）时标记为 `unverified`，绝不伪造合格分——下游质量面板与卷级报告会诚实展示「未评估」状态。

---

## 质量门禁架构

分级漏斗在长篇逐章生成循环中运行（`src/core/quality/gate.py` 编排），核心是**用规则承担 90% 的检查量，LLM 只在它真正擅长的地方出手**：

| 层级 | 触发条件 | 检查方式 | Token |
|------|----------|----------|-------|
| L0 规则门禁 | 每章必跑 | 字数 / 段落重复 / 句式复用 / 大纲覆盖率 / 失败标记 | 零 |
| L1 风险分级 | 每章 | 基于 L0 + state_delta + 章节类型 | 零~极低 |
| L2 LLM 评审 | 仅高风险章 | 8 维评分 + 人物/世界观一致性硬门禁 | 中 |
| L3 候选改写 | 仅 L2 不达标 | 基线 vs 候选，改善且保护维度不下降才激活 | 高 |

**成本控制**：低风险章零 LLM 评审（仅 1 次 flash 抽取 state_delta），仅高风险章（失败 / 关键章 / 严重告警）触发 L2/L3。`QUALITY_MODE` 切换 economy / balanced / high 三档。

**健壮性**：漏斗任何环节失败都不阻塞章节落库和下一章生成——最坏 `quality_status=unverified`，章节内容仍是可用基线。单章 Token 预算耗尽转人工。

**一致性硬门禁**：人物一致性 / 世界观一致性出现严重冲突（评分 < 0.4）时，无论综合分多少都不通过，三条一致性检查路径（KG subagent / 非 subagent / StoryBible）全覆盖。

---

## 项目结构

```
xIaoShuo/
├── src/
│   ├── api/
│   │   ├── routes/               # API 路由层（25 个路由模块）
│   │   ├── services/             # API 业务服务层
│   │   │   ├── generation/       # 小说/章节生成编排与进度
│   │   │   ├── content/          # 小说内容域管理
│   │   │   ├── quality/          # 质量检测、报告与改写
│   │   │   ├── knowledge/        # 知识图谱服务
│   │   │   └── tasks/            # 持久化任务队列
│   │   └── models/db_models.py   # SQLAlchemy ORM
│   └── core/
│       ├── langgraph/
│       │   ├── graph.py          # LangGraph 流程图（含质量循环路由）
│       │   ├── state.py          # 状态定义
│       │   ├── checkpointer.py   # HITL 中断/恢复持久化
│       │   └── nodes/            # 各阶段节点实现
│       ├── llm/
│       │   ├── client.py         # DeepSeek API 客户端（flash/pro 双档）
│       │   └── chapter_generator.py  # 章节流式生成 + pause_checker
│       ├── quality/
│       │   ├── gate.py           # 质量门禁编排器（L0/L1/L2/L3 漏斗）
│       │   ├── rules.py          # L0 零 Token 规则门禁
│       │   ├── risk.py           # L1 风险分级 + should_invoke_l2
│       │   ├── state_delta.py     # 结构化状态增量抽取
│       │   └── evaluator.py      # L2 八维质量评估
│       ├── agents/               # 连续性编辑/图谱协调/记忆策展等子智能体
│       ├── security/             # 认证 / owner 校验 / 加密
│       ├── config.py             # 含 QUALITY_MODE 等质量配置
│       └── database.py
├── frontend/                     # Vue 3 + Vite 前端
├── alembic/                      # 数据库迁移
├── tests/                        # pytest 测试套件（changeNNN_ 前缀）
├── docs/images/                  # 截图资源
├── docker-compose.yml
├── Dockerfile
├── run_api.py
└── pyproject.toml
```

---

## 开发

```bash
# 一键跑全部门禁（后端测试 + 前端测试 + ruff + 结构/残留检查 + 前端构建）
make verify

# 单项
make test-backend        # 后端全部测试（排除真 LLM 的 test_langgraph）
make test-unit           # 后端单元测试
make test-api            # 后端 API 测试（需可达 PostgreSQL 测试库）
make test-integration    # 后端集成测试（排除真 LLM）
make test-frontend       # 前端 Vitest
make ruff                # 静态检查
make build-frontend      # 前端生产构建
make check-structure      # 目录结构约束
make check-legacy-paths  # 旧路径残留检查
```

### 准备测试数据库

集成/API 测试需可达的 PostgreSQL 测试库。本机已存在时 conftest 会自动探测；也可显式指定：

```bash
export TEST_DATABASE_URL='postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test'
```

若无库，先建：

```bash
createdb xiaoshuo_test
```

> 注：`tests/integration/test_langgraph/test_graph.py` 真打 DeepSeek API（慢、依赖外网），默认不进门禁，需手动验证时单独跑 `poetry run pytest tests/integration/test_langgraph`。

变更历史见 [CHANGELOG.md](CHANGELOG.md)。

---

## License

[MIT](LICENSE)

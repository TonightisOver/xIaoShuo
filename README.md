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

1. **多智能体图流编排** — 基于 LangGraph StateGraph 实现非线性流程控制，支持任意步骤人工介入（Human-in-the-Loop）
2. **8 维网文质量评估** — DeepSeek 对生成文本进行主线推进、冲突悬念、角色一致性等八个维度打分，低于 0.80 自动触发局部重写
3. **活态知识图谱** — 每章生成前自动抽取实体三元组，防范"吃设定"、"死人复活"、"战力崩溃"等常见顽疾
4. **故事圣经约束** — 精准注入本章相关人物/伏笔/时间线，生成后 LLM 反向更新圣经并检测性格漂移与设定矛盾
5. **章节版本管理** — 每次生成/重写自动创建快照，支持版本对比、激活、回滚
6. **实时 Web 前端** — Vue 3 + WebSocket 进度推送 + 三层图谱可视化 + 流式打字效果

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

    ChapterGen --> KGCheck[5. 知识图谱一致性校验]
    KGCheck --> QualCheck[6. 8 维质量评估]

    QualCheck --> Routing{综合得分 ≥ 0.80?}
    Routing -- 不合格 --> Revision[7. 针对性重写]
    Revision --> ChapterGen
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

> 若大模型网络抖动或 JSON 解析失败，系统执行安全降级，赋予综合分 `0.82` 避免死循环。

---

## 项目结构

```
xiaoshuo_review/
├── src/
│   ├── api/
│   │   ├── routes/               # API 路由层
│   │   ├── services/             # 业务逻辑层
│   │   └── models/db_models.py   # SQLAlchemy ORM
│   └── core/
│       ├── langgraph/
│       │   ├── graph.py          # LangGraph 流程图
│       │   ├── state.py          # 状态定义
│       │   └── nodes/            # 各阶段节点实现
│       ├── llm/
│       │   ├── client.py         # DeepSeek API 客户端
│       │   └── chapter_generator.py
│       ├── config.py
│       └── database.py
├── frontend/                     # Vue 3 + Vite 前端
├── alembic/                      # 数据库迁移
├── tests/                        # pytest 测试套件
├── docs/images/                  # 截图资源
├── docker-compose.yml
├── Dockerfile
├── run_api.py
└── pyproject.toml
```

---

## 开发

```bash
# 测试
poetry run pytest tests/ -v

# 代码检查
poetry run ruff check src/ tests/
poetry run mypy src/
```

变更历史见 [CHANGELOG.md](CHANGELOG.md)。

---

## License

[MIT](LICENSE)

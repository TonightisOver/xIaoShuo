# TonightisOver/xIaoShuo (AI小说多智能体协同共创平台)

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue.js-3.4+-4fc08d.svg)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

`xIaoShuo` 是一款基于 **LangGraph 多智能体协同流** 与 **活态时空知识图谱** 深度融合的高硬度 AI 网络小说创作与人机共创平台。通过先进的多 Agent 编排技术，平台实现了从“小说创意 -> 精细化大纲 -> 卷/章级别自动规划 -> 角色/世界观一致性动态检查 -> 多维网文总编辑部级质量硬性评估 -> 交互式反馈修改”的完整小说全功能生成闭环。

项目界面基于现代极简的 **Glassmorphism（渐变毛玻璃感）** 设计系统构建，带来极致的沉浸式创作与监控体验。

---

## 🎨 视觉预览与前端布局

平台采用了极其精美的高清透明卡片、磨砂玻璃背景与动态霓虹流光动效：

### 1. 小说全景创作看板
展示项目概览、世界观设定、核心角色以及章节生成进度。
![小说全景创作看板](docs/images/media1.png)

### 2. 高水准异步任务监控
实时跟踪多 Agent 流中每一个节点的执行状态、消耗时长，并提供日志透显。
![异步任务监控](docs/images/media2.png)

---

## 🏗️ 核心架构与多 Agent 执行流

平台后端采用了 FastAPI 微服务，前端采用 Vue 3 + Vite，核心工作流基于 Python `LangGraph` 编排。

### LangGraph 核心执行流程图

```mermaid
graph TD
    Start([开始创作]) --> Init[1. 初始化状态 Init Node]
    Init --> Outline[2. 大纲与卷规划 Outline Node]
    Outline --> CheckGate{人机交互/自动}
    CheckGate -- 交互干预 --> Interactive[3. 人机共创交互 Node]
    CheckGate -- 自动继续 --> ChapterGen[4. 章节精细生成 Chapter Gen Node]
    Interactive --> ChapterGen
    
    ChapterGen --> KGCheck[5. 知识图谱一致性检查 KG Service]
    KGCheck --> QualCheck[6. 多维网文编辑评估 Quality Check Node]
    
    QualCheck --> Routing{综合得分 >= 0.80 ?}
    Routing -- 不合格 Refuse --> Revision[7. 针对性重写指导 Revision Node]
    Revision --> ChapterGen
    Routing -- 合格 Approve --> Output[8. 章节落库与KG更新 Output Node]
    
    Output --> CheckMore{还有下一章吗?}
    CheckMore -- 有 --> ChapterGen
    CheckMore -- 无 --> Complete([小说生成圆满完成])
```

---

## 核心特性与技术亮点

1. **多智能体（Multi-Agent）图流编排**：基于 `LangGraph` 状态图实现长文本生成的非线性流程控制，支持在任意步骤引入人工介入（Human-in-the-loop）修改。
2. **多维网文总编辑部级质量评估**：集成 DeepSeek API 对生成文本进行八个极其严苛的网文黄金维度自适应硬度打分（主线推进、悬念冲突、角色一致性、世界观一致性、伏笔回收、节奏掌控、表达精炼度、网文爽点契合度），低于 0.80 分自动进入局部重写并加入修改意见。
3. **活态时空知识图谱（Living Knowledge Graph）**：在生成每章前自动抽取并同步实体（角色、地点、势力、秘宝）三元组，提供一致性校验，防范”吃设定”、”死人复活”、”战斗力崩溃”等网文常见顽疾。支持频次筛选，区分主要/次要实体。
4. **故事圣经约束系统（Story Bible）**：精准约束注入（只注入本章出场人物/相关伏笔/近期时间线），生成后 LLM 自动反向更新圣经，质量评估阶段检测人物性格漂移、时间线冲突、设定矛盾、伏笔遗忘。
5. **章节版本管理与回滚**：每次生成/重写自动创建版本快照，支持版本对比、激活、回滚，质量评分持久化到版本记录。
6. **高感知 Web 前端**：基于 Vue 3 + Vue Router 打造，具备流式打字效果、WebSocket 进度事件推送、三层图谱可视化以及酷炫的任务监控看板。

---

## 🚀 五分钟极速启动指南

### 环境依赖
- **Python**: `3.13+`
- **Node.js**: `20+`
- **PostgreSQL**: `15+` (若使用本地数据库)

### 方案 A：一键 Docker Compose 容器化部署（最快）

1. 复制 `.env.example` 并重命名为 `.env`，配置您的 OpenAI/DeepSeek API Key：
   ```bash
   cp .env.example .env
   ```
2. 使用 Docker Compose 一键启动所有服务（PostgreSQL + 后端 API + Nginx + 前端 UI）：
   ```bash
   docker-compose up -d --build
   ```
3. 访问浏览器：[http://localhost:8080](http://localhost:8080) 即可开始创作。

---

### 方案 B：本地开发环境启动

#### 1. 后端 (Poetry) 启动
1. 安装 Python 依赖：
   ```bash
   poetry install
   ```
2. 配置环境变量（在项目根目录新建 `.env`）：
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/xiaoshuo
   DEEPSEEK_API_KEY=sk-your-api-key
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   DEEPSEEK_MODEL=deepseek-v4-pro
   KNOWLEDGE_GRAPH_ENABLED=true
   ```
3. 执行数据库迁移（若未初始化）：
   ```bash
   poetry run alembic upgrade head
   ```
4. 运行 FastAPI 后端服务：
   ```bash
   poetry run uvicorn run_api:app --host 127.0.0.1 --port 8000 --reload
   ```

#### 2. 前端 (Vite) 启动
1. 进入前端目录：
   ```bash
   cd frontend
   ```
2. 安装依赖：
   ```bash
   npm install
   ```
3. 运行前端开发服务器：
   ```bash
   npm run dev
   ```
4. 访问开发页面：[http://localhost:5173](http://localhost:5173)

---

## API 核心路由一览

| 模块 | 端点前缀 | 功能 |
|------|----------|------|
| 项目管理 | `POST/GET /api/v1/projects` | 创建、列表、详情、更新、删除 |
| 全流程生成 | `POST /api/v1/projects/{id}/generate-full` | 13 阶段 LangGraph 流水线 |
| 卷管理 | `GET/PUT /api/v1/projects/{id}/volumes` | 卷结构、卷生成 |
| 章节管理 | `/api/v1/projects/{id}/chapters` | CRUD、批量生成、AI 片段重写 |
| 章节版本 | `/api/v1/projects/{id}/chapters/{n}/versions` | 版本历史、对比、回滚、激活 |
| 大纲管理 | `/api/v1/projects/{id}/outlines` | 总纲/卷纲/章纲树 |
| 故事线 | `/api/v1/projects/{id}/storylines` | 主线/支线/人物弧光/场景 |
| 世界设定 | `/api/v1/projects/{id}/world` | 世界观、力量体系、人物库 |
| 知识图谱 | `/api/v1/projects/{id}/knowledge-graph` | 实体、三元组、状态、一致性 |
| 故事圣经 | `/api/v1/projects/{id}/story-bible` | 约束管理（含时间线/悬念/目标） |
| 对话协作 | `/api/v1/projects/{id}/conversations` | 人机对话共创 |
| 任务管理 | `/api/v1/novels` | 异步任务状态、取消、清理 |
| WebSocket | `/api/v1/ws` | 实时进度事件推送 |
| 健康检查 | `GET /api/v1/health` | 服务状态与 API Key 校验 |

### 快速示例：创建项目并生成

```bash
# 创建项目
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "title": "大荒武神",
    "novel_type": "玄幻修真",
    "idea": "天生石脉的凡人少年逆天改命的故事",
    "target_words": 500000,
    "writing_style": "热血、快节奏、升级流"
  }'

# 启动全流程生成
curl -X POST http://localhost:8000/api/v1/projects/{novel_id}/generate-full
```

---

## 📊 高硬度质量评估维度详解

| 维度 ID | 维度名称 | 评估侧重点与硬性标准 |
| :--- | :--- | :--- |
| **advancement** | 主线推进度 | 严防注水。判定本章是否切实前推了大纲锁定的剧情进度。 |
| **conflict** | 冲突与悬念 | 是否具备爽点、危机、打脸、期待感或章末用于勾引读者的“悬念钩子”。 |
| **character_consistency**| 角色一致性 | 强行比对已在图谱中登记的性格、语调与身份，防止角色智商下线。 |
| **world_consistency** | 世界观一致性| 对照力量体系上限、规则设定，防止无端创造冲突逻辑的伪概念。 |
| **foreshadowing** | 伏笔与回收 | 自动识别是否有为后续埋下的暗线，或精彩回收之前的旧引线。 |
| **pacing** | 叙事节奏控制 | 排查文字拖沓、大段无意义废话、或强行水字数行为。 |
| **readability** | 语言精炼度 | 文笔的通顺程度，排查低级错别字、大段车轱辘话和排版硬伤。 |
| **trope_alignment** | 网文题材契合度| 深度匹配玄幻/都市/仙侠等题材的特有套路表现力，提高阅读爽感。 |
| **consistency** | 图谱一致性检查| 结合 PostgreSQL 抽取冲突条数，给出高精度的图谱核查分数。 |

> [!TIP]
> **优雅降级防御死锁**：若大模型网络抖动或 JSON 解析发生格式故障，系统将记录日志并执行**安全降级策略**，赋予综合分数 `0.82` 以确保主生成流能够安全进入下一步，避免 AI 陷入反复死循环修改。

---

## 项目文件结构

```
xiaoshuo_review/
├── src/                          # 后端核心源码
│   ├── api/
│   │   ├── routes/               # API 路由
│   │   │   ├── projects.py       # 项目 CRUD & 生成
│   │   │   ├── novels.py         # 任务管理
│   │   │   ├── outlines.py       # 大纲管理
│   │   │   ├── storylines.py     # 故事线 & 人物弧光
│   │   │   ├── knowledge_graph.py# 知识图谱
│   │   │   ├── story_bible.py    # 故事圣经
│   │   │   ├── conversations.py  # 对话协作
│   │   │   └── ws.py             # WebSocket
│   │   ├── services/             # 业务逻辑
│   │   │   ├── novel_generator.py# 生成流水线
│   │   │   ├── novel_manager.py  # 小说 CRUD
│   │   │   ├── story_bible_service.py # 约束抽取/反向更新/冲突检测
│   │   │   ├── knowledge_graph_service.py
│   │   │   └── task_manager.py   # 异步任务
│   │   └── models/
│   │       └── db_models.py      # SQLAlchemy ORM 模型
│   └── core/
│       ├── langgraph/
│       │   ├── graph.py          # LangGraph 流程图
│       │   ├── state.py          # 状态定义
│       │   └── nodes/            # 各阶段节点
│       │       ├── chapter_generation.py
│       │       ├── quality_check.py  # 8维评分 + 冲突检测
│       │       └── ...
│       ├── llm/
│       │   ├── client.py         # DeepSeek API 客户端
│       │   └── chapter_generator.py # 章节生成（含约束注入）
│       ├── config.py             # 配置管理
│       └── database.py           # 数据库连接
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── views/                # 页面组件
│   │   ├── components/           # 可复用组件
│   │   └── router/               # 路由配置
│   └── package.json
├── alembic/                      # 数据库迁移
├── tests/                        # 测试套件
│   └── unit/                     # 单元测试
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml                # Poetry 依赖
```

---

## 未来演进规划

- [ ] **多 LLM 交叉盲审**：支持配置多个大模型（如 DeepSeek-R1 + Claude）进行跨模型一致性质量盲审
- [ ] **交互式时空沙盘**：前端通过 3D 拓扑网络，实时查看随着章节推进知识图谱节点的动态变化
- [ ] **角色克隆共创**：允许用户扮演特定角色，直接与 AI 进行沉浸式对话式共创
- [ ] **多语言输出**：支持中英日韩多语言小说生成
- [ ] **读者反馈闭环**：集成读者评论分析，自动调整后续章节风格

---

## 开源协议

本项目基于 [MIT License](LICENSE) 协议开源。欢迎 Star 与贡献 PR！

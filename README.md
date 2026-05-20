# 🌟 TonightisOver/xIaoShuo (AI小说多智能体协同共创平台)

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue.js-3.4+-4fc08d.svg)](https://vuejs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-orange.svg)](https://github.com/langchain-ai/langgraph)
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

## 🌟 核心特性与技术亮点

1. **多智能体（Multi-Agent）图流编排**：基于 `LangGraph` 状态图实现长文本生成的非线性流程控制，支持在任意步骤引入人工介入（Human-in-the-loop）修改。
2. **多维网文总编辑部级质量评估（Problem 2 解决）**：集成 DeepSeek API 对生成文本进行八个极其严苛的网文黄金维度自适应硬度打分（主线推进、悬念冲突、角色一致性、世界观一致性、伏笔回收、节奏掌控、表达精炼度、网文爽点契合度），低于 0.80 分自动进入局部重写并加入修改意见。
3. **活态时空知识图谱（Living Knowledge Graph）**：在生成每章前自动抽取并同步实体（角色、地点、势力、秘宝）三元组，提供一致性校验，防范“吃设定”、“死人复活”、“战斗力崩溃”等网文常见顽疾。
4. **高感知 Web 前端**：基于 Vue 3 + Pinia + Vue Router 打造，具备流式打字效果、WebSocket 进度事件推送、三元图谱树形可视化以及酷炫的任务监控看板。

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
   OPENAI_API_KEY=your-deepseek-or-openai-api-key
   OPENAI_API_BASE=https://api.deepseek.com/v1
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

## 📦 API 调用指引与核心路由

后端服务提供全功能的 RESTful API 与实时交互 WebSocket，核心接口如下：

### 1. 创建小说创作项目
- **请求方法**：`POST`
- **路径**：`/api/novels/`
- **Payload 示例**：
  ```json
  {
    "title": "大荒武神",
    "novel_type": "玄幻修真",
    "idea": "一个天生石脉的凡人少年通过活态知识图谱获得逆天改命传承的故事。",
    "target_words": 500000,
    "writing_style": "热血、快节奏、升级流"
  }
  ```
- **响应**：返回项目 `project_id`、初始元信息及知识图谱状态。

### 2. 生成/编辑大纲与卷规划
- **请求方法**：`POST`
- **路径**：`/api/novels/{project_id}/outline`
- **响应**：自动规划整本书的卷（Volumes）结构与细化的大纲。

### 3. 一键启动小说章节生成
- **请求方法**：`POST`
- **路径**：`/api/novels/{project_id}/chapters/generate`
- **Payload 示例**：
  ```json
  {
    "volume_index": 0,
    "chapter_index": 0,
    "interactive_prompt": "让第一章主角在测试石碑前爆发出前所未有的金色命格！"
  }
  ```
- **响应**：触发 LangGraph 后台异步任务，前端可以通过 WebSocket 监听 `/api/ws/progress` 管道。

### 4. 获取项目任务监控列表
- **请求方法**：`GET`
- **路径**：`/api/novels/{project_id}/tasks`
- **响应**：提供该项目下所有已执行、执行中和排队中的多 Agent 任务清单，配合 Vue Glassmorphic 任务监控面板刷新渲染。

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

## 🛠️ 项目文件分布说明

项目采用了清晰且规范的前后端分离式布局，绝无代码混杂：

```
xiaoshuo_review/
├── src/                      # ======= 后端核心源码 =======
│   ├── api/                  # FastAPI 路由、请求/响应 Pydantic 模型
│   │   ├── routes/           # novels.py, task.py 等业务路由
│   │   └── models/           # 响应体结构
│   ├── core/                 # 多智能体核心
│   │   ├── langgraph/        # LangGraph 图定义、状态定义、以及各个 Node
│   │   │   └── nodes/        # quality_check.py (多维评分) 等节点
│   │   ├── llm/              # 大模型客户端集成
│   │   └── json_utils.py     # 稳健的 JSON 解析提取工具
│   └── database/             # 数据库模型、Session 编排与 Alembic 迁移
│
├── frontend/                 # ======= 前端 Vue 3 源码 =======
│   ├── src/
│   │   ├── components/       # 可复用 Glassmorphism 卡片、状态标签
│   │   ├── views/            # TaskList.vue (任务面板), App.vue 等主页面
│   │   └── router/           # 前端路由控制
│   ├── index.html            # 单页面入口
│   └── package.json          # 前端依赖配置
│
├── docs/                     # ======= 项目展示与文档 =======
│   └── images/               # media1.png, media2.png 界面演示截图
└── pyproject.toml            # Poetry 后端配置及依赖锁定
```

---

## 🔮 未来演进规划与路线图

- [ ] **多 LLM 交叉盲审**：支持配置多个大模型（如 DeepSeek-R1 + Claude 3.5 Sonnet）进行跨模型一致性质量盲审。
- [ ] **交互式时空沙盘**：前端通过 3D 拓扑网络，实时查看随着小说章节推进，知识图谱节点的生死、黑化、结盟与升降动态。
- [ ] **角色克隆共创**：允许用户扮演特定角色，直接与 AI 进行沉浸式对话式共创，对话历史自动转写为网文段落。

---

## ⚖️ 开源协议

本项目基于 [MIT License](LICENSE) 协议开源。欢迎 Star 与贡献 PR！

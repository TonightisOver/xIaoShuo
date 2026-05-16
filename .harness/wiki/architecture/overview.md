# 系统架构总览

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Vite + Tailwind CSS | SPA，嵌入 FastAPI 静态服务 |
| API | FastAPI | 异步 RESTful + WebSocket |
| 工作流 | LangGraph | 7 阶段小说生成流程 |
| LLM | DeepSeek (deepseek-v4-pro) | 大模型 API |
| 数据库 | PostgreSQL 17 | SQLAlchemy 2.0 async ORM |
| 迁移 | Alembic | 数据库版本管理 |
| 部署 | Docker Compose | API + DB + Nginx |

## 系统架构图

```
┌─────────────────────────────────────────────────┐
│                   Nginx (:80)                    │
│              反向代理 + WebSocket                 │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              FastAPI (:8000)                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 前端静态  │  │ REST API │  │  WebSocket   │  │
│  │ (Vue 3)  │  │ /api/v1/ │  │ /ws/tasks/   │  │
│  └──────────┘  └────┬─────┘  └──────┬───────┘  │
│                      │               │           │
│  ┌───────────────────▼───────────────▼────────┐ │
│  │            Services Layer                   │ │
│  │  NovelManager / TaskManager / EventBus     │ │
│  └───────────────────┬────────────────────────┘ │
│                      │                           │
│  ┌───────────────────▼────────────────────────┐ │
│  │         LangGraph Workflow                  │ │
│  │  idea → world → chars → outline → chapters │ │
│  └───────────────────┬────────────────────────┘ │
│                      │                           │
└──────────────────────┼───────────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │    PostgreSQL (:5432)      │
         │  novels / world_settings  │
         │  characters / chapters    │
         │  power_systems / tasks    │
         └───────────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │    DeepSeek API           │
         │  (deepseek-v4-pro)        │
         └───────────────────────────┘
```

## 模块划分

```
src/
├── api/                    # Web 层
│   ├── main.py            # 应用入口
│   ├── routes/            # 路由（health/novels/projects/ws）
│   ├── models/            # Pydantic + SQLAlchemy 模型
│   └── services/          # 业务服务
└── core/                   # 核心层
    ├── config.py          # 配置管理
    ├── database.py        # 数据库连接
    ├── langgraph/         # 工作流引擎
    │   ├── graph.py       # 图定义
    │   ├── state.py       # 状态定义
    │   └── nodes/         # 7 个节点
    └── llm/               # LLM 客户端
```

## 数据流

1. 用户创建小说项目 → `POST /api/v1/projects`
2. 触发生成 → `POST /api/v1/projects/{id}/generate`
3. 后台执行 LangGraph 工作流（astream 逐节点）
4. 每个节点完成 → 更新 DB 进度 + 发布 WebSocket 事件
5. 全部完成 → 结果拆分存入子表（world_settings/characters/chapters）
6. 用户查看/编辑设定和章节

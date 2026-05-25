# 压力测试 (Load Testing)

基于 Locust 的 API 压力测试套件，覆盖项目全部核心接口。

## 快速开始

### 1. 安装依赖

```bash
pip install locust requests
```

### 2. 生成 Seed 数据

从目标服务器拉取小说/章节/任务 ID 作为压测参数：

```bash
python loadtest/generate_seed.py --host http://115.190.142.169:8000
```

生成的数据保存在 `loadtest/data/seed.json`。

### 3. 运行压测

**Web UI 模式（推荐）：**

```bash
locust -f loadtest/locustfile.py
```

打开 http://localhost:8089，设置并发用户数和增长速率，点击 Start。

**无头模式：**

```bash
# 50 并发用户，每秒增加 10 个，运行 5 分钟
locust -f loadtest/locustfile.py --headless -u 50 -r 10 --run-time 5m

# 100 并发 + HTML 报告
locust -f loadtest/locustfile.py --headless -u 100 -r 20 --run-time 10m --html loadtest/report.html
```

## 用户画像

| 角色 | 权重 | 行为 |
|------|------|------|
| ReaderUser | 60% | 高频读取章节、浏览列表、查看版本 |
| WriterUser | 25% | 编辑保存、触发生成、查看任务进度 |
| AdminUser | 15% | 浏览大纲、世界观、知识图谱 |

## 覆盖接口

| 模块 | 接口数 | 说明 |
|------|--------|------|
| chapter_read | 2 | 章节内容 + 版本历史 |
| chapter_list | 4 | 章节列表 + 小说详情 + 卷列表 + 小说列表 |
| chapter_edit | 1 | 章节内容保存 |
| chapter_generate | 1 | 触发章节生成 |
| ai_rewrite | 1 | AI 改写 |
| task_management | 3 | 任务列表 + 任务详情 + 健康检查 |
| outline_world | 5 | 大纲 + 世界观 + 角色 + 故事圣经 + 故事线 |
| knowledge_graph | 4 | 实体 + 三层图谱 + 可视化 + 三元组 |

共 **21 个** 压测场景。

## 配置

环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| LOADTEST_HOST | http://115.190.142.169:8000 | 目标服务器地址 |

## 压测建议

| 阶段 | 并发 | 时长 | 目的 |
|------|------|------|------|
| 冒烟测试 | 5 | 1min | 验证脚本正确性 |
| 负载测试 | 50 | 5min | 正常负载下的性能基线 |
| 压力测试 | 100-200 | 10min | 找到性能瓶颈 |
| 峰值测试 | 200+ | 15min | 极端场景下的表现 |

## 目录结构

```
loadtest/
├── locustfile.py          # 入口：用户画像定义
├── config.py              # 配置：HOST + seed 数据加载
├── generate_seed.py       # 工具：从服务器拉取 seed 数据
├── data/
│   └── seed.json          # 压测参数（novel_ids, chapter_numbers 等）
└── tasks/
    ├── __init__.py
    ├── chapter_read.py    # 章节读取 + 版本
    ├── chapter_list.py    # 列表 + 详情
    ├── chapter_edit.py    # 章节编辑保存
    ├── chapter_generate.py # 章节生成
    ├── ai_rewrite.py      # AI 改写
    ├── task_management.py # 任务管理 + 健康检查
    ├── outline_world.py   # 大纲 + 世界观
    └── knowledge_graph.py # 知识图谱
```

# CHANGE-026 归档记录

- 原名称：小说全功能生成
- 状态：completed
- 时间范围：2026-05-18
- 原路径：`.harness/changes/CHANGE-026-小说全功能生成`
- 归档路径：`archive/changes/CHANGE-026-小说全功能生成`
- 关联提交：
  - 03fe5fd 2026-05-18 feat: improve full novel generation and storyline context

## 目标

用户需要一键生成一部完整小说，题材为科幻/奇幻方向，建议采用 **"赛博修仙"（CyberCultivation）** 题材 -- 将传统修仙体系嵌入近未来赛博朋克世界观，科技与灵力并存，具有巨大的发挥空间。生成过程必须使用平台全部功能：LangGraph 小说生成流程、卷管理、章节管理、故事线、对话系统、大纲编辑、世界设定、角色管理、力量体系、文风系统、WebSocket 进度推送。同时需要将 DeepSeek API 配置从 `deepseek-v4-pro` + 旧 key 切换为用户提供的 `deepseek-v4-flash` + 新 key。

## 主要设计决定

**日期**: 2026-05-18
**版本**: v1

## 架构方案

### 整体数据流

```
用户点击"一键全功能生成"
        |
        v
POST /api/v1/projects/full-generate   (新建项目 + 启动全功能生成)
        |
        v
generate_novel_full_background()     (后台任务)
        |
        |-- [复用] LangGraph 7 节点流程 (idea_expansion ... human_review)
        |       |
        |       +-- [复用] _persist_to_novel() (world_setting / characters / volumes / chapters)
        |
        |-- [新增] generate_power_systems_ai()          --> power_systems 表
        |-- [新增] persist_outlines_from_result()       --> outlines 表 (master/volume/chapter)
        |-- [复用] generate_storylines_ai()              --> storylines 表
        |-- [复用] generate_arcs_ai()                    --> character_arcs 表
        |-- [复用] generate_scenes_ai()                  --> scenes_table 表
        |-- [新增] generate_auto_conversation()          --> conversations + messages 表
        |
        v
WebSocket 推送全阶段进度 -> 前端 TaskDetail 实时展示 -> 完成后跳转 NovelDetail 查看成果
```

### 设计原则

1. **复用优先**: 子功能（故事线/弧光/场景）的 LLM 生成方法已存在于 `StorylineService`，直接调用而非重写
2. **wrapper 模式**: 新增 `generate_novel_full_background()` 函数封装完整流程，不修改现有 `generate_novel_background()`
3. **独立容错**: 每个子功能独立 try-catch，一个子功能失败不阻断后续步骤
4. **进度透明**: 每个子功能执行前后通过 WebSocket 推送事件

---

## API 设计

### 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/full-generate` | 创建项目 + 一键全功能生成（推荐入口） |
| POST | `/api/v1/projects/{novel_id}/generate-full` | 对已有项目执行全功能生成 |

### POST `/api/v1/projects/full-generate`

**请求体** (`CreateProjectRequest`, 复用现有模型):

```json
{
    "idea": "2087年，人类发现了第7种基本力——灵子力。程序员林锐发现修仙法诀本质是一种攻击向量，渡劫是DoS攻击，飞升是获得root权限...",
    "novel_type": "科幻",
    "target_words": 100000,
    "title": "灵网入侵",
    "writing_style": "轻松幽默",
    "custom_style_description": null,
    "writing_style_prompt": null

## 涉及模块

- `frontend/src/components/StageIndicator.vue`
- `frontend/src/views/Create.vue`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/TaskDetail.vue`
- `src/api/main.py`
- `src/api/models/responses.py`
- `src/api/routes/`
- `src/api/routes/projects.py`
- `src/api/services/`
- `src/api/services/conversation_service.py`
- `src/api/services/novel_generator.py`
- `src/api/services/outline_service.py`
- `src/api/services/progress_event_bus.py`
- `src/api/services/storyline_service.py`
- `src/core/database.py`
- `src/core/llm/prompts.py`
- `tests/conftest.py`
- `tests/integration/`
- `tests/integration/test_full_generate_api.py`
- `tests/unit/`
- `tests/unit/test_change025_fixes.py`
- `tests/unit/test_change026_full_generate.py`

## 实施结果

**日期**: 2026-05-18
**版本**: v1
用户需要一键生成一部完整小说，题材为科幻/奇幻方向，建议采用 **"赛博修仙"（CyberCultivation）** 题材 -- 将传统修仙体系嵌入近未来赛博朋克世界观，科技与灵力并存，具有巨大的发挥空间。生成过程必须使用平台全部功能：LangGraph 小说生成流程、卷管理、章节管理、故事线、对话系统、大纲编辑、世界设定、角色管理、力量体系、文风系统、WebSocket 进度推送。同时需要将 DeepSeek API 配置从 `deepseek-v4-pro` + 旧 key 切换为用户提供的 `deepseek-v4-flash` + 新 key。
- 将 `.env` 中 `DEEPSEEK_API_KEY` 改为 `[REDACTED_API_KEY]`
- 将 `DEEPSEEK_MODEL` 从 `deepseek-v4-pro` 改为 `deepseek-v4-flash`
- 将 `DEEPSEEK_MAX_TOKENS` 从 `2000` 提升到 `16000`（`deepseek-v4-flash` 支持更长输出，章节生成需要较大 max_tokens）
- 基于现有 LangGraph 流程图（idea_expansion -> world_building -> character_design -> outline_generation -> chapter_generation -> quality_check -> human_review），在其 **完成后** 自动串联执行以下子功能生成：
  - 力量体系（PowerSystem）AI 生成
  - 故事线（Storylines）AI 生成
  - 人物弧光（Character Arcs）AI 生成
  - 场景（Scenes）AI 生成
  - 三级大纲持久化（总纲 + 卷纲 + 章纲 写入 outlines 表）

## 测试与验证

| 指标 | 数值 |
|------|------|
| 通过 | 21 |
| 失败 | 0 |
| 跳过 | 0 |
| 总计 | 21 |

## 遗留事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| `deepseek-v4-flash` token 限制或格式差异 | 章节内容可能被截断或格式变更 | 增加 max_tokens 到 16000；添加响应格式兼容逻辑 |
| 全功能流程过长导致超时 | 10+ 个 LLM 调用可能超过 HTTP/WebSocket 超时 | 每个子功能独立 try-catch，失败不阻断后续；设置合理超时 |
| 多个 LLM 调用串行导致用户体验差 | 用户可能等待超过 5-10 分钟 | WebSocket 实时推送每一步进度；考虑并发调用独立子功能 |
| LLM 返回 JSON 解析失败 | 部分功能（力量体系、场景）无 fallback 值 | 为每个新增生成方法添加 fallback 逻辑 |
| 现有代码改动过多引入 bug | 影响现有功能稳定性 | 新增编排函数而非修改现有函数；全功能流程作为独立入口 |

## 原始文件清单

- `.gate1-approved`
- `.gate2-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `04-编码报告-v2.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`

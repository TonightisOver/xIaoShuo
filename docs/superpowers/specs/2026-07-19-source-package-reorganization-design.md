# 源码服务层分包设计

> 在不改变业务逻辑、公开 API、数据库模型和运行行为的前提下，将
> `src/api/services/` 的扁平模块按职责整理为稳定的子包，并同步更新所有导入路径、
> 测试 patch 路径和包说明。

## 背景

当前 `src/api/services/` 包含 39 个业务模块和 1 个 `__init__.py`。生成、内容管理、
质量治理、知识图谱和持久化任务队列模块混放在同一层，导致目录浏览成本较高，也使新增服务
难以确定归属。

现有 `src/api/routes/` 已按资源拆分，`src/core/` 已按 `agents`、`langgraph`、`llm`、
`quality` 和 `security` 分包。本次只处理结构问题最集中的 `src/api/services/`，避免把一次
目录整理扩大为架构重写。

当前源码、测试和脚本中约有 90 个文件、997 处服务模块路径引用，其中包含大量测试
`patch()` 目标。源码迁移必须覆盖普通导入、延迟导入、字符串 patch 路径和包级再导出。

## 目标

1. 将服务模块按稳定业务职责整理为 `generation`、`content`、`quality`、`knowledge`、
   `tasks` 五个子包。
2. 保留少量跨领域或独立服务在 `services` 根目录，避免人为制造错误归属。
3. 只搬迁完整文件并更新导入路径，不拆函数、不改类名、不改函数签名、不改控制流。
4. 更新源码、测试和脚本中的全部导入及 patch 路径，使新路径成为唯一正式路径。
5. 用包级说明和服务目录文档记录边界，降低后续文件再次无序堆积的概率。
6. 分批迁移和验证，使路径错误能够在最小批次内定位。

## 非目标

- 不修改 API 路由、请求响应模型、数据库表、Alembic 迁移或前端契约。
- 不拆分约 940 行的 `src/api/models/db_models.py`。
- 不进一步拆分任何服务文件的内部函数、类或常量。
- 不重构现有服务依赖关系，不引入依赖注入层、Facade 或仓储抽象。
- 不搬迁 `src/api/routes/`、`src/core/`、`src/api/models/` 或前端源码。
- 不处理认证、密钥、权限或部署安全收口。
- 不保留大量旧模块路径兼容壳；仓库内调用方统一切换到新路径。
- 不执行 Git 暂存、提交、分支或推送。

## 方案比较

### 方案一：维持扁平目录，只补充 README

改动最少，也没有导入路径风险，但不能解决 39 个业务模块同层堆积的问题。后续新增模块仍然
缺少明确落点，不采用。

### 方案二：按五个稳定职责分包（采用）

将生成、内容、质量、知识和任务队列模块分别归档，独立或跨领域模块保留在根目录。它能显著
缩短目录列表，同时不要求改变内部实现或既有依赖方向，符合“只调整目录、导入和包说明”的
边界。

### 方案三：同时重组 routes、models 和 core

目录可以更统一，但会扩大到路由注册、ORM 拆分、跨层依赖和迁移加载等高风险区域，难以证明
业务逻辑完全不变。本阶段不采用。

## 目标结构

```text
src/api/services/
├── README.md
├── __init__.py
├── generation/
├── content/
├── quality/
├── knowledge/
├── tasks/
├── agent_journal_service.py
├── book_import_service.py
├── export_service.py
└── reader_simulation_service.py
```

五个子包分别承担以下职责：

- `generation`：小说、章节和长篇生成编排，以及生成进度、暂停状态和落库辅助。
- `content`：小说实体及其章节、人物、世界观、卷、大纲、故事线等内容域管理。
- `quality`：质量动作、报告、灌水检测、伏笔跟踪、上下文和改写闭环。
- `knowledge`：知识图谱服务、提示词和相似度工具。
- `tasks`：持久化任务队列的状态管理、白名单调度和 worker 生命周期。

根目录保留的四个模块具有跨领域或相对独立的职责：智能体日志、书籍导入、导出和读者模拟。
本阶段不为单文件职责创建额外子包。

## 完整模块映射

### generation

| 旧路径（`src.api.services` 下） | 新路径 |
|---|---|
| `novel_generator` | `generation.novel_generator` |
| `novel_generator_planning` | `generation.novel_generator_planning` |
| `long_form_generation_helpers` | `generation.long_form_generation_helpers` |
| `long_form_progress_service` | `generation.long_form_progress_service` |
| `chapter_generation_utils` | `generation.chapter_generation_utils` |
| `chapter_persistence_service` | `generation.chapter_persistence_service` |
| `ai_generation_service` | `generation.ai_generation_service` |
| `pause_state_store` | `generation.pause_state_store` |
| `progress_event_bus` | `generation.progress_event_bus` |

### content

| 旧路径（`src.api.services` 下） | 新路径 |
|---|---|
| `novel_manager` | `content.novel_manager` |
| `chapter_service` | `content.chapter_service` |
| `character_service` | `content.character_service` |
| `world_service` | `content.world_service` |
| `volume_service` | `content.volume_service` |
| `outline_service` | `content.outline_service` |
| `outline_sync_service` | `content.outline_sync_service` |
| `storyline_service` | `content.storyline_service` |
| `story_bible_service` | `content.story_bible_service` |
| `blueprint_service` | `content.blueprint_service` |
| `conversation_service` | `content.conversation_service` |
| `career_service` | `content.career_service` |
| `inspiration_service` | `content.inspiration_service` |
| `chapter_analysis_service` | `content.chapter_analysis_service` |

`chapter_analysis_service` 读取并分析章节内容，但其核心职责是维护章节分析结果，因此与章节
内容生命周期一起归入 `content`，而不是质量门禁包。

### quality

| 旧路径（`src.api.services` 下） | 新路径 |
|---|---|
| `quality_action_service` | `quality.quality_action_service` |
| `quality_report_service` | `quality.quality_report_service` |
| `filler_detection_service` | `quality.filler_detection_service` |
| `foreshadow_tracker_service` | `quality.foreshadow_tracker_service` |
| `novel_context_service` | `quality.novel_context_service` |
| `rewrite_loop_service` | `quality.rewrite_loop_service` |

### knowledge

| 旧路径（`src.api.services` 下） | 新路径 |
|---|---|
| `knowledge_graph_service` | `knowledge.knowledge_graph_service` |
| `kg_prompts` | `knowledge.kg_prompts` |
| `kg_similarity` | `knowledge.kg_similarity` |

### tasks

| 旧路径（`src.api.services` 下） | 新路径 |
|---|---|
| `task_manager` | `tasks.task_manager` |
| `task_dispatcher` | `tasks.task_dispatcher` |
| `task_worker` | `tasks.task_worker` |

### 保留在根目录

以下模块路径不变：

- `src.api.services.agent_journal_service`
- `src.api.services.book_import_service`
- `src.api.services.export_service`
- `src.api.services.reader_simulation_service`

## 导入与包接口规则

1. 仓库内部统一使用新模块的完整绝对路径，例如
   `src.api.services.tasks.task_manager`。
2. 子包 `__init__.py` 只写简短职责说明，不批量再导出类和函数，避免隐藏真实定义位置和制造
   新的循环导入。
3. 顶层 `src/api/services/__init__.py` 继续提供现有的三个包级符号：
   `TaskManager`、`get_task_manager` 和 `generate_novel_background`，但其内部导入改指向新路径。
   这是现有包接口的延续，不是旧模块路径兼容壳。
4. 源码中的直接导入、函数内延迟导入和测试中的字符串 patch 路径必须同步修改。
5. 本次不强制重画依赖方向。现有跨服务引用只更新路径，不借搬迁机会进行依赖反转或逻辑重写。
6. 旧模块文件搬走后不在原位置创建同名转发文件。若仓库内仍存在旧路径引用，验证必须失败并
   修正调用方。

## 包说明

新增 `src/api/services/README.md`，记录：

- 五个子包的职责和模块归属。
- 哪类新服务应放在哪个子包。
- 根目录只保留跨领域或独立服务的约束。
- “目录迁移不等于业务重构”的维护原则。

每个新子包的 `__init__.py` 增加一行模块文档字符串。根 README 的“项目结构”章节同步展示
新的 services 子目录，但不改其他架构说明。

## 实施批次

按依赖面由小到大执行，每批都完成“建包、整文件搬迁、全仓路径替换、聚焦验证”后再进入
下一批：

1. `knowledge`：3 个模块，先验证工具模块与图谱服务的内部引用。
2. `tasks`：3 个模块，重点覆盖 FastAPI 生命周期、路由和队列测试 patch 路径。
3. `quality`：6 个模块，覆盖质量路由、LangGraph 节点和相关单元测试。
4. `content`：14 个模块，覆盖 API 路由、生成服务和内容管理测试。
5. `generation`：9 个模块，最后迁移引用面最大的生成链路。
6. 更新包说明、顶层包接口和根 README，执行完整验证。

批次顺序只用于降低定位成本，不改变最终依赖关系。文件移动采用机械操作，文件内部除导入语句
外不做格式化或顺手重构，以便审查时识别任何非结构性差异。

## 错误处理与工作区保护

- 每批若出现导入错误、循环导入或测试收集失败，先在当前批次修正路径，不继续扩大迁移范围。
- 若发现真实运行代码依赖旧模块字符串路径，更新该配置或 patch 目标；不使用兼容壳掩盖遗漏。
- 保留用户工作区中已有的归档、队列和其他未提交改动，不覆盖、不回退无关文件。
- 不读取或修改 `.claude/worktrees/*` 内的工作树内容。
- 任何超出“文件位置、导入路径、包说明”的必要改动都停止实施并回到设计确认。

## 验证策略

### 每批验证

- 搜索该批旧模块路径，确认源码、测试和脚本中没有残留。
- 对新子包执行 Python 导入冒烟检查。
- 运行受影响模块的聚焦单元测试。
- 对本批修改文件执行 Ruff 检查。

### 最终验证

- 搜索全部旧服务模块路径，确认没有旧导入和旧 patch 目标。
- 导入 `src.api.main`，验证 FastAPI 应用及服务包可收集。
- 运行完整后端测试基线。
- 运行完整 Ruff 检查。
- 收集并运行环境允许的集成测试；需要 PostgreSQL 而环境不可访问时如实记录为环境未验证，
  不把它表述为通过。
- 运行前端测试和生产构建，确认后端路径整理未影响仓库整体基线。
- 审查最终差异，确认被搬迁模块除导入路径外没有业务逻辑变化。

## 验收标准

1. `src/api/services/` 最终只包含五个职责子包、四个根服务模块、README 和包入口。
2. 35 个目标模块全部位于设计指定的子包中，旧模块文件不存在。
3. 仓库内源码、测试和脚本不再引用旧模块路径。
4. 现有包级公开符号仍可从 `src.api.services` 导入。
5. HTTP 路由、函数签名、类名、数据库模型和业务控制流没有改变。
6. 后端测试、Ruff、FastAPI 导入、前端测试和构建均达到迁移前基线。
7. `src/api/services/README.md`、各子包说明和根 README 与最终目录一致。
8. 不触碰 `.claude/worktrees/*`，不执行任何 Git 写操作。

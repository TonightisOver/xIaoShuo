# 项目历史归档索引

## Harness 变更

| 变更 | 状态 | 摘要 | 提交 |
|---|---|---|---|
| [CHANGE-001-langgraph-基础框架](changes/CHANGE-001-langgraph-基础框架/archive-record.md) | completed | 搭建 LangGraph 基础框架，实现小说创作的核心流程编排，包括状态定义、图定义、7 个核心节点实现、Checkpointer 配置和完整的测试。 | `02fcb98` |
| [CHANGE-002-deepseek-api集成](changes/CHANGE-002-deepseek-api集成/archive-record.md) | completed | 集成 DeepSeek API，替换当前的 mock 数据，实现真实的 AI 小说内容生成。 | `02fcb98` |
| [CHANGE-003-web-api](changes/CHANGE-003-web-api/archive-record.md) | completed | 为 xIaoShuo 平台提供 RESTful Web API，支持通过 HTTP 接口创建小说生成任务、查询任务状态、列出任务列表，并提供 Swagger 交互式文档。 | `37e475f` |
| [CHANGE-004-数据库持久化](changes/CHANGE-004-数据库持久化/archive-record.md) | completed | 将任务存储从 JSON 文件迁移到 PostgreSQL 数据库，支持并发访问、事务、索引查询，使用 SQLAlchemy 2.0 async ORM 和 Alembic 数据库迁移管理。 | `37e475f` |
| [CHANGE-005-websocket实时进度](changes/CHANGE-005-websocket实时进度/archive-record.md) | completed | 实现 WebSocket 实时进度推送，让前端能即时展示小说生成的每个阶段完成状态和逐章进度，替代轮询方式。 | `37e475f` |
| [CHANGE-006-前端界面](changes/CHANGE-006-前端界面/archive-record.md) | completed | 为 xIaoShuo 平台添加 Web 前端界面，参考起点/番茄小说的功能布局但更高级简洁，支持创建任务、查看实时进度、浏览生成结果。 | `37e475f` |
| [CHANGE-007-小说项目管理](changes/CHANGE-007-小说项目管理/archive-record.md) | completed | 将系统从扁平的"任务"模型升级为"小说项目"模型，每本书有独立的世界观、等级体系、人物关系，支持多本书管理和内容编辑。生成完成后自动将结果拆分存入子资源表。 | `37e475f` |
| [CHANGE-008-docker部署](changes/CHANGE-008-docker部署/archive-record.md) | completed | 实现 Docker 容器化部署，支持一键启动完整服务栈（API + PostgreSQL + Nginx），部署到云服务器。 | `37e475f` |
| [CHANGE-009-修复云服务器问题](changes/CHANGE-009-修复云服务器问题/archive-record.md) | completed | 用户在云服务器（115.190.142.169）上创建了小说生成任务，但遇到以下问题： | `a5d2939` |
| [CHANGE-010-画风文风风格选择](changes/CHANGE-010-画风文风风格选择/archive-record.md) | completed | 创建小说时可选择写作风格（8 种预设文风），影响所有 LLM 生成节点的输出风格。 | `31b77ad` |
| [CHANGE-011-按卷生成](changes/CHANGE-011-按卷生成/archive-record.md) | completed | 为小说平台新增按卷生成功能，支持将小说按卷组织并逐卷生成章节内容。 | `5cd389b` |
| [CHANGE-012-按章生成](changes/CHANGE-012-按章生成/archive-record.md) | completed | 新增按章节范围生成功能，允许用户指定 chapter_start 和 chapter_end 精确控制生成范围。 | `290509d` |
| [CHANGE-013-人机交互问答生成](changes/CHANGE-013-人机交互问答生成/archive-record.md) | completed | 为小说创作平台新增"创作对话"功能，允许用户与 AI 进行多轮对话讨论小说设定和情节，对话结束后自动提取结构化建议。 | `ec35bfa` |
| [CHANGE-014-自定义文风LLM生成](changes/CHANGE-014-自定义文风LLM生成/archive-record.md) | completed | 在 CHANGE-010 的 8 种预设文风基础上，添加"自定义"选项。用户输入自然语言描述（如"江南的文风，带一点灰色幽默"），通过 LLM 生成具体的风格指令，注入到生成 prompt 中。 | `cf2feb4` |
| [CHANGE-015-前端UX全面修复](changes/CHANGE-015-前端UX全面修复/archive-record.md) | completed | 后端 API 功能已全部实现，但前端 UI 存在大量未对接或体验不佳的问题。本次全面修复前端与后端的对接，确保所有功能在浏览器中可用。 | `f62f766` |
| [CHANGE-016-大纲体系重构](changes/CHANGE-016-大纲体系重构/archive-record.md) | completed | 将大纲从单层 JSON 重构为三级结构化体系（总纲→卷纲→章纲），支持 LLM 自动生成和手动编辑，支持从人机交互对话中提取总纲。 | `b0771e1` |
| [CHANGE-017-故事线人物弧光场景](changes/CHANGE-017-故事线人物弧光场景/archive-record.md) | completed | 为小说项目添加结构化叙事管理：故事线（主线/副线/暗线）、人物弧光（成长轨迹）、场景管理，以及它们之间的三元关联关系。 | `0aa722d` |
| [CHANGE-018-三元图谱树形可视化](changes/CHANGE-018-三元图谱树形可视化/archive-record.md) | completed | 使用 D3.js 将故事线/人物弧光/场景的三元关系以树形图可视化展示。 | `a1c97a2` |
| [CHANGE-019-功能修复与集成检查](changes/CHANGE-019-功能修复与集成检查/archive-record.md) | completed | 修复用户实际使用中发现的 5 个问题：对话结论不能修改设定、缺少删除功能、故事线无法从对话生成、生成内容与设定不匹配、功能集成检查。 | `a1c97a2` |
| [CHANGE-020-人机交互升级](changes/CHANGE-020-人机交互升级/archive-record.md) | completed | 升级人机交互从"建议模式"到"确定模式"。对话中 AI 回复可直接确认为设定，对话结束后可一键驱动大纲生成流程。 | `7150678` |
| [CHANGE-021-章节管理与UI优化](changes/CHANGE-021-章节管理与UI优化/archive-record.md) | completed | 修复章节大纲分组Bug，新增章节管理操作按钮，新增故事线AI生成功能，优化UI交互动效。 | `5e8121e` |
| [CHANGE-022-Review问题修复](changes/CHANGE-022-Review问题修复/archive-record.md) | completed | 修复 Review 过程中发现的 3 个真实代码问题，确认 4 个 P0 为服务器部署问题（非代码缺陷）。 | `30a12ee` |
| [CHANGE-023-数据隔离与健壮性修复](changes/CHANGE-023-数据隔离与健壮性修复/archive-record.md) | completed | 修复 Codex Review 发现的 P1 数据隔离缺陷和健壮性问题，防止跨小说越权操作和异常状态。 | `f5e8c3e` |
| [CHANGE-024-数据隔离收口与跨小说负例测试](changes/CHANGE-024-数据隔离收口与跨小说负例测试/archive-record.md) | completed | 统一收口对话和故事线模块的 novel_id 隔离逻辑，消除所有跨小说读写漏洞，并补充跨小说负例集成测试。 | `03fe5fd` |
| [CHANGE-025-概览编辑与大纲修复](changes/CHANGE-025-概览编辑与大纲修复/archive-record.md) | completed | 修复4个用户反馈的功能缺陷：概览创意不可编辑、大纲章纲只有第一卷可用、总纲需人工输入、故事线/人物弧光AI生成无效。 | `03fe5fd` |
| [CHANGE-026-小说全功能生成](changes/CHANGE-026-小说全功能生成/archive-record.md) | completed | 用户需要一键生成一部完整小说，题材为科幻/奇幻方向，建议采用 **"赛博修仙"（CyberCultivation）** 题材 -- 将传统修仙体系嵌入近未来赛博朋克世界观，科技与灵力并存，具有巨大的发挥空间。生成过程必须使用平台全部功能：L | `03fe5fd` |
| [CHANGE-027-代码质量改进](changes/CHANGE-027-代码质量改进/archive-record.md) | completed | 本次变更是一次纯代码质量改进，不涉及新业务功能。目标是消除已识别的 8 类技术债务，提升系统的可靠性、可观测性和可维护性。所有改动均在现有架构内完成，不引入新的外部依赖（结构化日志除外）。 | `0637259` |
| [CHANGE-028-frontend-api-url-fix](changes/CHANGE-028-frontend-api-url-fix/archive-record.md) | completed | 修复 `frontend/src/views/NovelDetail.vue` 中两条 API URL 前缀错误。 | `0637259` |
| [CHANGE-029-chapter-volume-display](changes/CHANGE-029-chapter-volume-display/archive-record.md) | completed | 补充 `volume_number` 字段的返回链路，修复前端卷内章节编号显示。 | `0637259` |
| [CHANGE-030-story-knowledge-graph](changes/CHANGE-030-story-knowledge-graph/archive-record.md) | completed | 当前 xIaoShuo 平台在长篇小说生成中面临以下问题： | `1260a0f` |
| [CHANGE-031-architecture-cleanup](changes/CHANGE-031-architecture-cleanup/archive-record.md) | completed | 基于全项目架构审查，修复 3 个 Critical 和 5 个 High 级别问题。核心目标：消除重复代码、统一日志框架、补全数据完整性约束。 | `1260a0f` |
| [CHANGE-032-live-knowledge-graph](changes/CHANGE-032-live-knowledge-graph/archive-record.md) | completed | 大模型写长篇小说由于上下文窗口限制容易产生“健忘”问题，本项目通过对小说知识图谱升级，为实体引入时间轴/章节状态记录（时空与状态追踪），并在生成新章节前，自动提取大纲涉及实体，并智能从图谱中加载其最新属性、性格特征与最新双向关系（上下文关联 | `b029902` |
| [CHANGE-033-任务大厅与质量评估](changes/CHANGE-033-任务大厅与质量评估/archive-record.md) | completed | 新增任务大厅页面（TaskList），支持按状态筛选所有生成任务；扩展质量检查节点为 8 维度 AI 评估系统；知识图谱服务支持实体别名匹配和状态继承。 | `413f7f0` |
| [CHANGE-034-story-bible与三层图谱](changes/CHANGE-034-story-bible与三层图谱/archive-record.md) | archived-completed | 新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识 | `413f7f0` |
| [CHANGE-035-任务进度与图谱UX优化](changes/CHANGE-035-任务进度与图谱UX优化/archive-record.md) | archived-completed | 全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。 | `413f7f0` |
| [CHANGE-036-修复章节生成挂起与API调用](changes/CHANGE-036-修复章节生成挂起与API调用/archive-record.md) | archived-completed | 修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。 | `413f7f0` |
| [CHANGE-038-章节生成修复](changes/CHANGE-038-章节生成修复/archive-record.md) | archived-completed | 历史变更主题：CHANGE-038-章节生成修复 | `e52f87f` |
| [CHANGE-039-版本化评审与UI重构](changes/CHANGE-039-版本化评审与UI重构/archive-record.md) | archived-completed | 1. UI Apple 风格重构（章节 Tab + VolumeList） | `d60a7ee` |
| [CHANGE-042-chapter-bug-and-loadtest](changes/CHANGE-042-chapter-bug-and-loadtest/archive-record.md) | archived-completed | LOADTEST_HOST=http://staging.example.com locust -f loadtest/locustfile.py | `5799e10` |
| [CHANGE-043-API压力测试扩展](changes/CHANGE-043-API压力测试扩展/archive-record.md) | completed | 查阅归档记录 | `e5bebc2` |
| [CHANGE-044-百万字长篇生成验证](changes/CHANGE-044-百万字长篇生成验证/archive-record.md) | completed | 当前系统已完成基础功能开发与 API 压力测试，具备中篇（约20万字）小说的完整生成能力。本需求要求将生成规模从中篇升级为百万字级别长篇网文，验证系统在大规模连续生成场景下的各子系统（StoryBible、知识图谱、人物弧光、伏笔管理、质量 | `407a032` |
| [CHANGE-045-章节节奏控制与定向改写闭环](changes/CHANGE-045-章节节奏控制与定向改写闭环/archive-record.md) | completed | ### T1: ChapterBlueprint 数据模型 | `76a9dab` |
| [CHANGE-046-导出与发布系统](changes/CHANGE-046-导出与发布系统/archive-record.md) | completed | 实现了完整的小说导出功能，支持 TXT/EPUB/DOCX 三种格式，含排版模板引擎、流式下载 API 和前端导出对话框。 | `fa2be8d` |
| [CHANGE-047-大纲正文双向同步](changes/CHANGE-047-大纲正文双向同步/archive-record.md) | completed | 历史变更主题：CHANGE-047-大纲正文双向同步 | `fa2be8d` |
| [CHANGE-048-读者视角模拟](changes/CHANGE-048-读者视角模拟/archive-record.md) | completed | 历史变更主题：CHANGE-048-读者视角模拟 | `fa2be8d` |
| [CHANGE-049-项目优化解耦与冗余消除](changes/CHANGE-049-项目优化解耦与冗余消除/archive-record.md) | completed | 完成 9 个重构任务，消除了 core 层对 api/services 层的反向依赖，提取了 3 个公共模块，拆分了过大的 service 文件。 | `3974d31` |
| [CHANGE-050-工程质量修复-层级边界与前端测试](changes/CHANGE-050-工程质量修复-层级边界与前端测试/archive-record.md) | completed | 将三个超大 Vue 页面拆分为 composables + 子组件，使每个视图文件行数达标。 | `c71584b` |

## 历史实施计划

| 路径 | 状态 | 提交 |
|---|---|---|
| [plans/2026-07-03-refactor-split-projects-and-novelmanager.md](plans/2026-07-03-refactor-split-projects-and-novelmanager.md) | archived | `e124b3e` |
| [plans/2026-07-04-backend-refactor-review.md](plans/2026-07-04-backend-refactor-review.md) | archived | `e124b3e` |
| [plans/2026-07-04-frontend-refactor.md](plans/2026-07-04-frontend-refactor.md) | archived | `e124b3e` |
| [plans/2026-07-04-quality-optimization.md](plans/2026-07-04-quality-optimization.md) | archived | `450312e` |
| [plans/2026-07-04-xiaoshuo-5-priorities-complete-plan.md](plans/2026-07-04-xiaoshuo-5-priorities-complete-plan.md) | archived | `e124b3e` |
| [plans/2026-07-14-funnel-quality-gate.md](plans/2026-07-14-funnel-quality-gate.md) | archived | `f667b34` |
| [plans/2026-07-15-long-form-quality-gate-integration.md](plans/2026-07-15-long-form-quality-gate-integration.md) | archived | `374f929` |
| [plans/2026-07-18-round2-cleanup-and-refactor.md](plans/2026-07-18-round2-cleanup-and-refactor.md) | archived | `5653747` |

## 历史设计规格

| 路径 | 状态 | 提交 |
|---|---|---|
| [specs/2026-07-15-long-form-quality-gate-integration-design.md](specs/2026-07-15-long-form-quality-gate-integration-design.md) | archived | `3bec709` |

## 历史报告

| 路径 | 状态 | 提交 |
|---|---|---|
| [reports/E2E_VERIFICATION_REPORT.md](reports/E2E_VERIFICATION_REPORT.md) | archived | `2f0ce88` |
| [reports/harness/ci-result.md](reports/harness/ci-result.md) | archived | `118a656` |
| [reports/harness/code-review.md](reports/harness/code-review.md) | archived | `ca88dab` |
| [reports/harness/coding-report.md](reports/harness/coding-report.md) | archived | `ca88dab` |
| [reports/harness/test-report.md](reports/harness/test-report.md) | archived | `ca88dab` |
| [reports/harness/test-review.md](reports/harness/test-review.md) | archived | `ca88dab` |
| [reports/本次改动内容.md](reports/本次改动内容.md) | archived | `eac9604` |

## 临时工程记录

| 路径 | 状态 | 提交 |
|---|---|---|
| [scratch/post-funnel-cleanup/issues/01-security-ops-debt.md](scratch/post-funnel-cleanup/issues/01-security-ops-debt.md) | archived | `5653747` |
| [scratch/post-funnel-cleanup/issues/02-split-novel-generator.md](scratch/post-funnel-cleanup/issues/02-split-novel-generator.md) | archived | `5653747` |
| [scratch/post-funnel-cleanup/issues/03-chapter-generator-context.md](scratch/post-funnel-cleanup/issues/03-chapter-generator-context.md) | archived | `5653747` |
| [scratch/post-funnel-cleanup/issues/04-gate-convergence-short-form.md](scratch/post-funnel-cleanup/issues/04-gate-convergence-short-form.md) | archived | `5653747` |
| [scratch/post-funnel-cleanup/issues/05-long-form-progress-ui.md](scratch/post-funnel-cleanup/issues/05-long-form-progress-ui.md) | archived | `7bf09e0` |
| [scratch/post-funnel-cleanup/issues/06-short-form-taskdetail-ux.md](scratch/post-funnel-cleanup/issues/06-short-form-taskdetail-ux.md) | archived | `57949b6` |
| [scratch/post-funnel-cleanup/issues/07-project-structure-cleanup.md](scratch/post-funnel-cleanup/issues/07-project-structure-cleanup.md) | archived | `dc7720f` |
| [scratch/post-funnel-cleanup/map.md](scratch/post-funnel-cleanup/map.md) | archived | `73a9169` |
| [scratch/post-funnel-cleanup/spec.md](scratch/post-funnel-cleanup/spec.md) | archived | `73a9169` |

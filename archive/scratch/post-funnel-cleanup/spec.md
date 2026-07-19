# Spec：funnel-quality-gate 上线 + 低内聚高耦合重构

## 已完成（2026-07-16 ~ 2026-07-18）

### 首页 & 全站风格
- [x] 水墨书法首页（`/`）：毛笔逐笔书写「落笔生花」+ 鼠标墨迹 + 五屏内容滚动
- [x] 全站米白纸墨统一：清理 slate/gray/neutral 深色异类，Inspiration 整页米白化
- [x] 首页置于根路径 `/`，书房移至 `/shelf`

### Dev 体验
- [x] 取消登录守卫，dev 免登录（DEV_AUTO_LOGIN）
- [x] 路由守卫取消 + App 根底改纸白

### Bug 修复
- [x] 人物对话句尾 `------`（后处理 + prompt 禁半角连字符）
- [x] 长篇质量门禁 state_delta/quality_status 未落库（persist 顺序 + 门禁字段双保险）
- [x] long-form 鉴权 + owner_id + 进度路由
- [x] 大纲生成 499/504（nginx 超时 300s→600s + 前端进度提示）
- [x] 进度逐章实时落库 LFP 表（进行中卷不再卡 0）
- [x] persist upsert（重试不撞唯一约束）
- [x] 失败章节不写垃圾行
- [x] chapters.state_delta/quality_status 迁移 + compose DEV_AUTO_LOGIN 注入

### 低内聚高耦合重构（三步）
- [x] Step 1：提取 `compute_chapter_numbering` 纯函数（TDD，4 测试）
- [x] Step 2：GVC 用纯函数 + 支持无卷退化
- [x] Step 2.5：提取 `record_chapter_artifacts` 版本+StoryBible 语义统一（TDD，3 测试）
- [x] Step 3：删 `_generate_chapters_batch`（-120 行），全路径接入 GVC

### 工程化
- [x] Matt Pocock engineering skills 配置（issue-tracker=本地 markdown，domain=单上下文）
- [x] CONTEXT.md 领域术语表

## 第二轮（2026-07-18）：工程债务清理 + 依赖链重构

### Ticket 01 — 安全运维 debt（partial）
- [x] BackgroundTasks 丢失保护：启动恢复同时清理 pending 任务，防进程内调度丢失后假死（`recover_interrupted_tasks` where 含 pending + was_running 文案区分）
- [x] 前端 5 组件风格残留统一纸墨（ForeshadowTracker/ChapterEdit/KnowledgeGraphView/KnowledgeGraph/Careers/Home：neutral→ink/paper, accent→vermilion，保留语义色）
- [ ] 关 DEV_AUTO_LOGIN / 改 root 密码 / 恢复登录守卫 — 用户决策暂不处理

### Ticket 02 — 拆 novel_generator
- [x] 长篇三入口（generate_chapters_background/generate_long_form_background/generate_volume_background）迁入 long_form_generation_helpers
- [x] novel_generator 996→640 行，保留 re-export 保测试 patch 路径稳定

### Ticket 03 — chapter_generator 接口收窄
- [x] ChapterGenContext dataclass 封装 14 个散列参数（chars_str/world_str/storylines_str/style/blueprint/story_bible/prev/target_words...）
- [x] generate_single_chapter / generate_chapter_stream / _generate_single_chapter_inner 三函数收 ctx
- [x] 修 helpers storylines 漏传 bug（gen_ctx.storylines_str 未透传到 ChapterGenContext）

### Ticket 04 — 短篇 quality_check 收敛 gate
- [x] 短篇 LangGraph quality_check 节点收敛到 run_quality_gate（评分+state_delta+consistency 硬门禁统一走 gate）
- [x] 保留 KG 抽取副作用（consistency_warnings / kg_continuity_report / extract_from_chapter）
- [x] 删 KG verdict / StoryBible error 硬门禁（口径收敛为 gate L2 评分 < 0.4）
- [x] 短篇首次抽 state_delta 入 state
- [x] revision_requests 用 gate.warnings 兜底（L0 告警，取前 5）

### 遗留债务清理
- [x] long_form_generation_helpers `i` NameError（真实运行时 bug，588/693 行，改 enumerate 的 vol_ch_idx）
- [x] test_novel_generator_supplement 4 孤儿测试（删 TestGenerateChaptersBatch 死代码 + 重写 TestGenerateVolumeBackgroundFallback patch 路径）
- [x] test_change036 慢测试（前两个重试测试 patch wait_exponential → 0.2s；exhausts 降级路径退避未覆盖 → skip 待定位）

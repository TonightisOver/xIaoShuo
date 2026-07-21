# xIaoShuo — 领域术语表

## 核心概念
- **小说(Novel)**：用户创建的作品，含 idea/title/novel_type/target_words/writing_style
- **章节(Chapter)**：小说的基本单元，按 chapter_number 全局连续编号，含 content/word_count/status
- **卷(Volume)**：章节的分组容器，含 volume_number/chapter_start/chapter_end/outline
- **任务(Task)**：异步生成任务，含 task_id/status/pipeline，后台 LangGraph 或长篇幅流水线执行

## 生成流水线
- **短篇(Short-form)**：target_words ≤ 200k，走 13 阶段 LangGraph 流水线（idea_expansion→world_building→character_design→outline→chapter_generation→quality_check→complete），跳 TaskDetail 流程页
- **长篇(Long-form)**：target_words > 200k，走 generate_long_form_background 逐卷循环（master_outline→volume_outline→generate_volume_chapters→quality_report），跳 NovelDetail
- **逐章生成(CGV，generate_volume_chapters)**：统一逐章生成函数，流式+gate+persist+版本+StoryBible，全路径共用

## 质量体系
- **质量门禁(Gate)**：L0 规则(零Token)→L1 风险分级→L2 LLM评审(仅高风险章)→L3 候选改写(仅不达标章)
- **state_delta**：每章抽取的结构化状态增量(关键事件/人物变化/伏笔/时间线/冲突)，替代正文截取做长期记忆
- **quality_status**：章节质量标记 verified/unverified/failed
- **一致性硬门禁(Consistency block)**：人物/世界观设定矛盾检测

## 创作过程控制
- **创作阶段(Creative Stage)**：把生成拆成 10 个可控阶段（创意→世界观→角色→总纲→卷纲→章节蓝图→正文→质检→人工确认→定稿），每阶段产物可查看/编辑/锁定/审批/局部重生成
- **产物(Artifact)**：受控的创作单元，按 artifact_type（novel/world/character/master_outline/volume_outline/blueprint/chapter）+ artifact_id 定位
- **控制状态(Control Status)**：产物 8 态机 —— draft/generated/edited/approved/locked/stale/generating/failed，非法转移被拒
- **创作模式(Creation Mode)**：auto（连续生成不打断）/ assisted（关键阶段 1/4/7/9 等待确认）/ manual（每阶段等待确认），控制生成后是否置 awaiting_review
- **影响范围(Impact)**：上游产物变更时按依赖图计算下游 —— upstream/direct_downstream/full_downstream，并分流 regenerable（未锁可重生成）与 to_mark_stale（已锁/已确认仅标记过期）
- **依赖图(Dependency Graph)**：novel→world/master_outline，world→character/master_outline，character→master_outline，master_outline→volume_outline，volume_outline→blueprint/chapter，blueprint→chapter
- **产物版本(Artifact Version)**：非正文产物的通用版本快照（ArtifactVersion 表），正文版本仍复用 ChapterVersion，不建第二套
- **乐观锁(Optimistic Lock)**：所有写操作带 expected_version，与当前版本不符抛 409 冲突，防止基于过期页面覆盖
- **操作日志(Operation Log)**：编辑/生成/重生成/锁定/解锁/确认/回退/采纳候选等操作留痕，含产物类型/ID/前后版本/操作人/时间/原因/任务ID
- **生成范围(Generation Scope)**：单章/范围/单卷/从某章继续/仅重蓝图/仅重正文，支持保留已锁定、跳过已确认，可预览受影响章数与 Token

## 生成辅助
- **知识图谱(Knowledge Graph)**：实体三元组抽取，防范"吃设定"
- **故事圣经(Story Bible)**：人物/伏笔/时间线约束，生成后反向更新
- **版本(Chapter Version)**：每次生成/重写自动快照，支持对比/激活/回滚
- **灌水检测(Filler Detection)**：段落重复/句式复用/字数校验
- **进度(LFP，Long Form Progress)**：长篇逐章进度表

## 前端
- **首页(Landing)**：`/`，水墨书法风，介绍平台特性
- **书房(Shelf)**：`/shelf`，小说书架列表
- **灵感向导(Inspiration Wizard)**：`/inspiration`，AI 对话式创意收集
- **流程页(TaskDetail)**：`/task/:id`，短篇生成进度+控制台
- **创作控制台(CreativeStudio)**：`/novels/:id/studio`，10 阶段可视化控制面板，查看/编辑/锁定/审批/局部重生成产物

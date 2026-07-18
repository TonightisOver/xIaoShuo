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

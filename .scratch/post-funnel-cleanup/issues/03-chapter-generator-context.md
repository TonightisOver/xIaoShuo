# 03 — chapter_generator 接口收窄：14 参数 → Context 对象

**What to build:** `generate_single_chapter`/`generate_chapter_stream`/`_generate_single_chapter_inner` 接收 11-14 个裸参数（chars_str/world_str/storylines_json/style/blueprint/story_bible/prev...），调用方三处手工拆解 gen_ctx（已发散：helpers:510 漏传 storylines）。提取 `GenerationContext` 对象，chapter_generator 读它，调用方不再逐字段拆。

**Blocked by:** 02（novel_generator 拆完后调用方数量稳定，改接口风险更可控）

**Status:** ready-for-agent

- [ ] 定义 `GenerationContext`：封装 chars_str/world_str/storylines_str/style_instruction/blueprint/story_bible_context/previous_chapter/target_words
- [ ] chapter_generator 内部函数接收 GenerationContext 替代散列参数
- [ ] 三处调用方（novel_generator LangGraph 节点、long_form_generation_helpers、chapter_generation 节点）改为传 ctx
- [ ] 顺手修 storylines 漏传 bug：helpers:510 补 storylines_str
- [ ] 测试：章节生成相关测试全部通过，无回归

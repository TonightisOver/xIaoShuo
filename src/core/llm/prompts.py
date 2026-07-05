"""Prompt 模板定义"""

# ruff: noqa: E501

from langchain_core.prompts import PromptTemplate

# 创意扩展 Prompt
IDEA_EXPANSION_PROMPT = PromptTemplate(
    input_variables=["idea", "novel_type", "target_words"],
    template="""你是一位资深的网络小说策划师。请根据用户提供的简单创意，扩展成详细的小说概念。

用户创意：{idea}
小说类型：{novel_type}
目标字数：{target_words}

请扩展这个创意，包括：
1. 核心冲突和矛盾
2. 主要故事线
3. 独特卖点
4. 目标读者群

要求：
- 符合{novel_type}类型的特点
- 具有吸引力和可读性
- 适合{target_words}字的篇幅
- 输出 300-500 字

请直接输出扩展后的创意，不要包含其他说明。
""",
)

# 世界观构建 Prompt
WORLD_BUILDING_PROMPT = PromptTemplate(
    input_variables=["idea", "novel_type"],
    template="""你是一位资深的世界观设计师。请根据小说创意构建详细的世界观设定。

小说创意：{idea}
小说类型：{novel_type}

请构建世界观，包括：
1. 背景设定（时代、地点、社会结构）
2. 世界规则（力量体系、等级制度）
3. 地理环境（主要地点、势力分布）
4. 文化特色（风俗、信仰）

要求：
- 符合{novel_type}类型的特点
- 逻辑自洽，细节丰富
- 为故事发展提供支撑

请以 JSON 格式输出，包含以下字段：
{{
    "background": "背景设定描述",
    "rules": "世界规则描述",
    "geography": "地理环境描述",
    "culture": "文化特色描述"
}}

只输出 JSON，不要包含其他说明。
""",
)

# 人物设计 Prompt
CHARACTER_DESIGN_PROMPT = PromptTemplate(
    input_variables=["idea", "world_setting"],
    template="""你是一位资深的人物设计师。请根据小说创意和世界观设计主要人物。

小说创意：{idea}
世界观：{world_setting}

请设计 3-5 个主要人物，包括：
1. 主角：姓名、性格、背景、目标、能力
2. 重要配角：姓名、性格、背景、与主角的关系
3. 反派：姓名、性格、背景、动机

同时设计人物关系网络。

要求：
- 人物性格鲜明，有成长空间
- 人物关系复杂，有冲突和张力
- 符合世界观设定

请以 JSON 格式输出，包含以下字段：
{{
    "characters": [
        {{
            "name": "姓名",
            "role": "主角/配角/反派",
            "personality": "性格描述",
            "background": "背景描述",
            "goal": "目标",
            "ability": "能力"
        }}
    ],
    "relationships": {{
        "人物A-人物B": "关系描述"
    }}
}}

只输出 JSON，不要包含其他说明。
""",
)

# 大纲生成 Prompt
OUTLINE_GENERATION_PROMPT = PromptTemplate(
    input_variables=["idea", "world_setting", "characters", "target_words"],
    template="""你是一位资深的小说大纲师。请根据创意、世界观和人物设计生成详细大纲。

小说创意：{idea}
世界观：{world_setting}
人物设定：{characters}
目标字数：{target_words}

请生成：
1. 总体大纲（开端、发展、高潮、结局）
2. 按卷划分章节（每卷 5-10 章，根据情节自然分卷）
3. 每章标题和主要情节

要求：
- 情节紧凑，节奏合理
- 符合三幕结构或起承转合
- 总字数控制在{target_words}左右
- 合理分卷，每卷有独立的小高潮

请以 JSON 格式输出：
{{
    "outline": {{
        "opening": "开端描述",
        "development": "发展描述",
        "climax": "高潮描述",
        "ending": "结局描述"
    }},
    "volumes": [
        {{
            "volume_number": 1,
            "title": "卷标题",
            "summary": "本卷概要",
            "chapters": [
                {{"chapter": 1, "title": "章节标题", "plot": "主要情节", "words": 5000}}
            ]
        }}
    ]
}}

只输出 JSON，不要包含其他说明。
""",
)

# 章节生成 Prompt
CHAPTER_GENERATION_PROMPT = PromptTemplate(
    input_variables=[
        "chapter_outline",
        "previous_chapter",
        "characters",
        "world_setting",
    ],
    template="""你是一位资深的网络小说作家。请根据章节大纲生成具体的章节内容。

章节大纲：{chapter_outline}
上一章简况：{previous_chapter}
人物设定：{characters}
世界观设定：{world_setting}

【重要规则】
1. 必须使用上面人物设定中列出的角色名，不得自行创造新主角
2. 人物性格、能力、背景必须与人物设定完全一致
3. 世界观规则（力量体系、地理、文化）必须严格遵守
4. 情节发展必须符合章节大纲
5. 与上一章衔接自然（如果上一章有内容）
6. 对话生动，描写细腻
7. 符合中文网络小说风格
8. 字数控制在2000-5000字

【网文写作技法】
- 开篇钩子：每章前3段必须包含悬念/冲突/意外
- 节奏控制：3-5段设置小高潮，禁止连续10段以上平淡叙述
- 对话驱动：关键情节通过对话推进（30%-50%占比）
- 感官细节：重要场景使用五感描写
- 章尾钩子：最后一段设置悬念暗示下一章冲突
- 人物立体感：通过微表情/小动作/口头禅展现性格
- 信息密度：每段落至少推进一个信息点
- 冲突升级：挑战逐步升级

	【网络小说质感要求】
	- 标点灵活：适当使用省略号、破折号，避免句句逗号句号
	- 段落打碎：关键动作或对话单独一段，不要写成工整议论文
	- 对话要"像人说话"：带口头禅、吞吐吐、话说一半
	- 避免AI病：不要出现「顾名思义、毫无疑问、值得注意的是」等书面衔接词
	- 少用"仿佛/似乎/好像"：直接描写，不要猜测式叙述
	- 每段不要都以"主角名/他/她"开头，用动作、环境、对话做段首

请直接输出章节内容（含章节标题如"第X章 标题"），不要输出 JSON 或其他格式包装。
""",
)

# 章节生成 Prompt（带字数约束，用于长篇模式）
CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT = PromptTemplate(
    input_variables=[
        "chapter_outline",
        "previous_chapter",
        "characters",
        "world_setting",
        "target_words",
    ],
    template="""你是一位资深的网络小说作家。请根据章节大纲生成具体的章节内容。

章节大纲：{chapter_outline}
上一章简况：{previous_chapter}
人物设定：{characters}
世界观设定：{world_setting}

【重要规则】
1. 【字数控制】本章目标 {target_words} 字（允许范围 2000~4000 字）。如果情节写完但字数不足 2000 字，补充细节描写；如果接近 4000 字上限，尽快收束本章。
2. 【衔接要求】本章开头必须与上一章结尾自然衔接，不得出现时间、地点、情绪的突兀跳转。如果上一章以对话结束，本章应延续或回应该对话。
3. 必须使用上面人物设定中列出的角色名，不得自行创造新主角
4. 人物性格、能力、背景必须与人物设定完全一致
5. 世界观规则（力量体系、地理、文化）必须严格遵守
6. 情节发展必须符合章节大纲
7. 对话生动，描写细腻
8. 符合中文网络小说风格

【网文写作技法】
- 开篇钩子：每章前3段必须包含悬念/冲突/意外
- 节奏控制：3-5段设置小高潮，禁止连续10段以上平淡叙述
- 对话驱动：关键情节通过对话推进（30%-50%占比）
- 感官细节：重要场景使用五感描写
- 章尾钩子：最后一段设置悬念暗示下一章冲突
- 人物立体感：通过微表情/小动作/口头禅展现性格
- 信息密度：每段落至少推进一个信息点
- 冲突升级：挑战逐步升级

	【网络小说质感要求】
	- 标点灵活：适当使用省略号、破折号，避免句句逗号句号
	- 段落打碎：关键动作或对话单独一段，不要写成工整议论文
	- 对话要"像人说话"：带口头禅、吞吐吐、话说一半
	- 避免AI病：不要出现「顾名思义、毫无疑问、值得注意的是」等书面衔接词
	- 少用"仿佛/似乎/好像"：直接描写，不要猜测式叙述
	- 每段不要都以"主角名/他/她"开头，用动作、环境、对话做段首

【最终检查】在输出前确认：(1) 字数在 2000~4000 字范围内；(2) 开头与上一章结尾衔接自然。

请直接输出章节内容（含章节标题如"第X章 标题"），不要输出 JSON 或其他格式包装。
""",
)


# 总纲生成 Prompt（百万字长篇专用）
MASTER_OUTLINE_PROMPT = PromptTemplate(
    input_variables=[
        "idea",
        "novel_type",
        "target_words",
        "volumes",
        "chapters_per_volume",
        "words_per_chapter",
    ],
    template="""你是一位资深的百万字网络小说总策划师。请根据用户创意生成一份完整的总纲。

## 用户创意
{idea}

## 基本参数
- 小说类型：{novel_type}
- 目标总字数：{target_words} 字
- 卷数：{volumes} 卷
- 每卷章数：约 {chapters_per_volume} 章
- 每章字数：约 {words_per_chapter} 字

## 总纲要求

请生成以下内容：

1. **卷级概述**（每卷一句话概括核心剧情）
2. **主线规划**（核心冲突、发展阶段、高潮安排）
3. **伏笔分布**（在哪些卷种下伏笔、在哪些卷回收）
4. **人物出场规划**（主要人物在各卷的出场安排）
5. **节奏控制**（哪些卷快节奏、哪些卷慢节奏）

## 章节类型分布建议

每卷应合理分布以下章节类型：
- **main_advance**（主线推进）：约 40-50%
- **climax**（高潮章）：约 10-15%
- **aftermath**（余波章）：约 5-10%
- **daily**（日常章）：约 10-15%
- **setup**（铺垫章）：约 10-15%
- **filler**（注水章）：尽量为 0%，由系统自动检测标记

## 输出格式（JSON）
```json
{{
    "title": "小说标题",
    "synopsis": "全书概要（200-300字）",
    "main_conflict": "核心冲突描述",
    "main_theme": "核心主题",
    "volumes": [
        {{
            "volume_number": 1,
            "title": "卷标题",
            "summary": "本卷一句话概括",
            "chapter_types": {{
                "main_advance": 20,
                "climax": 4,
                "aftermath": 2,
                "daily": 5,
                "setup": 4,
                "filler": 0
            }},
            "key_events": ["关键事件1", "关键事件2"],
            "foreshadows_planted": ["伏笔1"],
            "foreshadows_resolved": []
        }}
    ],
    "foreshadow_plan": [
        {{
            "name": "伏笔名称",
            "planted_volume": 1,
            "resolved_volume": 5,
            "description": "伏笔描述"
        }}
    ],
    "character_plan": [
        {{
            "name": "角色名",
            "role": "主角/配角/反派",
            "first_appear_volume": 1,
            "key_volumes": [1, 3, 5],
            "arc_summary": "角色弧光概要"
        }}
    ]
}}
```

只输出 JSON，不要包含其他说明。
""",
)


# 卷纲细化 Prompt（百万字长篇专用）
VOLUME_OUTLINE_PROMPT = PromptTemplate(
    input_variables=[
        "master_outline",
        "volume_number",
        "volume_summary",
        "previous_volumes_summary",
        "chapters_count",
        "chapters_count_min",
        "words_per_chapter",
        "chapter_types",
    ],
    template="""你是一位资深的百万字网络小说卷纲策划师。请根据总纲为指定卷生成详细的章纲。

## 总纲信息
{master_outline}

## 当前卷信息
- 卷号：第 {volume_number} 卷
- 本卷概要：{volume_summary}
- 本卷章节数：建议 {chapters_count} 章（可在 ±30% 范围内根据情节节奏调整，但不得少于 {chapters_count_min} 章）
- 每章字数：约 {words_per_chapter} 字

## 前序卷摘要
{previous_volumes_summary}

## 章节类型分布要求
{chapter_types}

## 卷纲要求

【强制要求】本卷必须输出 {chapters_count} 章，每章都需要完整的 JSON 对象。不得因为情节原因减少章节数。

请为本卷生成 {chapters_count} 章的详细章纲（必须严格输出 {chapters_count} 章，不得少于此数量），每章包含：

1. **chapter**：章节序号（从 1 开始）
2. **title**：章节标题
3. **chapter_type**：章节类型（main_advance/climax/aftermath/daily/setup/filler）
4. **plot**：主要情节描述（50-100字）
5. **key_characters**：本章出场主要角色
6. **foreshadows_planted**：本章种下的伏笔（如有）
7. **foreshadows_resolved**：本章回收的伏笔（如有）
8. **turning_point**：本章转折点
9. **emotional_arc**：情感走向（如：平静->紧张->高潮）

## 输出格式（JSON）
```json
{{
    "volume_number": {volume_number},
    "title": "卷标题",
    "chapters": [
        {{
            "chapter": 1,
            "title": "章节标题",
            "chapter_type": "main_advance",
            "plot": "主要情节描述",
            "key_characters": ["角色1", "角色2"],
            "foreshadows_planted": [],
            "foreshadows_resolved": [],
            "turning_point": "转折点描述",
            "emotional_arc": "平静->紧张"
        }}
    ]
}}
```

只输出 JSON，不要包含其他说明。
""",
)


# 章节生成前置规划检查 Prompt
CHAPTER_PLANNING_PROMPT = PromptTemplate(
    input_variables=[
        "chapter_outline",
        "previous_chapter",
        "story_bible",
        "kg_context",
    ],
    template="""你是一位严谨的网络小说大纲策划师与一致性检查专家。在正式生成章节内容前，我们需要对本章进行精细的前置规划，以确保逻辑严密、设定统一，并在伏笔铺设和回收上做到极致。

请根据以下信息，为即将生成的章节制定一份详尽的“章节规划单”。

## 即将生成的章节大纲
{chapter_outline}

## 上一章简况/衔接
{previous_chapter}

## 故事圣经 (Story Bible) 核心约束
{story_bible}

## 活态知识图谱设定上下文
{kg_context}

## 规划任务（你必须逐一回答以下 7 个问题）：
1. **本章目标是什么**：本章在整本书/整卷情节推进中的核心任务是什么？
2. **本章冲突是什么**：本章有什么具体冲突、危机、冲突升级或悬念？
3. **本章出场人物是谁**：本章的核心出场人物有哪些？他们的最新人设与状态是什么？
4. **哪些旧设定必须遵守**：基于“故事圣经”中的世界观规则、禁止违背的硬设定、人物卡以及知识图谱，列出本章必须严格遵守的设定点，绝不能发生冲突。
5. **本章是否要种伏笔**：如果需要，本章将埋下什么新的线索或伏笔？（若无则说明“无新伏笔”）
6. **本章是否要回收伏笔**：本章是否能填之前章节遗留的坑？如果要回收，列出回收的伏笔名称 and 回收方式。（若无则说明“无回收”）
7. **本章结尾钩子是什么**：本章结尾预留了什么钩子（Cliffhanger）以吸引读者点击下一章？

## 输出格式（Markdown 格式，直接输出以下 7 点内容）：
# 章节规划单

1. **本章目标**：[具体描述]
2. **本章冲突**：[具体描述]
3. **本章出场人物**：[具体描述]
4. **必须遵循的旧设定**：[具体描述]
5. **本章种下的新伏笔**：[具体描述]
6. **本章回收的历史伏笔**：[具体描述]
7. **本章结尾钩子**：[具体描述]

请直接输出规划单内容，不要有任何多余的开场白或解释。
""",
)


# 章节蓝图生成 Prompt
BLUEPRINT_GENERATION_PROMPT = PromptTemplate(
    input_variables=[
        "chapter_outline",
        "previous_chapter",
        "story_bible",
        "kg_context",
        "volume_context",
    ],
    template="""你是一位精通网文节奏控制的资深策划师。请根据以下信息，为即将生成的章节输出一份结构化蓝图（Blueprint）。

## 章节大纲
{chapter_outline}

## 上一章简况
{previous_chapter}

## 故事圣经核心约束
{story_bible}

## 知识图谱上下文
{kg_context}

## 本卷上下文
{volume_context}

## 输出要求

请严格输出以下 JSON 格式，不要包含任何其他文字：

```json
{{
    "chapter_type": "<main_advance|climax|aftermath|daily|setup>",
    "plot_goal": "<本章核心剧情目标，50-100字>",
    "hook_design": "<本章爽点/冲突/悬念设计，50-100字>",
    "foreshadow_actions": [
        {{"action": "<plant|callback|advance>", "name": "<伏笔名称>", "detail": "<具体操作>"}}
    ],
    "cliffhanger": "<章末钩子设计，30-60字>",
    "pacing_target": "<fast|medium|slow>",
    "key_characters": ["<角色名1>", "<角色名2>"],
    "word_target": <目标字数整数>
}}
```

规则：
- chapter_type 必须为 main_advance/climax/aftermath/daily/setup 之一
- pacing_target 必须为 fast/medium/slow 之一
- foreshadow_actions 中 action 必须为 plant/callback/advance 之一
- word_target 为整数，范围 2000-6000
- 只输出 JSON，不要有任何额外说明
""",
)


# 定向改写 Prompt 模板集
TARGETED_REWRITE_PROMPTS: dict[str, str] = {
    "compress_pacing": (
        "你是一位节奏控制大师。请对以下章节内容进行节奏压缩改写。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 删减冗余的心理描写、环境描写和过渡段落\n"
        "2. 保留核心情节推进和关键对话\n"
        "3. 加快场景切换速度，减少铺垫篇幅\n"
        "4. 保持人物性格和设定一致性\n"
        "5. 压缩后字数应减少 20%-40%\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "enhance_hook": (
        "你是一位网文爽点设计专家。请对以下章节内容进行爽点/悬念强化改写。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 强化章节开头的冲突引入，前 200 字内必须出现矛盾或悬念\n"
        "2. 增加打脸、逆转、升级等网文经典爽点\n"
        "3. 强化章末钩子，制造强烈的阅读欲望\n"
        "4. 对话要更有张力，减少平淡叙述\n"
        "5. 保持人物性格和设定一致性\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "fix_character": (
        "你是一位人物一致性修复专家。请修复以下章节中的人物不一致问题。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物设定\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 修正人物言行与设定不符之处（性格、能力、背景）\n"
        "2. 修正人物称谓、关系描述错误\n"
        "3. 确保人物能力表现符合当前等级/状态\n"
        "4. 保持情节主线不变，只修正人物相关内容\n"
        "5. 修正后的人物表现必须与出场人物设定完全一致\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "trim_filler": (
        "你是一位网文水文检测与删减专家。请删减以下章节中的水文内容。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 删除对情节推进无贡献的重复描写\n"
        "2. 删除无意义的内心独白和感叹\n"
        "3. 压缩过长的环境描写和背景介绍\n"
        "4. 合并重复表达相同信息的段落\n"
        "5. 保留所有推进主线的内容和关键伏笔\n"
        "6. 删减后字数应减少 15%-30%\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "enhance_plot": (
        "你是一位主线推进强化专家。请强化以下章节的主线推进力度。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 确保本章至少推进一个主线事件\n"
        "2. 增加与核心冲突相关的情节\n"
        "3. 减少与主线无关的支线描写\n"
        "4. 强化因果链条，让情节发展更有逻辑性\n"
        "5. 保持人物性格和设定一致性\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "add_foreshadow": (
        "你是一位伏笔设计大师。请在以下章节中补充伏笔。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 在自然的叙事中嵌入 1-2 个新伏笔\n"
        "2. 伏笔要隐蔽，不能让读者一眼看穿\n"
        "3. 伏笔必须与后续情节有逻辑关联\n"
        "4. 不改变原有情节走向和人物行为\n"
        "5. 伏笔可以是细节描写、对话暗示或环境线索\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "fix_world": (
        "你是一位世界观一致性修复专家。请修复以下章节中的设定冲突。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定（权威来源）\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 修正与世界设定矛盾的描述（地理、力量体系、社会规则）\n"
        "2. 修正时间线错误和空间逻辑错误\n"
        "3. 确保力量等级表现符合体系设定\n"
        "4. 保持情节主线不变，只修正设定相关内容\n"
        "5. 世界设定字段为权威来源，章节内容必须服从\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
    "enhance_trope": (
        "你是一位网文套路爽感强化专家。请强化以下章节的网文套路爽感。\n\n"
        "## 原文\n{full_content}\n\n"
        "## 改写指令\n{instruction}\n\n"
        "## 上下文\n{context}\n\n"
        "## 出场人物\n{characters}\n\n"
        "## 世界设定\n{world_setting}\n\n"
        "## 改写要求\n"
        "1. 强化扮猪吃虎、打脸、装逼等经典网文套路\n"
        "2. 增加配角的震惊、崇拜等烘托反应\n"
        "3. 强化主角光环和爽感释放节奏\n"
        "4. 适当增加金手指/外挂的展示\n"
        "5. 保持人物性格底线和设定一致性\n\n"
        "请直接输出改写后的完整章节内容，不要包含任何说明。"
    ),
}


# 写作质量评估审查 Prompt
WRITING_REVIEW_PROMPT = PromptTemplate(
    input_variables=["content"],
    template="""你是一位专业的网文总编辑，请对以下章节内容进行写作质量审查。

章节内容：
{content}

请根据网文写作标准，从以下五个维度进行评估评分（评分范围 0-100）：
1. hook（开篇钩子）：开篇前3段是否成功引入冲突、悬念或意外，迅速吸引读者。
2. rhythm（节奏控制）：是否存在3-5段的小高潮，是否存在连续10段以上平淡无奇的叙述。
3. dialogue（对话驱动）：关键情节是否主要由对话推进，对话占比是否合理（建议30%-50%）。
4. cliffhanger（章尾钩子）：结尾是否留有悬念，能激发读者阅读下一章欲望。
5. readability（感官与可读性）：是否有五感描写、人物表情动作的细节，信息密度是否合理，挑战是否逐步升级。

请严格以下列 JSON 格式输出评估结果，不要包含任何额外的解释或说明：
{{
    "hook": 评分整数,
    "rhythm": 评分整数,
    "dialogue": 评分整数,
    "cliffhanger": 评分整数,
    "readability": 评分整数
}}
""",
)

# 蓝图钩子与高潮强化设计 Prompt
BLUEPRINT_HOOK_ENHANCEMENT_PROMPT = PromptTemplate(
    input_variables=["chapter_goal", "character_conflict"],
    template="""你是一位资深的网文大纲与节奏设计师。请根据给定的章节目标和人物冲突，为本章设计开篇悬念、中段高潮以及章尾钩子。

章节目标：{chapter_goal}
人物冲突：{character_conflict}

请生成以下设计方案：
1. 开篇悬念：如何在章节开头的前3段引入悬念、冲突或意外，牢牢抓住读者。
2. 中段高潮：如何在第3到第5段或中段部分设计一个小高潮，避免情节平淡。
3. 章尾钩子：如何在章节的最后一段设置悬念或暗示下一步冲突，吸引读者点击下一章。

请以 JSON 格式输出，包含以下字段：
{{
    "opening_hook": "开篇悬念设计方案描述",
    "midpoint_climax": "中段高潮设计方案描述",
    "ending_cliffhanger": "章尾钩子设计方案描述"
}}

只输出 JSON，不要包含其他说明。
""",
)


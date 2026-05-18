"""Prompt 模板定义"""

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

请直接输出章节内容（含章节标题如"第X章 标题"），不要输出 JSON 或其他格式包装。
""",
)

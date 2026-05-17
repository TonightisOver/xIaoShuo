# 数据模型设计

## ER 关系图

```
novels (1) ──── (1) world_settings
  │
  ├──── (N) power_systems
  ├──── (N) characters ──── (N) character_arcs
  ├──── (N) chapters
  ├──── (N) volumes
  ├──── (N) outlines (master/volume/chapter)
  ├──── (N) storylines ──── (N) storyline_characters
  ├──── (N) scenes_table
  ├──── (N) conversations ──── (N) messages
  └──── (N) tasks
```

## 表结构（14 张表）

### novels（小说项目）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | VARCHAR(100) UNIQUE | 业务 ID |
| title | VARCHAR(200) | 标题 |
| idea | TEXT | 创意 |
| novel_type | VARCHAR(50) | 类型（13 种） |
| target_words | INTEGER | 目标字数 |
| writing_style | VARCHAR(50) | 文风（8 预设 + 自定义） |
| custom_style_description | TEXT | 自定义风格描述 |
| writing_style_prompt | TEXT | LLM 生成的风格指令 |
| status | VARCHAR(20) | draft/generating/completed/failed |

### world_settings（世界观）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | 一对一 |
| background | TEXT | 世界背景 |
| geography | TEXT | 地理环境 |
| culture | TEXT | 文化体系 |
| rules | TEXT | 世界规则 |
| extra | JSON | 扩展 |

### characters（人物）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| name | VARCHAR(100) | 姓名 |
| role | VARCHAR(50) | 主角/配角/反派/导师 |
| description, personality, abilities, background_story | TEXT | 详情 |

### chapters（章节）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| volume_number | INTEGER | 所属卷 |
| chapter_number | INTEGER | 章节号 |
| title | VARCHAR(200) | 标题 |
| content | TEXT | 正文 |
| word_count | INTEGER | 字数 |
| status | VARCHAR(20) | draft/generated/edited/regenerated |

### volumes（卷）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| volume_number | INTEGER | 卷号 |
| title, summary | TEXT | 标题/概要 |
| outline | JSON | 卷大纲 |
| status | VARCHAR(20) | draft/generating/completed |

### outlines（三级大纲）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| level | VARCHAR(20) | master/volume/chapter |
| volume_number | INTEGER | 卷号（volume/chapter） |
| chapter_number | INTEGER | 章号（chapter） |
| content | JSON | 大纲内容 |
| status | VARCHAR(20) | draft/confirmed |

### storylines（故事线）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| name | VARCHAR(200) | 线索名称 |
| type | VARCHAR(20) | main/sub/hidden |
| description | TEXT | 描述 |
| key_events | JSON | 关键事件 |
| status | VARCHAR(20) | active/resolved/abandoned |

### character_arcs（人物弧光）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| character_id | FK → characters | |
| arc_type | VARCHAR(30) | growth/fall/flat/transformation |
| description | TEXT | 弧光描述 |
| stages | JSON | 阶段列表 |

### scenes_table（场景）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| name | VARCHAR(200) | 场景名称 |
| location | VARCHAR(200) | 地理位置 |
| description | TEXT | 描述 |
| appearances | JSON | 出现章节 |

### storyline_characters（故事线-人物关联）
| 字段 | 类型 |
|------|------|
| storyline_id | FK → storylines |
| character_id | FK → characters |
| role_in_line | VARCHAR(50) |

### conversations（对话）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| topic | VARCHAR(100) | 讨论主题 |
| status | VARCHAR(20) | active/concluded |

### messages（消息）
| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | FK → conversations | |
| role | VARCHAR(20) | user/assistant |
| content | TEXT | 消息内容 |
| confirmed_as | VARCHAR(50) | null/world/character/storyline/outline |

### tasks（生成任务）
| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(100) UNIQUE | 任务 ID |
| novel_id | FK → novels | 关联小说 |
| status | VARCHAR(20) | pending/running/completed/failed |
| progress | JSON | 进度 |
| result | JSON | 结果 |

### power_systems（等级体系）
| 字段 | 类型 | 说明 |
|------|------|------|
| novel_id | FK | |
| name | VARCHAR(100) | 体系名称 |
| levels | JSON | 等级列表 |

## 级联删除

删除 novel 时自动删除所有关联子资源（CASCADE）。tasks.novel_id 设为 NULL（SET NULL）。

## 数据隔离

所有子资源的 update/delete 操作都校验 novel_id 归属，防止跨小说数据篡改。

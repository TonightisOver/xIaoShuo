# 故事线与图谱系统

## 概述

管理小说的叙事结构：故事线（情节线索）、人物弧光（角色成长轨迹）、场景（时空地点），以及它们之间的三元关系。

## 三大实体

### 故事线 (Storylines)
贯穿多章的情节线索。

| 类型 | 说明 |
|------|------|
| main | 主线 — 核心情节 |
| sub | 副线 — 辅助情节 |
| hidden | 暗线 — 隐藏伏笔 |

状态：active → resolved / abandoned

### 人物弧光 (Character Arcs)
人物在故事中的内在变化轨迹。

| 弧光类型 | 说明 |
|---------|------|
| growth | 成长型（从弱到强） |
| fall | 堕落型（从善到恶） |
| flat | 平坦型（始终如一） |
| transformation | 转变型（从敌到友） |

每个弧光包含多个阶段（stages），每阶段有章节范围、状态、触发事件。

### 场景 (Scenes)
故事中的重要时空场景，记录出现的章节和事件。

## 三元关系

- 故事线 ↔ 人物（storyline_characters 关联表）
- 故事线 → 关键事件（key_events JSON）
- 场景 → 出现章节（appearances JSON）
- 人物弧光 → 阶段轨迹（stages JSON）

## AI 辅助生成

三个 LLM 生成端点：
- `POST /storylines/generate-ai` — 基于小说设定自动生成故事线（注入世界观 + 人物）
- `POST /character-arcs/generate-ai` — 基于人物+大纲+世界观+故事线生成弧光（全量上下文）
- `POST /scenes/generate-ai` — 基于世界观生成场景

也可从对话中提取：
- `POST /storylines/from-conversation/{conv_id}`

### 人物弧光生成上下文（CHANGE-026 v2）

弧光生成不再仅基于人物表，而是注入完整小说上下文：
1. 小说类型 + 核心 idea（500 字）
2. 世界观背景 + 世界规则（各 200-300 字）
3. 已有故事线（名称 + 类型 + 描述）
4. 总纲前提 + 主要冲突
5. 全部人物（名称 + 角色 + 描述，最多 10 个）

弧光匹配策略（三级 fallback）：
1. LLM 返回 `character_id` → 直接匹配
2. LLM 返回 `character_name` → 按名称匹配
3. 无匹配 → 按数组顺序对应人物列表

## 图谱可视化

`GET /projects/{id}/relations` 返回完整三元关系数据。

前端使用 D3.js 树形布局渲染：
- 根节点 → 三大分支（故事线/弧光/场景）
- 节点按类型着色（蓝/绿/紫/橙/灰）
- 水平展开，SVG 渲染

## 数据安全（CHANGE-024）

所有写操作均强制 novel_id 隔离，跨小说访问返回 404：

- `update/delete_storyline(sl_id, novel_id)` — novel_id 必填，WHERE 双键
- `update/delete_character_arc(arc_id, novel_id)` — novel_id 必填，WHERE 双键
- `update/delete_scene(scene_id, novel_id)` — novel_id 必填，WHERE 双键
- `add_character_to_storyline(sl_id, char_id, novel_id)` — 插入前校验故事线归属
- `get_relations(novel_id)` — StorylineCharacter 通过 JOIN Storyline 过滤，无全表扫描

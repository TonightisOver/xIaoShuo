# Story Bible（故事圣经）

## 概述

Story Bible 是小说的结构化设定管理系统，存储世界观规则、角色卡、阵营关系、伏笔清单等核心设定，供章节生成时作为硬性约束注入 prompt，防止 AI 违背已建立的世界规则。

## 数据结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `worldview_rules` | text | 世界观规则（不可违反的物理/魔法/社会规则） |
| `character_cards` | JSON list | 角色卡列表（姓名/性格/能力/禁忌行为） |
| `faction_relations` | text | 阵营关系描述 |
| `location_settings` | text | 重要地点设定 |
| `prop_settings` | text | 关键道具/法宝设定 |
| `foreshadowing_list` | JSON list | 伏笔清单（已埋/已回收/待回收） |
| `hard_settings` | text | 硬性设定（绝对不能出现的内容） |

## API 端点

前缀: `/api/v1/projects/{novel_id}/story-bible`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取故事圣经 |
| PUT | `/` | 更新故事圣经（部分更新） |
| POST | `/reset` | 重置为空 |

## 与章节生成的集成

`chapter_generator.py` 在生成每章前，从 story_bible 中提取 `hard_settings` 和 `worldview_rules` 注入 prompt，确保 AI 不违背核心设定。

## 数据库

表名：`story_bibles`，与 `novels` 一对一关联（`novel_id` UNIQUE）。

迁移文件：`alembic/versions/1f4a7c9d2b35_add_story_bibles_table.py`

## 前端入口

`NovelDetail.vue` → "管理小说设定" 按钮 → Story Bible 编辑面板

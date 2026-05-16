# 数据模型设计

## ER 关系图

```
novels (1) ──── (1) world_settings
  │
  ├──── (N) power_systems
  │
  ├──── (N) characters
  │
  ├──── (N) chapters
  │
  └──── (N) tasks
```

## 表结构

### novels（小说项目）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| novel_id | VARCHAR(100) UNIQUE | 业务 ID |
| title | VARCHAR(200) | 标题 |
| idea | TEXT | 创意描述 |
| novel_type | VARCHAR(50) | 类型（玄幻/仙侠/...） |
| target_words | INTEGER | 目标字数 |
| status | VARCHAR(20) | draft/generating/completed/failed |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |

### world_settings（世界观）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | |
| novel_id | FK → novels | 一对一 |
| background | TEXT | 世界背景 |
| geography | TEXT | 地理环境 |
| culture | TEXT | 文化体系 |
| rules | TEXT | 世界规则 |
| extra | JSON | 扩展字段 |

### power_systems（等级体系）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | |
| novel_id | FK → novels | 一对多 |
| name | VARCHAR(100) | 体系名称 |
| description | TEXT | 描述 |
| levels | JSON | 等级列表 [{name, description}] |

### characters（人物）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | |
| novel_id | FK → novels | 一对多 |
| name | VARCHAR(100) | 姓名 |
| role | VARCHAR(50) | 主角/配角/反派/导师 |
| description | TEXT | 描述 |
| personality | TEXT | 性格 |
| abilities | TEXT | 能力 |
| background_story | TEXT | 背景故事 |
| extra | JSON | 扩展 |

### chapters（章节）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | |
| novel_id | FK → novels | 一对多 |
| chapter_number | INTEGER | 章节号 |
| title | VARCHAR(200) | 标题 |
| content | TEXT | 正文 |
| word_count | INTEGER | 字数 |
| status | VARCHAR(20) | draft/generated/edited |

### tasks（生成任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | |
| task_id | VARCHAR(100) UNIQUE | 任务 ID |
| novel_id | FK → novels | 关联小说 |
| status | VARCHAR(20) | pending/running/completed/failed |
| progress | JSON | 进度信息 |
| result | JSON | 完整结果 |
| errors | JSON | 错误列表 |

## 索引

- `novels.novel_id` (UNIQUE)
- `novels.status`
- `tasks.task_id` (UNIQUE)
- `tasks.novel_id`
- `tasks.status`
- `chapters.novel_id`
- `characters.novel_id`
- `power_systems.novel_id`

## 级联删除

删除 novel 时自动删除所有关联的 world_settings、power_systems、characters、chapters。tasks 的 novel_id 设为 NULL（SET NULL）。

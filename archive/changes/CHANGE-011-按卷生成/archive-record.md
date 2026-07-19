# CHANGE-011 归档记录

- 原名称：按卷生成
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-011-按卷生成`
- 归档路径：`archive/changes/CHANGE-011-按卷生成`
- 关联提交：
  - 5cd389b 2026-05-16 feat(CHANGE-011): add volume-based generation

## 目标

为小说平台新增按卷生成功能，支持将小说按卷组织并逐卷生成章节内容。

## 主要设计决定

**变更 ID**: CHANGE-011
**创建时间**: 2026-05-16

## 1. 设计概述

将小说生成从"一次性全量"升级为"分卷渐进"模式。总纲生成时自动划分卷结构，用户可逐卷触发生成，每卷生成时将前面已完成卷的摘要作为上下文注入。

## 2. 系统架构变更

### 2.1 新增数据库表

```sql
CREATE TABLE volumes (
    id SERIAL PRIMARY KEY,
    novel_id VARCHAR(100) REFERENCES novels(novel_id) ON DELETE CASCADE,
    volume_number INTEGER NOT NULL,
    title VARCHAR(200),
    summary TEXT,
    outline JSON,
    status VARCHAR(20) DEFAULT 'draft',
    chapter_start INTEGER,
    chapter_end INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_volumes_novel_id ON volumes(novel_id);

ALTER TABLE chapters ADD COLUMN volume_number INTEGER;
```

### 2.2 工作流改造

**Phase 1: 项目初始化（现有流程保留）**
```
idea_expansion → world_building → character_design
```

**Phase 2: 大纲生成（改造）**

修改 `outline_generation` 节点的 prompt，要求 LLM 输出包含卷划分的结构：
```json
{
  "outline": {"opening": "...", "development": "...", "climax": "...", "ending": "..."},
  "volumes": [
    {
      "volume_number": 1,
      "title": "卷一标题",
      "summary": "本卷概要",
      "chapters": [
        {"chapter": 1, "title": "...", "summary": "..."},
        {"chapter": 2, "title": "...", "summary": "..."}
      ]
    }
  ]
}
```

生成后将 volumes 数据存入 volumes 表。

**Phase 3: 按卷生成（新增）**

新增 `generate_volume` 函数：
1. 读取该卷的 chapter_outlines
2. 读取前面已完成卷的章节摘要作为上下文
3. 调用 chapter_generation 节点生成该卷章节
4. 更新 volume.status = "completed"

### 2.3 API 设计

```
POST /api/v1/projects/{novel_id}/generate          — 全量生成（现有，保留）
POST /api/v1/projects/{novel_id}/generate-volume   — 按卷生成
  Body: {"volume_number": 1}

GET  /api/v1/projects/{novel_id}/volumes           — 列出所有卷
GET  /api/v1/projects/{novel_id}/volumes/{num}     — 卷详情
PUT  /api/v1/projects/{novel_id}/volumes/{num}     — 编辑卷大纲
```

### 2.4 上下文传递策略

生成第 N 卷时，prompt 中注入：
- 总纲摘要
- 前 N-1 卷的每章标题 + 最后一章的结尾

## 涉及模块

- `alembic/versions/2001dedede3d_add_volumes_table.py`
- `alembic/versions/xxx.py`
- `alembic/versions/xxx_add_volumes.py`
- `frontend/src/views/NovelDetail.vue`
- `src/api/models/db_models.py`
- `src/api/routes/projects.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `src/core/langgraph/nodes/outline_generation.py`
- `src/core/langgraph/state.py`
- `src/core/llm/prompts.py`

## 实施结果

为小说平台新增按卷生成功能，支持将小说按卷组织并逐卷生成章节内容。

## 测试与验证

## 构建状态

| 步骤 | 状态 | 耗时 |
|------|------|------|
| 依赖安装 | PASS | - |
| 后端 lint | PASS | - |
| 后端测试 (13 cases) | PASS | ~8s |
| 前端构建 | PASS | - |
| 数据库迁移检查 | PASS | - |

## 测试结果

```
13 passed, 0 failed, 0 skipped
```

## 检查项

- [x] 无新增 lint 警告
- [x] 无类型错误
- [x] 数据库迁移脚本可正向执行
- [x] 前端 build 产物正常
- [x] 无安全漏洞告警

## 结论

CI 全流程通过，构建产物就绪。

## 遗留事项

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 并发生成同一卷 | 低 | 状态字段可防重入 |
| outline JSON 格式不一致 | 低 | prompt 约束 + 解析容错 |

## 原始文件清单

- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`
- `summary.md`

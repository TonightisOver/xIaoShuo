# Gate 2 审批 - CHANGE-043 API压力测试扩展

## 审批时间
2026-05-25

## 变更摘要

### 新增文件（8 个）
- `loadtest/tasks/chapter_edit.py` — 章节编辑保存场景
- `loadtest/tasks/task_management.py` — 任务管理 + 健康检查
- `loadtest/tasks/outline_world.py` — 大纲 + 世界观 + 角色 + 故事圣经 + 故事线
- `loadtest/tasks/knowledge_graph.py` — 知识图谱实体 + 三层 + 可视化 + 三元组
- `loadtest/generate_seed.py` — Seed 数据自动生成脚本
- `loadtest/data/seed.json` — 压测参数数据
- `loadtest/README.md` — 使用文档

### 修改文件（5 个）
- `loadtest/config.py` — 重构配置，支持缺失 seed 容错
- `loadtest/locustfile.py` — 三种用户画像 (Reader/Writer/Admin)
- `loadtest/tasks/__init__.py` — 导出全部 8 个 TaskSet
- `loadtest/tasks/chapter_read.py` — 新增版本历史场景
- `loadtest/tasks/chapter_list.py` — 新增卷列表 + 小说列表
- `loadtest/tasks/chapter_generate.py` — 修正请求字段名
- `loadtest/tasks/ai_rewrite.py` — 清理 sys.path hack
- `loadtest/.gitignore` — 忽略报告和缓存

### 附带 Bug 修复（后端）
- `src/api/routes/projects.py` — 修复 `list_tasks()` 返回值解构错误 + 超时任务清理

## 验证结果
- 全部 12 个 Python 文件语法验证通过
- 后端修复文件语法验证通过
- 压测覆盖 21 个 API 场景

## 待审批
- [ ] 确认交付

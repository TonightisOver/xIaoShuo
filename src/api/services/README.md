# API 服务层

`src/api/services` 保存 API 层复用的业务服务。新增模块应按职责进入已有子包，只有明确跨越多个领域或完全独立的服务才保留在根目录。

## 子包职责

- `generation/`：小说与章节生成编排、进度、暂停状态和落库辅助。
- `content/`：小说、章节、人物、世界观、卷、大纲、故事线等内容管理。
- `quality/`：质量动作、报告、检测、上下文和改写闭环。
- `knowledge/`：知识图谱、提示词和相似度工具。
- `tasks/`：持久化任务队列管理、白名单调度和 worker。

## 根目录模块

- `agent_journal_service.py`：智能体日志。
- `book_import_service.py`：书籍导入。
- `export_service.py`：内容导出。
- `reader_simulation_service.py`：读者模拟。

目录调整只表达职责归属。不要借移动文件修改业务流程；跨包依赖应使用完整绝对导入路径。

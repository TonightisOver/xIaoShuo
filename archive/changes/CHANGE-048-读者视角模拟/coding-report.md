# CHANGE-048 编码报告

## 变更摘要

实现读者视角模拟功能，通过 LLM 扮演4种读者人设对章节内容进行角色化评价，输出结构化反馈。

## 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/api/services/reader_simulation_service.py` | ~270 | 模拟服务核心（人设定义+并行LLM调用+结果存储） |
| `src/api/routes/reader_simulation.py` | ~80 | 4个REST API端点 |
| `frontend/src/components/ReaderSimPanel.vue` | ~160 | 读者模拟面板组件 |
| `tests/unit/test_reader_simulation_service.py` | ~210 | 8个单元测试 |

## 修改文件

| 文件 | 说明 |
|------|------|
| `src/api/models/db_models.py` | 新增 ReaderSimulation 模型 |
| `src/api/routes/__init__.py` | 注册 reader_simulation_router |
| `src/api/main.py` | 挂载 reader_simulation_router |
| `frontend/src/views/ChapterEdit.vue` | 添加"读者模拟"按钮 + 引入 ReaderSimPanel |

## 功能实现

### 4种读者人设
- 核心粉丝(hardcore_fan): 关注人物OOC、伏笔回收、情感共鸣
- 路人读者(casual_reader): 关注开头吸引力、节奏紧凑度、追更欲
- 专业评论家(critic): 关注叙事技巧、文笔质量、主题深度
- 网文老白(veteran_reader): 关注套路新鲜度、爽点密度、金手指合理性

### 模拟执行
- BackgroundTasks 异步执行，前端轮询获取结果
- asyncio.gather 并行调用4个人设的LLM
- 单个人设失败不影响整体，标记为 error
- 章节过长时截取前8000字+后2000字

### 结构化输出
- engagement_score (0-1)
- would_continue_reading (bool)
- emotional_response, pacing_assessment, character_consistency
- satisfaction_points, pain_points (列表)
- overall_comment (读者口吻总评)

### 前端交互
- 人设选择 checkbox（默认全选）
- 模拟中 loading 动画
- 结果卡片：评分、标签、亮点/不足、总评
- 历史记录折叠区域

## 验证
- ruff check: 通过
- pytest: 8/8 通过
- vite build: 成功
- 全量测试: 38/38 通过

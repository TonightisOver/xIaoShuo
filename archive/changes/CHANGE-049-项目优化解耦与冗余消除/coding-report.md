# 编码报告：全局架构优化 — 模块解耦与冗余消除

## 变更概述

完成 9 个重构任务，消除了 core 层对 api/services 层的反向依赖，提取了 3 个公共模块，拆分了过大的 service 文件。

## 变更文件清单

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| src/core/context/__init__.py | 新增 | 上下文构建模块包 |
| src/core/context/novel_context.py | 新增 | NovelContextBuilder — 统一上下文构建 |
| src/core/quality/__init__.py | 新增 | 质量评估模块包 |
| src/core/quality/evaluator.py | 新增 | 统一质量评估函数 + EVALUATION_PROMPT |
| src/core/llm/helpers.py | 新增 | generate_and_parse_json 辅助函数 |
| src/api/services/ai_generation_service.py | 新增 | AI 生成逻辑（从 storyline_service 分离） |
| src/api/services/chapter_persistence_service.py | 新增 | 章节持久化逻辑（从 novel_generator 分离） |
| src/api/services/long_form_generation_helpers.py | 新增 | 长篇生成辅助函数（从 novel_generator 分离） |
| src/core/llm/chapter_generator.py | 修改 | 去除所有 DB 依赖，参数化上下文 |
| src/core/llm/chapter_rewriter.py | 修改 | 去除所有 DB 依赖，接收 context 参数 |
| src/core/langgraph/nodes/chapter_generation.py | 修改 | 改为 config 注入依赖 |
| src/core/langgraph/nodes/quality_check.py | 修改 | 改为 config 注入依赖 |
| src/api/services/novel_generator.py | 修改 | 拆分职责，从 1627 行降至 ~1012 行 |
| src/api/services/storyline_service.py | 修改 | 只保留 CRUD，AI 逻辑移出 |
| src/api/services/blueprint_service.py | 修改 | 使用 NovelContextBuilder + generate_and_parse_json |
| src/api/services/outline_service.py | 修改 | 使用 generate_and_parse_json |
| src/api/services/rewrite_loop_service.py | 修改 | 使用公共质量评估模块 |
| src/api/routes/storylines.py | 修改 | 更新 import 指向 ai_generation_service |
| src/api/routes/projects.py | 修改 | 调用前构建 rewrite context |
| src/core/llm/__init__.py | 修改 | 导出 generate_and_parse_json |

## 实现说明

### Phase 1: 提取公共模块（P0）
- **NovelContextBuilder**: 统一了 5 处重复的上下文构建逻辑，返回类型化 dataclass
- **evaluate_chapter_quality**: 统一了 2 处重复的质量评估 Prompt 和解析逻辑
- **generate_and_parse_json**: 统一了 12 处重复的 LLM 调用 + JSON 解析模式

### Phase 2: 消除反向依赖（P1）
- **chapter_generator**: 新增 story_bible_context 参数，删除所有 DB import
- **LangGraph 节点**: 改为 LangGraph config["configurable"] 注入依赖
- **novel_generator 拆分**: 持久化逻辑 → chapter_persistence_service，长篇生成 → long_form_generation_helpers

### Phase 3: 职责边界重划（P2）
- **storyline_service**: AI 生成方法移至 ai_generation_service，只保留 CRUD
- **chapter_rewriter**: 接收 context 参数，不再自行查询 DB
- **章节生成循环**: 统一为 _generate_chapters_batch 函数

## 验证结果
- 361 个单元测试全部通过
- ruff 无新增 error（E501 为预先存在的 prompt 长行）
- core/llm 和 core/langgraph/nodes 中无 `from src.api.services` import
- core/context 仅依赖 db_models（数据模型定义），不依赖 service 逻辑

## 架构改善指标
- novel_generator.py: 1627 行 → 1012 行（-38%）
- core 层反向依赖: 6 处 → 0 处（core/llm, core/langgraph/nodes）
- 重复代码消除: ~390 行重复逻辑提取为公共模块
- 新增公共模块: 3 个（context, quality, llm/helpers）

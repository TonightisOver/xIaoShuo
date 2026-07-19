# CHANGE-044 归档记录

- 原名称：百万字长篇生成验证
- 状态：completed
- 时间范围：2026-05-25
- 原路径：`.harness/changes/CHANGE-044-百万字长篇生成验证`
- 归档路径：`archive/changes/CHANGE-044-百万字长篇生成验证`
- 关联提交：
  - 407a032 2026-05-25 feat: add million-word long-form novel generation support (CHANGE-044)

## 目标

当前系统已完成基础功能开发与 API 压力测试，具备中篇（约20万字）小说的完整生成能力。本需求要求将生成规模从中篇升级为百万字级别长篇网文，验证系统在大规模连续生成场景下的各子系统（StoryBible、知识图谱、人物弧光、伏笔管理、质量评分、章节版本系统）是否能长期维持一致性，并具备识别和处理常见长篇问题（无效注水、人物漂移、设定冲突、主线停滞）的能力。

核心目标不是生成质量本身，而是 **系统在百万字规模下的工程健壮性和一致性维护能力**。

## 主要设计决定

1. **StoryBible 约束系统** -- 精准抽取、反向更新、冲突检测已实现，可直接复用
2. **知识图谱** -- 实体/三元组抽取、一致性检查已实现，但需要针对大规模优化（实体数量会指数增长）
3. **质量评分** -- 8维度评分已实现，但缺少跨章节趋势分析
4. **章节版本系统** -- 多版本管理已实现，支持重写和回滚
5. **按卷生成** -- `generate_volume_background` 已实现按卷生成流程

## 涉及模块

- `src/api/models/db_models.py`
- `src/api/models/requests.py`
- `src/api/models/responses.py`
- `src/api/routes/novels.py`
- `src/api/schemas/novel.py`
- `src/api/services/filler_detection_service.py`
- `src/api/services/foreshadow_tracker_service.py`
- `src/api/services/long_form_progress_service.py`
- `src/api/services/novel_generator.py`
- `src/api/services/quality_report_service.py`
- `src/core/langgraph/graph.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `src/core/langgraph/nodes/outline_generation.py`
- `src/core/langgraph/state.py`
- `src/core/llm/chapter_generator.py`
- `src/core/llm/prompts.py`
- `tests/integration/`
- `tests/integration/test_change044_long_form_api.py`
- `tests/unit/`
- `tests/unit/test_change044_long_form_services.py`

## 实施结果

**日期**: 2026-05-25
**版本**: v1
当前系统已完成基础功能开发与 API 压力测试，具备中篇（约20万字）小说的完整生成能力。本需求要求将生成规模从中篇升级为百万字级别长篇网文，验证系统在大规模连续生成场景下的各子系统（StoryBible、知识图谱、人物弧光、伏笔管理、质量评分、章节版本系统）是否能长期维持一致性，并具备识别和处理常见长篇问题（无效注水、人物漂移、设定冲突、主线停滞）的能力。
核心目标不是生成质量本身，而是 **系统在百万字规模下的工程健壮性和一致性维护能力**。
- 支持单章 2000~4000 字、默认 3000 字左右的章节长度控制
- 当前系统 `max_tokens=8000` 无字数约束，LLM 输出长度波动大
- 需要通过 prompt 指令 + 后置截断/续写确保字数稳定
- 支持 8~12 卷、250~400 章的结构
- 当前 `outline_generation` 节点通过单次 LLM 调用生成大纲，百万字规模下单次调用难以产出完整大纲
- 需要分卷规划、逐步细化的两级大纲生成策略
- 区分主线推进章、高潮章、余波章、日常章、铺垫章等章节功能类型
- 每章大纲需包含 `chapter_type` 字段，不同类型对应不同的生成策略和质量评估权重

## 测试与验证

- 通过: 50 / 失败: 0 / 跳过: 0
- 覆盖率: 97%

## 遗留事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 单次生成大纲质量不足 | 300+ 章大纲需要分卷细化，跨卷一致性难以保证 | 分级大纲策略：总纲 -> 卷纲 -> 章纲，每级注入上级约束 |
| 百万字生成时间过长 | DeepSeek API 限流/超时，300+ 章可能需要数小时 | 按卷断点生成，单卷失败不影响全量，支持重试 |
| 知识图谱实体爆炸 | 百万字产生数千实体/三元组，查询性能下降 | 实体去重合并、按卷裁剪历史上下文、设置 KG 上下文长度上限 |
| 内存压力 | NovelState 中 chapters 列表存储所有章节内容 | 按卷批量生成，每卷完成后持久化清空内存，仅保留摘要 |
| 字数控制与文笔平衡 | 强制字数限制可能影响生成质量 | prompt 引导为主，后置截断为辅，允许 20% 浮动 |
| 伏笔遗忘累积 | 10章阈值在300+章中过于宽松 | 根据卷长度动态调整阈值，卷末强制检查所有悬挂伏笔 |

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

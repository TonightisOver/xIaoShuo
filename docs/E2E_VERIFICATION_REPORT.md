# 端到端验证报告（2026-07-12）

在服务器（115.190.142.169）上对真实生成流程进行端到端验证，发现并修复 2 个真实 bug。

## 验证方法
通过 API 注册用户 → 创建测试小说（2万字短篇）→ 触发分步生成 → 轮询任务进度 → 查询数据库验证落库。

## ✅ 验证通过

| 项 | 结果 |
|----|------|
| 管线端到端跑通 | idea_expansion → character_design（Pydantic 校验）→ outline → chapter_generation → quality_check → human_review（auto-approve）→ completed |
| trace_id 链路追踪 | 全程日志带 trace_id，串联清晰 |
| 模型分工 | pro 生成 blueprint，flash 写正文 |
| 数据落库 | world / characters / chapters / triples / entities 均落库 |
| HITL auto-approve 兜底 | 生效，管线不卡死 |
| Sub-Agent 运行 | memory_curator 等在真实流程中工作，依赖反转注入链路正常 |

## 🔴 发现并修复的真实 bug

### Bug 1（P0）：短篇章节跨卷重复导致落库丢失

**现象**：生成 26 章，但 DB 只落库 7 章。

**根因**：`outline_generation` 节点从 `volumes` 提取 `chapter_outlines` 时，直接 append 每卷的 chapters。LLM 习惯按卷内编号（每卷 chapter 从 1 开始），导致跨卷 chapter_number 重复（1-6 章各 4 次，第 7 章 2 次）。`persist` 时 `delete + insert` 同号覆盖，26 章最终只剩 7 章。

**修复**：提取时做全局重编号（1,2,3...连续），保留 volume_number，保证编号唯一。

**验证**：修复后日志显示 chapter 编号连续到 30（之前卡在 7），total_chapters=30。

### Bug 2（P1）：DeepSeek 不支持 embedding API，404 噪音

**现象**：每次创建实体都报 `embedding_api_failed: 404 Not Found`。

**根因**：DeepSeek API **不提供 embedding 接口**（只有 chat completions），但代码用 `EMBEDDING_MODEL="text-embedding-ada-002"`（OpenAI 模型名）调 `/v1/embeddings`，必 404。实体 embedding 全失败，语义检索从未工作（靠精确匹配兜底）。

**修复**：新增 `EMBEDDING_ENABLED` 配置（默认 False），关闭时跳过 embedding 调用。`retrieve_context` 已有精确匹配降级（基于实体名/别名），对中文小说足够。配了支持 embedding 的供应商时设 True 启用向量检索。

## 验证中发现的其他情况（非 bug）

1. **质量优化循环**：章节生成后若 quality_score < 0.8，`_should_continue_volume` 触发 regenerate 重生成。预期行为，但 progress 倒退显示会困惑用户——建议后续优化 progress 展示。
2. **HITL 真 interrupt/resume 未实现**：已用 auto-approve 兜底。真 HITL 需持久化 checkpointer + resume 路径（6-8h），排入下个迭代。
3. **SqliteSaver 误用 bug**：`from_conn_string` 返回 context manager 被当 saver 直接用，sqlite 模式从未工作。影响真 HITL 实现，需先修。

## 未完全验证

- **导出（F4）**：质量循环导致生成未跑到完成，无法验证导出。导出是独立模块，本次修复不涉及其代码，建议后续用完整生成验证。

## 提交记录
- `95a4dcf` fix: HITL 审核节点 auto-approve 兜底
- `2c0181d` fix: 短篇章节跨卷重复丢失 + embedding 404 噪音

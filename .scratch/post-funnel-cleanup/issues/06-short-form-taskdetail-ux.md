# 06 — 短篇流程页体验优化

**What to build:** 短篇 TaskDetail 流程页（`/task/:id`）现在是基础版——有 StageIndicator + ProgressBar + 流式文本 + 事件日志。补上：阶段说明（每个阶段在做什么）、失败重试按钮、完成后直接预览第一章。

**Blocked by:** None — 可立即开始

**Status:** ready-for-agent

- [ ] 阶段说明：StageIndicator 每个阶段旁加一行描述（"正在展开创意..."、"正在设计世界观..."）
- [ ] 失败重试：generation 节点失败时不直接标记 failed，给用户"重试本章"按钮
- [ ] 完成后一键跳转：生成完成 → "查看小说详情"按钮跳 NovelDetail
- [ ] 流式文本区加字数统计（实时显示已生成字数）
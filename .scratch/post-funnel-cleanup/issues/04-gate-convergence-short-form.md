# 04 — 质量门禁收敛：短篇 quality_check 节点接 gate

**What to build:** `run_quality_gate` 是深模块（L0→L3+state_delta+重写），但短篇 LangGraph 的 `quality_check` 节点自己重写了半个 gate（consistency_blocked 独立实现），手动按范围路径已通过重构接入 gate。让短篇 quality_check 节点也走 `run_quality_gate`，消灭最后一个浅复制品。

**Blocked by:** 03（Context 对象收窄后，gate 调用方接口统一）

**Status:** ready-for-agent

- [ ] `langgraph/nodes/quality_check.py` 的 `evaluate_chapter_quality` 改为调 `run_quality_gate`
- [ ] 去掉 short-form 里独立实现的 `consistency_blocked`（gate 自带 CONSISTENCY_BLOCK_THRESHOLD）
- [ ] 确保短篇章节也抽取 state_delta（目前短篇可能没有）
- [ ] 测试：LangGraph 质量节点相关测试全部通过

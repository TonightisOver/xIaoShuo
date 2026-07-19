# CHANGE-005 归档记录

- 原名称：websocket实时进度
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-005-websocket实时进度`
- 归档路径：`archive/changes/CHANGE-005-websocket实时进度`
- 关联提交：
  - 37e475f 2026-05-16 docs: complete 10-stage harness documentation for CHANGE-003~008
  - f950c4e 2026-05-16 docs: add CHANGE-003 to CHANGE-008 harness documentation

## 目标

实现 WebSocket 实时进度推送，让前端能即时展示小说生成的每个阶段完成状态和逐章进度，替代轮询方式。

---

## 主要设计决定

- 进程内 pub/sub（asyncio.Queue，每个订阅者独立队列）
- WebSocket 端点 `/ws/tasks/{task_id}`
- 30 秒心跳保活
- LangGraph `astream` 获取节点中间输出
- 回调注册表实现逐章进度推送

---

## 涉及模块

- `src/api/main.py`
- `src/api/routes/__init__.py`
- `src/api/routes/ws.py`
- `src/api/services/novel_generator.py`
- `src/api/services/progress_event_bus.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `tests/api/test_websocket.py`

## 实施结果

**变更 ID**: CHANGE-005
**创建时间**: 2026-05-16
**完成时间**: 2026-05-16
**状态**: ✅ 已完成

---

## 需求概述

实现 WebSocket 实时进度推送，让前端能即时展示小说生成的每个阶段完成状态和逐章进度，替代轮询方式。

---

## 技术方案

- 进程内 pub/sub（asyncio.Queue，每个订阅者独立队列）
- WebSocket 端点 `/ws/tasks/{task_id}`
- 30 秒心跳保活
- LangGraph `astream` 获取节点中间输出
- 回调注册表实现逐章进度推送

---

## 核心变更

### 新增文件

- `src/api/services/progress_event_bus.py` — ProgressEventBus（subscribe/publish/unsubscribe）+ 回调注册表
- `src/api/routes/ws.py` — WebSocket 端点（连接验证、事件转发、心跳、断开清理）
- `tests/api/test_websocket.py` — 4 个 WebSocket 测试

### 修改文件

- `src/api/services/novel_generator.py` — ainvoke → astream，每节点发布事件
- `src/core/langgraph/nodes/chapter_generation.py` — 逐章回调
- `src/api/routes/__init__.py` — 注册 ws_router
- `src/api/main.py` — 注册 ws_router

---

## 消息格式

```json
{
  "type": "stage_complete | chapter_progress | completed | error | heartbeat",
  "task_id": "novel-...",
  "data": {"stage": "...", "percentage": 42},
  "timestamp": "2026-05-16T..."
}
```

---

## 质量指标

- **事件类型**: 5 种（stage_start/stage_complete/chapter_progress/error/completed）
- **测试用例**: 4 个新增，总计 13 个全部通过
- **心跳**: 30 秒间隔
- **内存安全**: QueueFull 时丢弃事件，断开时自动清理

---

## 10 阶段完成情况

1. ✅ 需求分析 — 实时推送需求
2. ✅ 技术设计 — 进程内 pub/sub + WebSocket
3. ✅ 编码计划 — 3 个新文件 + 4 个修改
4. ✅ 编码实现 — 完成
5. ✅ 代码检查 — 通过
6. ✅ 专家评审 — 设计合理
7. ✅ 单元测试 — 事件总线 publish/subscribe/unsubscribe
8. ✅ 集成测试 — WebSocket 连接 + 事件接收
9. ✅ CI 验证 — 13 个测试通过
10. ✅ 部署验证 — WebSocket 连接正常

## 测试与验证

全部通过

## 遗留事项

- 低风险：当前为单实例部署，pub/sub 方案完全满足需求
- 无破坏性变更：REST API 行为不受影响

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

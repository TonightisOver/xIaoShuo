# 变更总结: 数据隔离收口与跨小说负例测试

**变更 ID**: CHANGE-024  
**创建时间**: 2026-05-17  
**状态**: 已完成

---

## 需求概述

统一收口对话和故事线模块的 novel_id 隔离逻辑，消除所有跨小说读写漏洞，并补充跨小说负例集成测试。

---

## 技术方案

在 service 层强制 novel_id 参数（非可选），在 route 层统一传递，confirm_message 同时校验 msg_id + conv_id + novel_id 三元组，add_character_to_storyline 校验故事线归属，补充 3 类跨小说负例测试。

---

## 核心变更

### 修改文件
- `src/api/services/conversation_service.py` - get_conversation/send_message/conclude_conversation 加 novel_id 校验；confirm_message 三元组校验
- `src/api/routes/conversations.py` - 所有 conv 路由传 novel_id 给 service
- `src/api/services/storyline_service.py` - update/delete arc/scene novel_id 改为必填；add_character_to_storyline 校验归属；get_relations 改为 DB 过滤
- `src/api/routes/storylines.py` - update/delete arc/scene 路由传 novel_id

### 新增文件
- `tests/api/test_cross_novel_isolation.py` - 跨小说负例测试（arc/scene/confirm_message）

---

## 质量指标

- **单元测试覆盖率**: 59 passed（+3 新增）
- **集成测试**: 通过
- **CI 验证**: 通过
- **代码检查**: ruff (通过), mypy (0 新增 errors)

---

**更新时间**: 2026-05-17

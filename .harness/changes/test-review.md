# CHANGE-051 测试评审报告

**日期**: 2026-05-27  
**评审者**: Reviewer Agent  
**评审类型**: test_review  
**轮次**: 第 1 轮

---

## 评审范围

| 文件 | 测试数 |
|------|--------|
| tests/unit/test_llm/test_token_tracker.py | 11 |
| tests/unit/test_llm/test_client.py（重点：TestLLMClientDualModel + TestLLMClientTokenTracking） | 21 |
| tests/unit/test_llm/test_client_db_config.py | 4 |
| tests/api/routes/test_llm_config.py | 11 |
| **合计** | **47** |

---

## 维度评审

### 1. 覆盖率

**test_token_tracker.py**

覆盖了 TokenTracker 的全部公开接口：`record()`、`skip()`、`get_stats()`、`get_token_tracker()` 单例工厂。
初始状态、单次记录、多次累加、按模型分组、recent_records 截断（50 条）、deque maxlen（1000 条）、records_skipped 字段均有对应测试。覆盖完整。

**test_client.py — TestLLMClientDualModel**

三个测试分别覆盖 `use_flash=True`、`use_flash=False`、默认不传三种路径，并通过 `assert_called_once()` / `assert_not_called()` 验证了互斥性。覆盖完整。

**test_client.py — TestLLMClientTokenTracking**

覆盖了四条分支：
- `response_metadata` 含完整 `token_usage` → `tracker.record()` 被调用
- `response_metadata` 为空 dict → `tracker.skip()` 被调用
- `token_usage` 存在但缺少 `prompt_tokens` → `tracker.skip()` 被调用
- `use_flash=True` 时 tracker 记录的 model 名为 flash 模型名

对照实现代码（client.py 第 148-161 行），这四条分支与实际条件判断完全对应。覆盖完整。

**test_client_db_config.py**

覆盖了 `llm_config` 参数的三种传入方式（有效对象、不传、显式 None）以及 DB 配置下 tracker 记录正确模型名。覆盖完整。

**test_llm_config.py**

覆盖了 CRUD 全路径（list、create、update、activate、delete）及其错误分支（404、400），以及 api_key 脱敏验证和 token-stats 结构验证。覆盖完整。

### 2. 边界场景

- `test_maxlen_1000_drops_old_records`：写入 1100 条，验证 deque 截断行为。
- `test_recent_records_limit_50`：写入 60 条，验证 recent_records 截断。
- `test_token_skip_called_when_token_usage_missing_prompt_tokens`：token_usage 部分缺字段的降级路径。
- `test_delete_active_config_rejected`：业务约束边界（不能删除激活配置）。
- `test_activate_config`：激活互斥性（激活 B 后 A 自动变为非激活）。
- `test_update_config_not_found` / `test_activate_config_not_found` / `test_delete_config_not_found`：404 路径均有覆盖。

边界场景覆盖充分。

### 3. 测试质量

**断言有效性**

- TokenTracker 测试：断言具体数值（total_calls、records_skipped、token 累加值），不是仅检查类型或非空。
- DualModel 测试：同时断言返回值内容和 mock 调用次数，避免了"调用了但结果错误"的漏洞。
- TokenTracking 测试：通过重置全局单例（`tt_module._tracker = None`）后再读取，确保断言的是本次调用产生的状态，而非残留状态。
- DB 配置测试：验证 `call_args_list` 中的具体参数值（api_key、base_url、model 名），断言精确。

**一个 SHOULD FIX 项**

`test_create_config`（test_llm_config.py 第 46-66 行）末尾有 `return data["id"]`，但该函数是一个 pytest 测试函数，返回值不会被任何地方使用。这是无效代码，可能是从辅助函数重构时遗留的。不影响测试结果，但会造成阅读困惑。

建议删除该 `return` 语句。

### 4. 独立性

- 每个 unit test 类通过 `setup_method` 或直接实例化创建独立对象，不共享状态。
- TokenTracking 测试在每个测试开始时重置全局单例（`tt_module._tracker = None`），避免跨测试污染。
- API 路由测试使用 `scope="module"` 的 `_db_setup` fixture，在模块级别创建/销毁数据库表，各测试共享同一数据库实例。

**潜在隐患（SHOULD FIX）**

`test_llm_config.py` 中多个测试向同一数据库写入数据，且没有在每个测试后清理。例如 `test_list_configs_empty` 假设数据库为空，但如果测试执行顺序改变（pytest 不保证顺序），其他测试先写入数据后，该测试可能失败。

当前测试通过，说明 pytest 默认按文件顺序执行且 `test_list_configs_empty` 排在最前。但这是一个脆弱性，建议为每个测试添加独立的数据清理，或使用 `scope="function"` 的 fixture 重建数据库。

### 5. 可维护性

- 测试数据使用有意义的字符串（`"deepseek-v4-flash"`、`"custom-flash"`），而非无意义占位符。
- `_make_mock_llm_config()` 工厂函数集中管理测试数据，便于维护。
- 测试类按功能分组（TestLLMClientDualModel、TestLLMClientTokenTracking、TestLLMClientDbConfig），结构清晰。
- 每个测试有中文 docstring 说明意图，可读性好。

---

## 问题汇总

| 级别 | 位置 | 描述 |
|------|------|------|
| SHOULD FIX | test_llm_config.py:66 | `test_create_config` 末尾的 `return data["id"]` 是无效代码，建议删除 |
| SHOULD FIX | test_llm_config.py | 路由测试共享数据库状态，`test_list_configs_empty` 依赖执行顺序，存在脆弱性 |

无 MUST FIX 项。

---

## 结论

**APPROVED**

47 个测试全部通过，覆盖了 CHANGE-051 引入的双模型路由、token 追踪、DB 配置初始化和 LLM 配置 CRUD 的核心业务路径及主要边界场景。断言有效，测试结构清晰，与实现代码逻辑对应准确。两个 SHOULD FIX 项不阻塞流程，可在后续迭代中改善。

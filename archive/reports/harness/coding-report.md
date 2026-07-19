# CHANGE-053 编码报告

**日期**: 2026-05-28  
**执行者**: Coder Agent

---

## 完成任务清单

| 任务 | 文件 | 状态 |
|------|------|------|
| T1 | src/api/services/novel_generator.py | 完成 |
| T2 | src/api/services/long_form_generation_helpers.py + novel_generator.py | 完成 |
| T3 | src/api/services/novel_generator.py | 完成 |
| T4 | src/api/services/outline_service.py | 完成 |

---

## 关键实现说明

### T1 — auto_calc_chapters 计算前移（novel_generator.py）

`chapters_per_vol` 计算块（含 `total_volumes`、`words_per_chapter` 赋值）整体移至函数入口处，在 `initialize_progress` 和 `update_novel` 之前执行。两处调用的 `chapters_per_volume` 参数均改为 `chapters_per_vol`，确保元数据存储的是实际使用值。

### T2 — generate_master_outline 新增 chapters_per_vol 参数

`long_form_generation_helpers.py` 中函数签名新增 `chapters_per_vol: int`，内部所有 `request.chapters_per_volume` 引用（prompt format + fallback 数据 5 处）替换为 `chapters_per_vol`。`novel_generator.py` 调用方传入 `chapters_per_vol=chapters_per_vol`。

### T3 — 卷大纲持久化（novel_generator.py）

在 `generate_volume_outline` 调用后、`generate_volume_chapters` 调用前插入持久化逻辑：
- `outline_service.upsert_volume_outline(novel_id, vol_num, vol_outline)` 保存卷大纲
- 遍历 `vol_outline.get("chapters", [])` 逐章调用 `upsert_chapter_outline`，章节编号使用 `ch.get("chapter", idx + 1)` fallback
- 整体用 try/except 包裹，失败记录 warning 不中断主流程
- 通过延迟导入 `get_outline_service()` 获取实例，与项目其他地方模式一致

### T4 — outline_service.py max_tokens 提升

`generate_chapter_outlines` 第 234 行：`max_tokens=4000` → `max_tokens=12000`，满足 40 章大纲 JSON 的生成需求。


---

## 测试文件

| 任务 | 测试文件 | 结果 |
|------|---------|------|
| T1 | tests/unit/test_llm/test_token_tracker.py（新建） | 11/11 通过 |
| T3 | tests/unit/test_llm/test_client.py（更新） | 14/14 通过 |
| T8 | tests/unit/test_llm/test_client_db_config.py（新建） | 4/4 通过 |
| T6 | tests/api/routes/test_llm_config.py（新建） | 待集成测试 |

---

## 关键实现说明

### 层级边界合规
LLMClient.__init__ 接受 llm_config: Any | None = None（duck-typed），不导入 src.api.models.db_models，
完全符合 CHANGE-050 的 core->api 反向依赖禁止规则。

### T1 — TokenTracker
- deque(maxlen=1000) 自动丢弃旧记录
- records_skipped 计数器记录无 token 信息的调用
- get_stats() 返回完整统计，含 by_model 分组和最近 50 条记录
- 使用 datetime.now(UTC) 替代已废弃的 utcnow()

### T2 — Settings
- 新增 DEEPSEEK_MODEL_FLASH = "deepseek-v4-flash" 和 DEEPSEEK_MODEL_PRO = "deepseek-v4-pro"
- 保留原 DEEPSEEK_MODEL 字段不变

### T3 — LLMClient
- 创建 self.llm_flash 和 self.llm_pro 两个 ChatOpenAI 实例
- 保留 self.llm = self.llm_pro 向后兼容直接访问该属性的代码
- generate() 新增 use_flash: bool = False 参数
- token 追踪：有 token_usage 则 record()，无则 skip()

### T4 — chapter_generator.py
- 步骤 3（规划）：generate(planning_prompt, max_tokens=3000) — 默认 pro
- 步骤 5（正文）：generate(prompt, max_tokens=8000, use_flash=True)
- _continuation_generation：generate(continuation_prompt, max_tokens=4000, use_flash=True)

### T5 — LLMConfig 模型
- 表名 llm_configs，is_active 加索引
- 通过 init_db() 的 create_all 自动建表

### T6 — llm_config 路由
- 完整 CRUD + activate + token-stats
- api_key 脱敏："****" + api_key[-4:]
- 激活操作在同一事务内先全部置 False 再激活目标
- 删除激活配置返回 400

### T8 — lifespan 单例初始化
- await init_db() 后查询激活的 LLMConfig
- 有激活配置则 LLMClient(llm_config=active_config)，否则 LLMClient()
- 异常时回退到 Settings 配置，不阻断启动

### T9 — LLMSettings.vue
- 配置列表 + 新增/编辑弹窗 + 激活/删除操作
- Token 统计面板（汇总卡片 + 按模型分组表格）
- 使用原生 fetch，与 Home.vue 风格一致

### T10 — 前端路由和导航
- 路由：{ path: "/settings/llm", name: "LLMSettings", component: LLMSettings }
- 导航：在任务大厅和开启创作之间插入模型配置链接

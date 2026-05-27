# CHANGE-051 任务清单

> 对应需求：`.harness/requirements.md` CHANGE-051  
> 日期：2026-05-27

---

## 任务分组

### 组 A — 后端核心（无前端依赖）

#### T1: 新增 TokenTracker 模块
**文件**: `src/core/llm/token_tracker.py`（新建）  
**描述**: 实现内存聚合器，记录每次 LLM 调用的 token 用量。  
**实现要点**:
- `TokenRecord` dataclass：`timestamp`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`
- `TokenTracker` 类（单例）：`record(...)` 方法追加记录，最多保留 1000 条（`collections.deque(maxlen=1000)`）；维护 `records_skipped: int` 计数器，每次因缺少 token 字段而跳过记录时加 1
- `get_stats()` 方法：返回总调用次数、累计三类 token、按模型分组统计、最近 50 条记录列表、`records_skipped` 跳过次数
- `get_token_tracker()` 工厂函数返回全局单例

**验收标准**:
- `pytest tests/unit/test_llm/test_token_tracker.py` 全部通过
- 超过 1000 条时旧记录被自动丢弃
- `get_stats()` 返回值包含 `records_skipped` 字段

**依赖**: 无

---

#### T2: 扩展 Settings — 双模型字段
**文件**: `src/core/config.py`  
**描述**: 新增 `DEEPSEEK_MODEL_FLASH` 和 `DEEPSEEK_MODEL_PRO` 字段。  
**实现要点**:
- 在 `Settings` 类中新增：
  ```python
  DEEPSEEK_MODEL_FLASH: str = "deepseek-v4-flash"
  DEEPSEEK_MODEL_PRO: str = "deepseek-v4-pro"
  ```
- 保留现有 `DEEPSEEK_MODEL` 字段不变（向后兼容）；`DEEPSEEK_MODEL_FLASH` 和 `DEEPSEEK_MODEL_PRO` 是独立的新增字段，与 `DEEPSEEK_MODEL` 并列，不存在别名或继承关系

**验收标准**:
- `python -c "from src.core.config import get_settings; s = get_settings(); assert s.DEEPSEEK_MODEL_FLASH == 'deepseek-v4-flash'"` 执行成功
- `python -c "from src.core.config import get_settings; s = get_settings(); assert s.DEEPSEEK_MODEL_PRO == 'deepseek-v4-pro'"` 执行成功
- `python -c "from src.core.config import get_settings; s = get_settings(); assert hasattr(s, 'DEEPSEEK_MODEL')"` 执行成功（原字段仍存在）

**依赖**: 无

---

#### T3: 升级 LLMClient — 双模型 + Token 监控
**文件**: `src/core/llm/client.py`  
**描述**: 在 `LLMClient` 中集成双模型实例和 token 记录。  
**实现要点**:
- `__init__` 中创建 `self.llm_flash`（使用 `settings.DEEPSEEK_MODEL_FLASH`）和 `self.llm_pro`（使用 `settings.DEEPSEEK_MODEL_PRO`）
- `generate()` 签名新增 `use_flash: bool = False`，根据参数选择对应实例
- 调用成功后，从 `response.response_metadata.get("token_usage", {})` 提取 token 数据，调用 `get_token_tracker().record(...)`；若字段不存在则静默跳过并将 `TokenTracker.records_skipped` 加 1
- token 记录中的 `model` 字段取实际使用的模型名

**验收标准**:
- `pytest tests/unit/test_llm/test_client.py` 全部通过
- 调用 `generate(prompt, use_flash=True)` 后，`get_token_tracker().get_stats()["total_calls"]` 增加 1
- 使用带有 `response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}` 的 mock 响应，验证 token 数据被正确提取并记录
- 使用不含 `response_metadata` 的 mock 响应，验证 `records_skipped` 增加 1 且不抛出异常
- 现有调用方（不传 `use_flash`）行为不变

**依赖**: T1, T2

---

#### T4: 更新 chapter_generator.py — 应用双模型策略
**文件**: `src/core/llm/chapter_generator.py`  
**描述**: 在章节生成流程中，正文生成使用 flash，规划使用 pro。  
**实现要点**:
- `_generate_single_chapter_inner` 中：
  - 步骤 3（规划）：`client.generate(planning_prompt, max_tokens=3000)` — 不传 `use_flash`（默认 pro）
  - 步骤 5（正文）：`client.generate(prompt, max_tokens=8000)` — 传入 `use_flash=True`
  - `_continuation_generation` 中的 `client.generate(continuation_prompt, max_tokens=4000)` — 传入 `use_flash=True`

**验收标准**:
- `pytest tests/unit/test_llm/test_chapter_generator.py` 全部通过（mock client 验证 `use_flash` 参数传递正确）

**依赖**: T3

> 注意：本任务仅修改 `chapter_generator.py`，不修改 `chapter_rewriter.py` 和 `helpers.py`。

---

### 组 B — 数据库与 API（依赖组 A）

#### T5: 新增 LLMConfig 数据库模型
**文件**: `src/api/models/db_models.py`  
**描述**: 新增 `LLMConfig` SQLAlchemy 模型。  
**实现要点**:
- 表名 `llm_configs`
- 字段：`id`(PK)、`name`(String 100)、`base_url`(String 500)、`api_key`(String 500)、`model_flash`(String 100)、`model_pro`(String 100)、`is_active`(Boolean, default=False)、`created_at`、`updated_at`
- `is_active` 上加索引，便于快速查询激活配置
- `is_active` 的唯一性（同一时刻最多一条为 True）由应用层事务保证（`POST /configs/{id}/activate` 在同一事务内先将所有配置置为 False，再激活目标配置）；当前系统为单 worker 场景，并发风险可接受，不添加数据库级部分唯一索引

**验收标准**:
- `python -c "from src.api.models.db_models import LLMConfig; print(LLMConfig.__tablename__)"` 输出 `llm_configs`
- 应用启动后 `init_db()` 自动创建该表（无需手动迁移）

**依赖**: 无（可与组 A 并行）

---

#### T6: 新增 llm_config 路由文件
**文件**: `src/api/routes/llm_config.py`（新建）  
**描述**: 实现 LLM 配置 CRUD 接口和 token 统计接口。  
**实现要点**:
- `router = APIRouter(prefix="/api/v1/llm", tags=["llm"])`
- `GET /configs` — 查询所有配置，api_key 脱敏（`****` + 末4位）
- `POST /configs` — 创建配置，body: `{name, base_url, api_key, model_flash, model_pro}`
- `PUT /configs/{config_id}` — 更新配置（部分字段可选）
- `DELETE /configs/{config_id}` — 删除配置（若为激活配置则拒绝删除，返回 400）
- `POST /configs/{config_id}/activate` — 激活配置（事务内将其他配置 `is_active=False`，目标配置 `is_active=True`）
- `GET /token-stats` — 调用 `get_token_tracker().get_stats()` 返回统计数据
- 新增对应 Pydantic 请求/响应模型（可放在路由文件顶部或 `src/api/models/responses.py`）

**验收标准**:
- `pytest tests/api/routes/test_llm_config.py` 全部通过
- `GET /api/v1/llm/configs` 返回 200，api_key 字段不含完整密钥
- `POST /api/v1/llm/configs/{id}/activate` 后，其他配置 `is_active` 变为 False

**依赖**: T1, T5

---

#### T7: 注册 llm_config 路由到应用
**文件**: `src/api/routes/__init__.py`、`src/api/main.py`  
**描述**: 将新路由注册到 FastAPI 应用。  
**实现要点**:
- 在 `src/api/routes/__init__.py` 中导出 `llm_config_router`
- 在 `src/api/main.py` 中 `app.include_router(llm_config_router)`

**验收标准**:
- 应用启动后 `GET /api/v1/llm/token-stats` 返回 200

**依赖**: T6

---

#### T8: LLMClient 全局单例 — lifespan 初始化
**文件**: `src/core/llm/client.py`、`src/api/main.py`  
**描述**: 在应用启动时（lifespan）统一查询激活配置并初始化全局 `LLMClient` 单例，消除双工厂，使数据库配置对所有调用点生效。  
**实现要点**:
- `LLMClient.__init__` 接受可选参数 `llm_config: LLMConfig | None = None`
- 若传入 `llm_config`，则 `base_url`、`api_key`、`model_flash`、`model_pro` 从该对象读取；否则从 `Settings` 读取
- 在 `src/api/main.py` 的 lifespan startup 阶段，`await init_db()` 之后：查询数据库中激活的 `LLMConfig`，若存在则调用 `LLMClient(llm_config=active_config)` 初始化全局单例；若无激活配置则以 `LLMClient()` 初始化（回退到 Settings）
- `get_llm_client()` 保持同步，返回已初始化的全局单例；不引入异步工厂
- `chapter_generator.py`、`chapter_rewriter.py`、`helpers.py` 等所有调用点继续使用同步 `get_llm_client()`，无需修改

**验收标准**:
- `pytest tests/unit/test_llm/test_client_db_config.py` 全部通过
- 激活数据库配置后重启应用，新的 LLM 调用使用数据库中的 base_url 和模型名
- 无激活配置时，应用正常启动并回退到 Settings 配置

**依赖**: T3, T5

---

### 组 C — 前端（依赖组 B）

#### T9: 新增 LLMSettings.vue 页面
**文件**: `frontend/src/views/LLMSettings.vue`（新建）  
**描述**: LLM 配置管理与 token 统计前端页面。  
**实现要点**:
- 配置列表区：展示所有配置（名称、base_url、模型名、激活状态徽章）
- 操作按钮：新增、编辑（弹窗/内联表单）、删除（确认提示）、激活
- 表单字段：名称、base_url、api_key（password 输入框）、model_flash、model_pro
- Token 统计区：总调用次数、累计 prompt/completion/total tokens、按模型分组表格
- 使用项目现有 CSS 类（`card`、`btn-primary`、`input` 等，与 Home.vue 风格一致）
- API 调用使用原生 `fetch`，参考 `Home.vue` 或 `NovelDetail.vue` 的调用模式

**验收标准**:
- 页面可正常渲染，无控制台错误
- 新增配置后列表刷新，激活操作后激活状态正确显示
- Token 统计数据正确展示

**依赖**: T7

---

#### T10: 注册路由并添加导航入口
**文件**: `frontend/src/router/index.js`（或 `.ts`）、主导航组件  
**描述**: 将 LLMSettings 页面接入前端路由和导航。  
**实现要点**:
- 在路由文件中添加 `{ path: '/settings/llm', component: LLMSettings, name: 'LLMSettings' }`
- 在主导航组件（通过 Glob 确认实际文件名）末尾添加"模型配置"导航项，链接到 `/settings/llm`

**验收标准**:
- 浏览器访问 `/settings/llm` 正确渲染 LLMSettings 页面
- 导航栏显示"模型配置"入口

**依赖**: T9

---

## 执行顺序

```
T1 ──┐
T2 ──┤──► T3 ──► T4
T5 ──┘
     │
     ├──► T6 ──► T7 ──► T9 ──► T10
     │
     └──► T8（依赖 T3、T5）
```

- T1、T2、T5 可并行启动
- T3 依赖 T1、T2
- T4 依赖 T3
- T6 依赖 T1、T5
- T7 依赖 T6
- T8 依赖 T3、T5
- T9 依赖 T7
- T10 依赖 T9

---

## 测试文件清单

| 任务 | 测试文件 |
|------|---------|
| T1 | `tests/unit/test_llm/test_token_tracker.py` |
| T3 | `tests/unit/test_llm/test_client.py`（扩展现有） |
| T4 | `tests/unit/test_llm/test_chapter_generator.py`（扩展现有） |
| T6 | `tests/api/routes/test_llm_config.py`（新建） |
| T8 | `tests/unit/test_llm/test_client_db_config.py`（新建） |

# xIaoShuo 五大优化优先级 — 完整实施计划

> 生成日期: 2026-07-04
> 基于提交 25a42c2（refactor/split-projects-and-novelmanager 分支）
> 当前状态: projects.py 980→363行, NovelManager 792→184行 — 重构初阶段已完成

---

## 目录

- [P1: 拆分巨型文件 —— novel_generator.py(1040行) + knowledge_graph_service.py(1034行)](#p1-拆分巨型文件)
- [P2: LLM Client 健壮性增强 —— fallback链+流式保护+限流](#p2-llm-client-健壮性增强)
- [P3: 测试基础设施升级 —— SQLite模式+Mock层+新service测试](#p3-测试基础设施升级)
- [P4: LangGraph Checkpointer 生产化 —— SqliteSaver集成](#p4-langgraph-checkpointer-生产化)
- [P5: 性能热点优化 —— N+1查+流式推送+前端体积](#p5-性能热点优化)

---

## P1: 拆分巨型文件

### 第一阶段：novel_generator.py (1040行)

novel_generator.py 是一个模块级别的 Python 文件（非类封装），混杂了 17 个顶层函数。按功能垂直切分：

#### 拆分目标文件

| 新文件 | 职责 | 包含的函数 | 预估行数 |
|--------|------|-----------|---------|
| **A: task_control.py** | 生成任务生命周期控制 | pause_task, resume_task, is_task_paused | ~40行 |
| **B: chapter_generation_orchestrator.py** | 章节目录和单卷/按范围生成 | _prepare_chapter_context, _persist_quality_to_version, _generate_chapters_batch, generate_volume_background, generate_chapters_background | ~300行 |
| **C: long_form_orchestrator.py** | 百万字长篇整卷循环编排 | calculate_long_form_chapter_plan, generate_long_form_background | ~80行 |
| **D: full_generation_orchestrator.py** | 全功能 13 阶段流水线编排 | _build_initial_state, generate_novel_full_background, _run_sub_feature | ~250行 |
| **E: pipeline_runner.py** | LangGraph 7 节点流水线通用运行逻辑 | STAGE_ORDER, FULL_GENERATE_STAGES, _full_generate_percentage, _run_langgraph_pipeline, generate_novel_background, _persist_to_novel | ~300行 |

**向后兼容**：novel_generator.py 保留为轻量重导出桩（约 30 行），外部 import 不变。

#### 引用更新清单

| 调用者 | 旧引用 | 新引用 |
|-------|--------|--------|
| routes/projects.py:15 | 4 个函数 batch import | 从各新文件 import |
| routes/projects.py:298 | generate_volume_background | from .chapter_generation_orchestrator |
| routes/projects.py:343 | generate_chapters_background | from .chapter_generation_orchestrator |
| routes/novels.py:198,218,276,464,563 | pause_task, resume_task, generate_volume_background | 从 task_control 和 chapter_generation_orchestrator |
| services/__init__.py:3 | from .novel_generator import generate_novel_background | from .pipeline_runner import generate_novel_background |

#### 依赖关系

```
Task A1 ─┐
Task A2 ─┼── (无先后依赖，可并行)
Task A3 ─┘
    ↓
Task A4 ─── (需要 Task A1 的 pause 函数引用）
    ↓
Task A5 ─── (需要 Task A2 的 batch 函数 + Task A4 的 pipeline 函数）
    ↓
Task A6 ─── (汇总更新所有 import）
    ↓
Task A7
```

#### 实施任务

- [ ] **A1**: 创建 task_control.py，移入 3 个暂停函数，保留重导出
- [ ] **A2**: 创建 chapter_generation_orchestrator.py，移入 5 个函数
- [ ] **A3**: 创建 long_form_orchestrator.py，移入 2 个函数
- [ ] **A4**: 创建 pipeline_runner.py，移入 6 个函数/常量
- [ ] **A5**: 创建 full_generation_orchestrator.py，移入 3 个函数
- [ ] **A6**: 汇总更新所有 import 路径，清理 novel_generator.py
- [ ] **A7**: 全量测试验证

### 第二阶段：knowledge_graph_service.py (1034行)

单一 KnowledgeGraphService 类，19 个 public/private 方法 + 2 个顶层 prompt 常量 + 1 个单例工厂。

#### 拆分目标文件

| 新文件 | 职责 | 包含的方法 | 预估行数 |
|--------|------|-----------|---------|
| **F: kg_queries.py** | 共享数据库查询工具 | _get_existing_entities, _get_triples_by_names, _get_chapter_triples | ~80行 |
| **G: kg_extraction.py** | 实体/三元组 LLM 抽取 | KG_EXTRACTION_PROMPT, extract_from_chapter, _merge_entities, _write_triples, _write_extraction_log | ~300行 |
| **H: kg_context.py** | 图谱上下文检索与格式化 | retrieve_context, _get_hanging_foreshadowings, _get_recent_events, _format_context, _format_rich_context | ~200行 |
| **I: kg_consistency.py** | 规则 + LLM 一致性检查 | CONSISTENCY_CHECK_PROMPT, check_consistency, _rule_based_check, _build_history_context, _llm_consistency_check | ~200行 |
| **J: kg_graph_data.py** | 三层可视化数据组装 | get_three_layer_graph | ~100行 |
| **K: knowledge_graph_service.py** | 改造为门面/组合层 | get_knowledge_graph_service() 单例工厂 | ~50行 |

#### 引用更新清单

| 调用者 | 旧引用 | 新引用 |
|-------|--------|--------|
| routes/knowledge_graph.py:16 | get_knowledge_graph_service | 保持（从门面文件导入） |
| novel_generator.py:306 | get_knowledge_graph_service | 保持（同上） |
| blueprint_service.py:11 | KnowledgeGraphService（类型注解） | 改为 from .kg_extraction import KGExtractionService |

#### 依赖关系

```
Task B1 (基础查询)
    ├── Task B2 (抽取)
    ├── Task B3 (上下文)  ──→  Task B4 (一致性)
    ├── Task B5 (图谱数据)
    └── 全部 → Task B6 (门面改造) → Task B7
```

#### 实施任务

- [ ] **B1**: 创建 kg_queries.py，移入 3 个共享查询方法
- [ ] **B2**: 创建 kg_extraction.py，移入 5 个方法（依赖 B1）
- [ ] **B3**: 创建 kg_context.py，移入 5 个方法（依赖 B1）
- [ ] **B4**: 创建 kg_consistency.py，移入 5 个方法（依赖 B1, B3）
- [ ] **B5**: 创建 kg_graph_data.py，移入 1 个方法（依赖 B1）
- [ ] **B6**: 改造 knowledge_graph_service.py 为门面 + 更新 blueprint_service.py
- [ ] **B7**: 全量测试验证 + 手动 API 回归

#### 向后兼容策略

1. knowledge_graph_service.py 保留为门面文件，外部引用不变
2. 每拆 1-2 个新文件就执行一次 ruff check + mypy + pytest
3. 拆分完成后运行 ruff check --fix --select I 确保 import 顺序合规

#### 测试验证步骤

1. pytest tests/ -v —— 全量测试通过
2. ruff check src/api/services/ —— 无 lint 错误
3. mypy src/api/services/ --strict —— 类型检查通过
4. 手动启动 API 服务，触发 3 类生成流程（simple / full / long-form），验证 progress 事件流正常
5. 触发知识图谱抽取 + 检索 + 一致性检查 + 图谱可视化 API，验证返回值无变化

---

## P2: LLM Client 健壮性增强

### 总体设计原则

1. **向后兼容**：所有现有调用方签名不变
2. **配置驱动**：所有阈值、开关、参数统一收归 Settings
3. **可测试**：每个新增组件可独立 mock 测试
4. **渐进增强**：分阶段实现，每阶段可独立合并

### 变更概览

| 组件 | 新增文件 | 修改文件 |
|------|---------|---------|
| 配置化参数 | —— | src/core/config.py |
| 模型 fallback 链 | src/core/llm/fallback.py | src/core/llm/client.py |
| 流式超时保护 | —— | src/core/llm/client.py |
| 429 速率限制 | src/core/llm/rate_limiter.py | src/core/llm/client.py |
| 降级事件追踪 | src/core/llm/fallback.py (内含) | —— |
| 降级事件 API | —— | src/api/routes/llm_config.py |
| 单元测试 | tests/unit/test_llm/test_fallback.py, test_rate_limiter.py | tests/unit/test_llm/test_client.py |

### 阶段 1：配置化参数扩展

Settings 中新增 12 个配置字段，全部含默认值：

```python
# Fallback 链
DEEPSEEK_FALLBACK_ENABLED: bool = True
DEEPSEEK_FALLBACK_PRO_FAILURE_THRESHOLD: int = 3
DEEPSEEK_FALLBACK_FLASH_FAILURE_THRESHOLD: int = 3
DEEPSEEK_FALLBACK_WINDOW_SECONDS: int = 300
DEEPSEEK_FALLBACK_RECOVERY_INTERVAL: int = 60
DEEPSEEK_FALLBACK_LOCAL_MODEL: str = ""

# 流式超时
DEEPSEEK_STREAM_TIMEOUT: int = 300
DEEPSEEK_STREAM_CHUNK_TIMEOUT: int = 30
DEEPSEEK_STREAM_FALLBACK_TO_NONSTREAM: bool = True

# 速率限制
DEEPSEEK_RATE_LIMIT_ENABLED: bool = True
DEEPSEEK_RATE_LIMIT_TOKENS_PER_SECOND: float = 10.0
DEEPSEEK_RATE_LIMIT_BURST: int = 30
DEEPSEEK_RATE_LIMIT_MAX_CONCURRENT: int = 5
```

### 阶段 2：降级事件追踪器 (fallback.py)

```python
@dataclass
class DegradationEvent:
    timestamp: datetime
    from_model: str          # "pro" / "flash"
    to_model: str            # "flash" / "local"
    reason: str              # "consecutive_failures" / "stream_timeout" / "rate_limit"
    failure_count: int
    exception_type: str
    duration_seconds: float

class DegradationTracker:
    """滑动时间窗口的失败计数 + 降级决策"""
    def record_failure(self, model_tier: str, exception: Exception) -> int
    def record_degradation(self, event: DegradationEvent) -> None
    def should_degrade(self, model_tier: str, threshold: int) -> bool
    def should_recover(self, model_tier: str, recovery_interval: int) -> bool
    def record_recovery(self, model_tier: str) -> None
    def get_degradation_log(self) -> list[dict]
```

### 阶段 3：模型 Fallback 链

核心逻辑嵌入 LLMClient.generate()：

```
当前状态: pro
  ├─ pro 连续失败 >= threshold
  │    └─ 降级到 flash, 记录 DegradationEvent
  │         ├─ flash 连续失败 >= threshold
  │         │    └─ 降级到 local（如果配置了本地模型）
  │         │         └─ local 也失败 → 抛异常
  │         └─ flash 成功 → 每 recovery_interval 尝试恢复 pro
  └─ pro 成功 → 正常状态
```

LLMClient 新增 `_current_tier` 属性和 `_get_effective_tier()` 方法，对外 `generate()` 接口不变。

### 阶段 4：流式超时保护

三重保护改造 stream_generate()：
1. **总超时**: asyncio.timeout(stream_timeout) 包裹整个 astream 迭代
2. **块间隔超时**: _stream_with_chunk_timeout() 检测 chunk 间延迟
3. **fallback 回退**: 超时后调用 self.generate() 作为一个 chunk 产出

### 阶段 5：429 速率限制 (rate_limiter.py)

```python
class TokenBucketRateLimiter:
    """令牌桶 + 请求队列 + 并发上限"""
    async def acquire(self) -> None

class NoopRateLimiter:
    """关闭时零开销空实现"""
```

每个 generate() / stream_generate() 入口执行 await self._rate_limiter.acquire()。

### 阶段 6：降级事件 API

在 llm_config.py 新增 GET /degradation-log 端点。

### 实施任务

- [ ] **S1**: 修改 Settings 添加 12 个字段，跑现有测试
- [ ] **S2**: 创建 fallback.py，实现 DegradationTracker，编写单元测试
- [ ] **S3**: 创建 rate_limiter.py，实现令牌桶 + 并发控制，编写单元测试
- [ ] **S4**: 修改 client.py，集成 fallback + rate_limiter + stream_timeout
- [ ] **S5**: 新增 /degradation-log 端点
- [ ] **S6**: 集成测试：完整 mock 验证 fallback/重试/限流/超时行为
- [ ] **S7**: Review：确认所有调用方无感知，向后兼容

---

## P3: 测试基础设施升级

### 核心架构

```
                         ┌──────────────────────────────────┐
                         │        tests/conftest.py          │
                         │  pytest_addoption + 自动分发      │
                         └──────────┬───────────────────────┘
                                    │ marker: sqllite / postgres
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
    ┌─────────────────────────┐    ┌─────────────────────────┐
    │    SQLite 模式           │    │   PostgreSQL 模式        │
    │  (默认，pytest --db=sqllite)│  │  (pytest --db=postgres) │
    │                         │    │                         │
    │  session-scope engine   │    │  保持 conftest.py       │
    │  + aiosqlite :memory:   │    │  现有行为不变              │
    │  + 每次 test 独立       │    │                         │
    │    session + 回滚        │    │                         │
    └──────────┬──────────────┘    └─────────────────────────┘
               │
               ▼
    ┌─────────────────────────┐
    │  LLM Mock Fixture       │
    │  (conftest_llm.py)      │
    │  mock_llm_client →      │
    │  patch ChatOpenAI       │
    │  可控预设响应/错误       │
    └─────────────────────────┘
```

### 实施任务

#### 阶段 1：基础依赖与 conftest 改造

- [ ] **1.1**: 添加 aiosqlite 依赖
- [ ] **1.2**: 新建 tests/conftest_db.py —— 数据库 fixture 工厂
  - pytest_addoption: --db={sqllite,postgres} 默认 sqllite
  - sqllite_engine fixture (session scope): :memory: SQLite 引擎
  - sqllite_create_tables (session scope, autouse): Base.metadata.create_all
  - db_session fixture (function scope): 新 AsyncSession，test 结束后回滚
- [ ] **1.3**: 修改 conftest.py —— 条件导入 SQLite fixture；pytest_configure 仅 postgres 生效
- [ ] **1.4**: 确保 EncryptedString 在 SQLite 中兼容（fixture patch）
- [ ] **1.5**: 验证 pytest tests/unit/ --db=sqllite --co

#### 阶段 2：LLM Mock Fixture

- [ ] **2.1**: 新建 tests/conftest_llm.py

| Fixture | Scope | 作用 |
|---------|-------|------|
| mock_llm_settings | function | patch get_settings 返回可控配置 |
| mock_chat_openai | function | patch ChatOpenAI 返回 AsyncMock |
| mock_llm_client | function | 组合返回预设 AIMessage(content=...) |
| mock_llm_client_failure | function | 模拟 401/429/500 测试重试逻辑 |
| mock_llm_client_stream | function | 模拟 astream chunk 序列 |

- [ ] **2.2**: 兼容现有 tests/unit/test_llm/test_client.py

#### 阶段 3：新 Service 单元测试

- [ ] **3.1**: 新建 tests/unit/test_services/ 目录
- [ ] **3.2**: test_volume_service.py —— CRUD + not_found + duplicate
- [ ] **3.3**: test_chapter_service.py —— CRUD + 版本管理 + rollback/activate/compare
- [ ] **3.4**: test_character_service.py —— CRUD + FK 约束
- [ ] **3.5**: test_world_service.py —— upsert + power_systems CRUD

#### 阶段 4：现有测试无损迁移

- [ ] **4.1**: 需要 PostgreSQL 的测试加 @pytest.mark.postgres
- [ ] **4.2**: conftest.py 按标记分发
- [ ] **4.3**: 添加 pytest-xdist，SQLite 模式可 -n auto 并行

#### 阶段 5：CI 配置

- [ ] **5.1**: CI pipeline 分步
- [ ] **5.2**: 全量回归 pytest --db=postgres
- [ ] **5.3**: 记录性能对比基线

### 预期成果

| 指标 | 当前 | 升级后 |
|------|------|--------|
| 单元测试数量 | ~300 | ~400+ |
| 全量测试时间 | ~5-10min | ~30s (SQLite) / 不变 (PG) |
| 无外部依赖测试 | ~200 | ~400+ |
| LLM 调用 | 真调用 DeepSeek | 全 mock，零外部依赖 |
| 并行能力 | 否 | 是（SQLite :memory: 隔离） |
| 测试间隔离 | 弱 | 强（function scope session + 回滚） |

---

## P4: LangGraph Checkpointer 生产化

### 方案：SqliteSaver（首选）

**理由**：
- Checkpoint 数据小，为几 KB 引入 PG schema 迁移不划算
- 零 Schema 侵入（现有 30+ ORM 模型）
- 本地开发零依赖，文件即数据库
- LangGraph 官方维护，API 稳定
- WAL 模式支持读写并发

**备选**：PostgresSaver（水平扩展 > 1 个 API 容器时）

### 文件改动清单

**1. pyproject.toml** —— 新增依赖
```
langgraph-checkpoint-sqlite = "^2.0.0"
```

**2. src/core/config.py** —— 新增配置项
```python
CHECKPOINTER_TYPE: str = "memory"
CHECKPOINTER_DIR: str = "data/checkpoints"
```

**3. checkpointer.py** —— 重构为工厂方法
```python
def get_checkpointer() -> MemorySaver | SqliteSaver:
    settings = get_settings()
    if settings.CHECKPOINTER_TYPE == "sqlite":
        cp_dir = Path(settings.CHECKPOINTER_DIR)
        cp_dir.mkdir(parents=True, exist_ok=True)
        db_path = cp_dir / "langgraph_checkpoints.sqlite"
        return SqliteSaver.from_conn_string(f"sqlite:///{db_path}")
    return MemorySaver()
```

**4. graph.py** —— 三处 MemorySaver() 替换为 get_checkpointer()

**5. .env.example** —— 新增环境变量
```
CHECKPOINTER_TYPE=memory
CHECKPOINTER_DIR=data/checkpoints
```

**6. docker-compose.yml** —— 持久化 volume（生产启用）
```yaml
environment:
  CHECKPOINTER_TYPE: sqlite
  CHECKPOINTER_DIR: /data/checkpoints
volumes:
  - checkpoint_data:/data/checkpoints
volumes:
  checkpoint_data:
```

### 实施任务

- [ ] **C1**: poetry add langgraph-checkpoint-sqlite
- [ ] **C2**: Settings 中新增 CHECKPOINTER_TYPE 和 CHECKPOINTER_DIR
- [ ] **C3**: 重构 checkpointer.py 为工厂方法
- [ ] **C4**: 重构 graph.py 三处替换 + 清理 import
- [ ] **C5**: 更新 .env.example + docker-compose.yml
- [ ] **C6**: 验证：CHECKPOINTER_TYPE=sqlite 下确认 checkpoint 文件生成
- [ ] **C7**: 回滚验证：切回 memory 模式不受影响

---

## P5: 性能热点优化

### P0 —— 高收益低风险（立即执行）

#### 1. N+1 查询检测与消除

**排查点**：
- [ ] 知识图谱批量校验：validate_consistency 中是否对每个 entity 单独查询 → 批量 JOIN/IN
- [ ] 章节列表加载：list 端点中是否对每章节单独查 outline/characters → selectinload
- [ ] 大纲同步：是否循环 refresh 单个节点 → INSERT ... ON CONFLICT
- [ ] 批量事件推送：publish_batch 每事件 send_json → asyncio.gather

**预期效果**：消除 50-80% 冗余 DB 查询

#### 2. 前端路由懒加载

- [ ] 所有 views 改为 () => import('@/views/Foo.vue')
- [ ] 确认 d3 cherry-pick 导入
- [ ] 大型图 IntersectionObserver + 视口内渲染

**预期效果**：首屏 JS 减少 40-60%，DOM 节点数减少 60-80%

### P1 —— 中等复杂度

#### 3. 流式生成逐 token/逐 chunk 推送

**改造流程**：LLM 每产出 chunk_size tokens → progress_event_bus.publish → WebSocket → 前端拼接渲染

- [ ] 后端：LLM invoke → stream，每 50-200 tokens 推送
- [ ] 后端：新增 STREAM_CHUNK / STREAM_DONE / STREAM_ERROR 事件类型
- [ ] 后端：WebSocket 接收 cancel_generation，中断生成
- [ ] 前端：StreamingText.vue 增量渲染
- [ ] 前端：useWebSocket.js 处理 STREAM_CHUNK 事件
- [ ] 前端：停止按钮 + 断连重连

**预期效果**：首 token 200ms 内展示（从 20-60s 白屏变为实时看到生成过程）

#### 4. WebSocket 连接管理

- [ ] 后端：连接注册表 {novel_id: set[WebSocket]}
- [ ] 后端：asyncio.gather 分发事件
- [ ] 前端：心跳 + 指数退避重连

**预期效果**：多 tab 连接数减少 50%

### P2 —— 按需优化

#### 5. 高频只读查询缓存

- [ ] get_novel_metadata、get_chapter_titles 等使用 aiocache / lru_cache + TTL

#### 6. 数据库连接池调优

- [ ] pool_size=10, max_overflow=20

### 基准测试与验证

- [ ] 每个优化前录制基线（scripts/benchmark.py）
- [ ] SQL 查询计数通过 X-DB-Queries 响应头返回
- [ ] vite build --report 记录 bundle 体积
- [ ] Lighthouse 记录 FCP/TBT

---

## 总体执行建议

### 推荐启动顺序

```
Week 1: P1 文件拆分 (novel_generator) + P4 Checkpointer
         → 并行推进：P4 改动量小（3 个文件）

Week 2: P1 文件拆分 (knowledge_graph) + P3 测试基础 (1.1-1.3)
         → P3 的 SQLite 模式支撑新 service 测试

Week 3: P2 LLM 健壮性 (S1-S4)
         → 依赖 P3 的 LLM mock 设施

Week 4: P5 性能优化 (N+1 + 路由懒加载) + P2 (S5-S7)
         → 快速见效，收尾
```

### 关键依赖图

```
P1 (拆分)  ← 阻塞  P3 (新 service 测试所测对象)
P3 (LLM Mock)  ← 支撑  P2 (fallback/限流测试)
P5 (流式推送)  ← 依赖  P2 (stream 超时保护)
P4 (Checkpointer)  ← 独立，可随时推进
```

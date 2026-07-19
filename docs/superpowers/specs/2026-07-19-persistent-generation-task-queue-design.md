# 持久化生成任务队列设计

> 将小说生成从 FastAPI `BackgroundTasks` 迁移到 PostgreSQL 租约队列，使排队任务在进程或容器重启后仍可执行，并通过数据库锁避免多进程重复领取。

## 背景

当前所有小说生成入口先在 `tasks` 表写入 `pending`，随后用 FastAPI
`BackgroundTasks.add_task()` 在进程内启动协程。`Task` 表只保存展示字段，没有任务类型、
可重放参数或执行租约。服务在创建记录后、后台协程真正启动前重启时，任务永久停在
`pending`；任务执行中重启时则停在 `running`。

现有 `recover_interrupted_tasks()` 的短期保护是在启动时把所有 `pending/running` 标记为
失败。它避免了假死，但没有恢复排队任务，也不能在多个 API worker 之间协调领取。

本设计覆盖所有使用 `TaskManager` 和 `Task` 表的生成任务：

- 普通小说生成。
- 13 阶段全功能生成。
- 百万字长篇生成。
- 指定卷生成与恢复。
- 指定章节范围生成。
- HITL 审核后的 `resume_pipeline`。

书籍导入和读者视角模拟目前分别使用内存任务字典与 `reader_simulations` 表，生命周期、
返回标识和持久化数据不同，不在本子工程中混入；它们在后续“非生成后台作业”阶段迁移。

## 目标

1. 任务记录与可执行参数在同一数据库事务中持久化。
2. 排队任务不依赖请求进程内的 `BackgroundTasks`，重启后仍保持可领取。
3. 多进程或多实例通过 PostgreSQL 行锁只领取一次任务。
4. worker 执行期间定期续租，能够识别失联执行者。
5. 保持现有 HTTP 路径、请求、响应和前端任务状态契约。
6. HITL 中断后任务停止占用队列；提交审核时重新入队同一 `task_id`。
7. 对非幂等生成流程采用安全失败策略，不在进程中断后盲目重复写入。
8. 为未来已经证明幂等的任务保留受限重试能力。

## 非目标

- 不引入 Celery、Redis、RabbitMQ 或新的外部基础设施。
- 不改变 LLM 调用、生成内容、质量门禁或章节算法。
- 不把 WebSocket 事件总线改成跨进程消息系统。
- 不在本阶段迁移书籍导入和读者模拟后台作业。
- 不自动重放已开始且可能产生部分写入的现有生成任务。
- 不处理登录、密钥、管理员配置等安全收口。
- 不执行 Git 暂存、提交或推送。

## 方案比较

### 方案一：Celery + Redis

生态成熟，具备完善的 worker、重试和监控能力，但项目当前没有 Redis，需同时修改
Poetry、Docker Compose、部署脚本和运维监控。生成任务仍需解决至少一次投递下的幂等性。
本阶段不采用。

### 方案二：启动时从 Task 表直接 `asyncio.create_task()` 重放

实现最少，但多个 API worker 会重复扫描和执行，没有领取锁、租约、心跳和背压。它只是
把 `BackgroundTasks` 换成另一种进程内协程，不构成可靠队列。不采用。

### 方案三：PostgreSQL 租约队列（采用）

复用现有 `tasks` 表和 PostgreSQL，通过 `SELECT ... FOR UPDATE SKIP LOCKED` 原子领取，
用租约和心跳检测失联 worker。无需新增外部服务，部署变化最小，并能在多 API 实例下避免
重复领取。

## 数据模型

在 `tasks` 表增加内部队列字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `task_type` | `varchar(50)`, nullable | 调度类型；`NULL` 表示历史不可重放任务 |
| `task_payload` | `json`, nullable | 仅保存重建调用所需的 JSON 参数 |
| `queue_state` | `varchar(20)`, nullable | `queued / leased / idle`；与用户可见 `status` 分离 |
| `attempt_count` | int, default 0 | 当前执行段已领取次数 |
| `max_attempts` | int, default 1 | 最大领取次数；现有生成类型固定为 1 |
| `available_at` | timestamptz, nullable | 最早可领取时间 |
| `lease_owner` | varchar(120), nullable | 当前 worker 唯一标识 |
| `lease_expires_at` | timestamptz, nullable | 租约失效时间 |
| `heartbeat_at` | timestamptz, nullable | 最近一次续租时间 |

建立 `(queue_state, available_at)` 索引。队列字段不加入现有公开响应模型，避免扩大 API
契约；内部测试可直接检查 ORM 对象或 TaskManager 返回的私有执行字典。

## 双状态机

`Task.status` 继续表示用户看到的业务状态：

```text
pending -> running -> completed / failed
                   -> paused
                   -> running + progress.waiting_for_review
```

`Task.queue_state` 只表示是否需要 worker 执行：

```text
queued -> leased -> idle
           |
           +-- 未捕获异常且允许重试 -> queued
           +-- 次数耗尽/非幂等中断 -> idle + Task.status=failed
```

分离两个状态的原因是 HITL：任务在等待人工审核时业务状态仍可保持 `running`，但队列必须
是 `idle`，否则 worker 会把等待审核误判为失联执行并重新生成。

## 任务类型与载荷

固定任务类型：

| `task_type` | handler | payload |
|---|---|---|
| `novel.generate` | `generate_novel_background` | `request` |
| `novel.full_generate` | `generate_novel_full_background` | `request` |
| `novel.long_form` | `generate_long_form_background` | `novel_id`, `request` |
| `novel.volume` | `generate_volume_background` | `novel_id`, `volume_number` |
| `novel.chapters` | `generate_chapters_background` | `novel_id`, `chapter_start`, `chapter_end` |
| `pipeline.resume` | `resume_pipeline` | `decision` |

Pydantic 请求统一使用 `model_dump(mode="json")` 入库，dispatcher 使用
`model_validate()` 重建。payload 不保存 LLM client、数据库 session、用户对象或任意可执行
Python 对象。

## TaskManager 接口

### 创建与重新入队

`create_task()` 增加可选关键字：`task_type`、`task_payload`、`max_attempts`。传入
`task_type` 时，在同一次 INSERT 中写入 `queue_state="queued"` 和 `available_at=now`。

`enqueue_existing_task()` 用于 HITL resume：锁定原 Task，替换类型和 payload，重置本执行段
的 `attempt_count=0`，清理旧租约并设置 `queue_state="queued"`。沿用原 `task_id`，前端不产生
第二条任务。

### 原子领取

`claim_next_task(worker_id, lease_seconds)` 查询：

- `queue_state="queued"`；
- `available_at` 为空或不晚于当前时间；
- `attempt_count < max_attempts`。

按 `created_at` 升序，使用 `FOR UPDATE SKIP LOCKED LIMIT 1`。领取后在同一事务中设置：

- `queue_state="leased"`；
- `status="running"`；
- `attempt_count += 1`；
- `lease_owner`、`lease_expires_at`、`heartbeat_at`。

### 续租与结束

- `renew_lease()` 仅允许当前 `lease_owner` 延长租约。
- `complete_task()`、`fail_task()`、用户取消均把 `queue_state` 设为 `idle` 并清空租约。
- handler 正常返回但处于 HITL/paused 时，worker 调用 `release_claim()` 使队列进入 `idle`。
- handler 正常返回但 Task 仍是普通 `running` 且未等待审核，视为实现错误并标记失败，避免
  再次形成假死任务。

### 异常与重试

worker 捕获未被 handler 处理的异常并调用 `retry_or_fail_claim()`：

- `attempt_count < max_attempts`：追加错误、设置 `available_at` 后重新 `queued`。
- 次数耗尽：Task 进入 `failed`，队列进入 `idle`。

现有六类生成任务和 `pipeline.resume` 都设置 `max_attempts=1`。原因是全功能生成会创建故事线、
人物弧光、场景等非幂等记录，进程中断后自动重放可能产生重复内容。只有后续完成幂等审计的
新任务类型才能把次数设置为大于 1。

## Worker 生命周期

新增 `PersistentTaskWorker`：

1. FastAPI 启动并完成数据库、checkpointer、LLM client 初始化后启动。
2. 每次只领取一个任务；多个 API 进程可各自运行一个 worker，由数据库锁协调。
3. 执行 handler 时并行运行心跳协程，间隔小于租约的三分之一。
4. 没有任务时按配置的轮询间隔等待。
5. 停机时停止领取、取消当前执行和心跳；不把取消当业务失败，保留 leased 状态供下次启动
   恢复逻辑判断。
6. 在 worker 完全停止后再关闭 checkpointer 和数据库连接。

配置项：

- `TASK_QUEUE_ENABLED=true`
- `TASK_QUEUE_POLL_SECONDS=1.0`
- `TASK_QUEUE_LEASE_SECONDS=120`
- `TASK_QUEUE_RETRY_DELAY_SECONDS=5`

## 启动恢复

`recover_interrupted_tasks()` 改为分类处理：

1. `queue_state="queued"`：保持不变，由 worker 继续领取。
2. `queue_state="leased"` 且租约未过期：可能属于另一个存活实例，不触碰。
3. `queue_state="leased"` 且租约过期：
   - 若 `attempt_count < max_attempts`，重新排队；
   - 否则标记失败，说明任务在执行中因进程中断且不安全自动重放。
4. `queue_state IS NULL` 的历史 `pending/running`：继续按旧逻辑标记失败，因为缺少类型和参数。
5. `idle`、`completed`、`failed`、等待审核任务不触碰。

返回值改为结构化统计 `queued_preserved / stale_requeued / stale_failed / legacy_failed`，
main 只记录日志。旧测试和调用方如需整数，使用 `total_changed` 属性，不再用模糊的单一 count。

## 路由迁移

所有 Task-backed 生成路由不再调用 `background_tasks.add_task()`，而是在 `create_task()` 时写入
类型和 payload。HTTP 响应仍立即返回 202，字段和状态文案保持不变。

HITL 审核路由对 `approved/revision` 调用 `enqueue_existing_task()`；`rejected` 仍直接失败。

路由内部的 `BackgroundTasks` 参数可移除，因为它不会出现在外部 HTTP 契约中。书籍导入与
读者模拟路由继续保留该参数，直到各自迁移。

## 兼容性与部署

- Alembic 迁移从当前唯一 head `c3d8e1f7a2b4` 继续。
- `Base.metadata.create_all()` 能为新测试库创建完整字段；线上库必须执行 Alembic upgrade。
- 历史 Task 行队列字段均为 NULL，不会被 worker 领取。
- `API_WORKERS>1` 时每个进程可运行一个 worker，`SKIP LOCKED` 保证单次领取。
- WebSocket 事件仍是进程内总线；若客户端连接到非执行 worker，只能通过现有任务状态查询
  获取进度。跨进程实时事件属于后续独立工程。

## 测试策略

### 数据模型与迁移

- Task 新字段默认值、nullable 和索引测试。
- Alembic upgrade/downgrade 静态结构测试。

### TaskManager

- 创建可执行任务原子写入类型、payload 和 queued 状态。
- `SKIP LOCKED` 领取并写入租约。
- 未到 `available_at`、次数耗尽和 idle 任务不领取。
- owner 不匹配不能续租或释放。
- HITL 重新入队重置执行段元数据。
- 启动恢复四类分支全部覆盖。

### Dispatcher 与 Worker

- 六种生成类型和 resume 参数重建正确。
- 未知类型失败且不执行任意导入路径。
- 心跳在长任务期间调用。
- 正常完成、HITL idle、未捕获异常、次数耗尽、取消停机分别覆盖。
- stop 后不再领取新任务。

### 路由

- 每个生成入口写入正确 `task_type/payload`。
- 路由不再注册 FastAPI BackgroundTask。
- 现有响应状态码和 JSON 契约不变。

### 回归

- 完整后端单元测试。
- Task 路由和长篇 API 测试（数据库可用时）。
- FastAPI lifespan 启停测试。
- 前端 47 个测试和生产构建。

## 验收标准

- 任一 queued Task 在 API 重启后仍保持 queued，并由新 worker 领取。
- 两个并发 worker 不会领取同一 Task。
- leased 任务持续续租；失联后按最大次数安全重排或失败。
- 当前非幂等生成任务不会在执行中断后自动重放。
- HITL 等待阶段不会被 worker 误领取；审核后同一 task_id 可再次入队。
- 所有 Task-backed 生成路由不再依赖 FastAPI BackgroundTasks。
- 现有 API 响应与前端测试不回归。
- 数据库集成验证若仍受环境限制，必须明确记录为未验证，不能用 Mock 替代线上结论。


# xIaoShuo 重构实施计划（方案1 + 方案2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `projects.py`（980行）路由拆分 + `NovelManager`（792行）按实体拆分，消除巨型文件，明确分层边界。

**架构原则：**
- 路由层只做参数校验和转发，业务逻辑下沉到 service
- 每个实体（Novel / Chapter / Volume / Character / World）一个独立 service 文件
- service 层统一通过 `get_db_session` 访问数据库
- 所有修改保持向后兼容，不改动现有 API 端点路径

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy asyncio · pytest

---

## 依赖变更图

```
重构前：
projects.py (路由) → NovelManager (792行, 所有实体CRUD) → db_models.py

重构后：
projects.py (路由, 仅Novel) ──────────→ NovelManager (仅Novel CRUD)
chapters.py (路由) ──────────────────→ ChapterService (章节+版本)
volumes.py (路由) ───────────────────→ VolumeService (卷)
characters.py (路由) ────────────────→ CharacterService (角色)
world.py (路由) ─────────────────────→ WorldService (世界观+力量体系)
```

---

## Task 规划

### Task 1: 准备阶段 — 备份 + 确认测试基线

**Files:**
- Run: `cd /Users/a1/Developer/projects/xIaoShuo && git status`

- [ ] **Step 1: 创建功能分支**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git checkout -b refactor/split-projects-and-novelmanager
```

- [ ] **Step 2: 确认当前测试能跑通，记录基线**

```bash
poetry install
poetry run pytest tests/ --tb=short -q 2>&1 | tail -20
```

---

### Task 2: 创建独立路由文件 — volumes.py

**Files:**
- Create: `src/api/routes/volumes.py`
- Modify: `src/api/routes/__init__.py`
- Modify: `src/api/main.py`

> 从 `projects.py` 中抽出所有 `/volumes` 相关的路由（约 70 行）。

- [ ] **Step 1: 创建 `src/api/routes/volumes.py`**

```python
"""卷管理 API 路由"""

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.models.responses import StatusResponse, VolumeResponse
from src.api.services.volume_service import (
    get_volume_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/{novel_id}", tags=["volumes"])


@router.get("/volumes")
async def list_volumes(novel_id: str):
    service = get_volume_service()
    return await service.list_volumes(novel_id)


@router.get("/volumes/{volume_number}", response_model=VolumeResponse)
async def get_volume(novel_id: str, volume_number: int):
    service = get_volume_service()
    vol = await service.get_volume(novel_id, volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")
    return vol


class VolumeUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


@router.put("/volumes/{volume_number}", response_model=StatusResponse)
async def update_volume(novel_id: str, volume_number: int, request: VolumeUpdateRequest):
    service = get_volume_service()
    updated = await service.update_volume(novel_id, volume_number, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Volume not found")
    return {"status": "updated"}
```

> 注意：这里 `VolumeUpdateRequest` 如果较短可以直接内联，后面再考虑提到 models 层。

- [ ] **Step 2: 将 `VolumeUpdateRequest` 提取为完整的内联定义，并引入 `BaseModel`**

```python
from pydantic import BaseModel
```
并在 `VolumeUpdateRequest` 上方补上 `class VolumeUpdateRequest(BaseModel):`。

- [ ] **Step 3: 在 `src/api/routes/__init__.py` 注册 volumes_router**

```python
from .volumes import router as volumes_router
```
并在 `__all__` 中添加 `"volumes_router"`。

- [ ] **Step 4: 在 `src/api/main.py` 注册路由**

在 `app.include_router(volumes_router)` 之前或之后合适位置添加。

**注意：** 此时 `volumes.py` 依赖的 `VolumeService` 还未创建，Task 2 只负责路由层的注册。我们将先做路由层骨架，再统一实现 service 层。但为了能够推进，可以先从 `NovelManager` 中重命名引用为临时桩 —— 或直接先将 `VolumeService` 的路由调用在测试时再注入。

稳妥策略：**先创建路由文件 + 注册到主应用，但路由函数体后续在 Task 5 实现 service 时才真正填充业务逻辑。** 这样避免中间状态不可用。

建议：Task 2-4（路由层）只创建文件骨架和注册，Task 5-8 再填充具体导入和实现。

---

以我的经验，更务实的顺序是：

## 执行顺序（按依赖）

```
Task 1: 准备分支 + 测试基线
├── Task 5: 创建 VolumeService（被 routes/volumes.py 依赖）
├── Task 6: 创建 ChapterService（被 routes/chapters.py 依赖）
├── Task 7: 创建 CharacterService（被 routes/characters.py 依赖）
├── Task 8: 创建 WorldService（被 routes/world.py 依赖）
├── 然后批量：Task 2 → Task 3 → Task 4（路由层，一次性从 projects.py 剪出）
└── Task 9: 瘦身 NovelManager（只保留 Novel CRUD）
└── Task 10: 验证 + 清理
```

但这样前 4 个 Task 做 service 时没有路由消费方，无法端到端测试。所以实际按**功能垂直切分**最稳妥：

```
Task 1: 准备
Task 2: 拆 卷 (Volume) — VolumeService + routes/volumes.py 一步到位
Task 3: 拆 章节 (Chapter) — ChapterService + routes/chapters.py 一步到位
Task 4: 拆 角色 (Character) — CharacterService + routes/characters.py 一步到位
Task 5: 拆 世界观 (World) — WorldService + routes/world.py 一步到位
Task 6: 瘦身 NovelManager — 移除已拆走的方法
Task 7: 瘦身 projects.py — 移除已拆走的路由
Task 8: 全局验证 + import cleanup
Task 9: 重复 Task 1 的测试确认所有测试通过
Task 10: 提交
```

---

### Task 1: 准备分支 + 测试基线

**Files:**
- Run: `cd /Users/a1/Developer/projects/xIaoShuo`

- [ ] **Step 1: 创建功能分支**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git checkout -b refactor/split-projects-and-novelmanager
```

- [ ] **Step 2: 确认当前测试能跑通，记录基线**

```bash
poetry run pytest tests/ --tb=short -q 2>&1 | tail -20
```

**预期：** 看到 `X passed`，记录 X 值。如果测试失败或无法运行，先记录当前状态。

- [ ] **Step 3: 确认 routes/__init__.py 和 main.py 已熟悉**

```bash
cat src/api/routes/__init__.py
```

---

### Task 2: 拆卷 — VolumeService + routes/volumes.py

**Files:**
- Create: `src/api/services/volume_service.py`
- Delete after extraction: `src/api/routes/volumes.py`
- Modify: `src/api/services/__init__.py`
- Modify: `src/api/routes/__init__.py`
- Modify: `src/api/main.py`

> 将 NovelManager 中所有 volume 相关方法（list_volumes, get_volume, create_volume, update_volume）移到 VolumeService。

- [ ] **Step 1: 创建 `src/api/services/volume_service.py`**

```python
"""卷管理服务"""

import structlog
from sqlalchemy import select

from src.api.models.db_models import Volume, Novel
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class VolumeService:
    """卷（Volume）的 CRUD 操作"""

    async def list_volumes(self, novel_id: str) -> list[dict]:
        """列出小说所有卷"""
        async with get_db_session() as session:
            stmt = (
                select(Volume)
                .where(Volume.novel_id == novel_id)
                .order_by(Volume.volume_number)
            )
            result = await session.execute(stmt)
            volumes = result.scalars().all()
            return [self._volume_to_dict(v) for v in volumes]

    async def get_volume(self, novel_id: str, volume_number: int) -> dict | None:
        """获取单个卷"""
        async with get_db_session() as session:
            stmt = select(Volume).where(
                Volume.novel_id == novel_id,
                Volume.volume_number == volume_number,
            )
            result = await session.execute(stmt)
            vol = result.scalar_one_or_none()
            return self._volume_to_dict(vol) if vol else None

    async def create_volume(self, novel_id: str, volume_number: int,
                            title: str, summary: str | None = None) -> int:
        """创建卷"""
        async with get_db_session() as session:
            vol = Volume(
                novel_id=novel_id,
                volume_number=volume_number,
                title=title,
                summary=summary or "",
            )
            session.add(vol)
            await session.commit()
            return vol.id

    async def update_volume(self, novel_id: str, volume_number: int,
                            **kwargs) -> bool:
        """更新卷信息"""
        async with get_db_session() as session:
            stmt = select(Volume).where(
                Volume.novel_id == novel_id,
                Volume.volume_number == volume_number,
            )
            result = await session.execute(stmt)
            vol = result.scalar_one_or_none()
            if not vol:
                return False
            for key, value in kwargs.items():
                if hasattr(vol, key) and value is not None:
                    setattr(vol, key, value)
            await session.commit()
            return True

    @staticmethod
    def _volume_to_dict(self, vol: Volume) -> dict:
        """将 Volume ORM 对象转为字典"""
        return {
            "id": vol.id,
            "novel_id": vol.novel_id,
            "volume_number": vol.volume_number,
            "title": vol.title,
            "summary": vol.summary,
            "chapter_start": vol.chapter_start,
            "chapter_end": vol.chapter_end,
            "status": vol.status,
            "created_at": vol.created_at.isoformat() if vol.created_at else None,
            "updated_at": vol.updated_at.isoformat() if vol.updated_at else None,
        }


# 全局单例
_service: VolumeService | None = None


def get_volume_service() -> VolumeService:
    global _service
    if _service is None:
        _service = VolumeService()
    return _service
```

- [ ] **Step 2: 从 `projects.py` 复制 volume 路由到 `routes/volumes.py`**

```python
"""路由模块 - 卷管理"""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.models.responses import StatusResponse, VolumeResponse
from src.api.services.volume_service import get_volume_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/{novel_id}", tags=["volumes"])


class VolumeUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


@router.get("/volumes")
async def list_volumes(novel_id: str):
    service = get_volume_service()
    return await service.list_volumes(novel_id)


@router.get("/volumes/{volume_number}", response_model=VolumeResponse)
async def get_volume(novel_id: str, volume_number: int):
    service = get_volume_service()
    vol = await service.get_volume(novel_id, volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")
    return vol


@router.put("/volumes/{volume_number}", response_model=StatusResponse)
async def update_volume(novel_id: str, volume_number: int, request: VolumeUpdateRequest):
    service = get_volume_service()
    updated = await service.update_volume(
        novel_id, volume_number, **request.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Volume not found")
    return {"status": "updated"}
```

- [ ] **Step 3: 在 `src/api/routes/__init__.py` 注册 volumes_router**

将 `from .volumes import router as volumes_router` 添加到导入，以及 `"volumes_router"` 添加到 `__all__`。

- [ ] **Step 4: 在 `src/api/main.py` 注册 volumes_router**

```python
app.include_router(volumes_router)
```

- [ ] **Step 5: 从 `NovelManager` 中删除 volume 相关方法**

删除 `NovelManager` 中以下方法：
- `list_volumes`
- `get_volume`
- `create_volume`
- `update_volume`

- [ ] **Step 6: 从 `projects.py` 中删除 volume 相关路由**

删除 `projects.py` 中：
- `list_volumes`
- `get_volume`
- `update_volume`

同步删除 `VolumeUpdateRequest` 类以及 `VolumeResponse` 的 import（如果不再被引用）。

- [ ] **Step 7: 运行测试确认**

```bash
poetry run pytest tests/ --tb=short -q 2>&1 | tail -10
```

---

### Task 3: 拆章节 — ChapterService + routes/chapters.py

**Files:**
- Create: `src/api/services/chapter_service.py`
- Create: `src/api/routes/chapters.py`
- Modify: `src/api/routes/__init__.py`
- Modify: `src/api/main.py`

> 从 NovelManager 中移出：list_chapters, list_chapters_preview, get_chapter_tail, get_chapter, update_chapter, delete_chapter, delete_failed_chapters, fix_volume_numbers
>
> 从 NovelManager 中移出版本管理：create_chapter_version, list_chapter_versions, get_chapter_version, rollback_chapter_version, activate_chapter_version, compare_chapter_versions
>
> 从 projects.py 中移出：ChapterUpdateRequest, CreateVersionRequest, RewriteRequest + 对应的路由

- [ ] **Step 1: 创建 `src/api/services/chapter_service.py`**

```python
"""章节管理服务"""

import structlog
from sqlalchemy import func, select

from src.api.models.db_models import Chapter, ChapterVersion, Novel
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class ChapterService:
    """章节（Chapter）的 CRUD 及版本管理"""

    async def list_chapters(self, novel_id: str) -> list[dict]:
        """列出小说所有章节（不含正文）"""
        async with get_db_session() as session:
            stmt = (
                select(Chapter)
                .where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number)
            )
            result = await session.execute(stmt)
            chapters = result.scalars().all()
            return [self._chapter_summary(c) for c in chapters]

    # ... 后续步骤逐个添加方法
```

- [ ] **后续 Step:** 逐个将 NovelManager 中的章节方法迁移过来，并在 `routes/chapters.py` 中创建对应路由。

- **迁移方法清单：**
  - `list_chapters` / `list_chapters_preview`
  - `get_chapter_tail` / `get_chapter`
  - `update_chapter` / `delete_chapter` / `delete_failed_chapters`
  - `fix_volume_numbers`
  - `create_chapter_version` / `list_chapter_versions`
  - `get_chapter_version` / `rollback_chapter_version`
  - `activate_chapter_version` / `compare_chapter_versions`

- **迁移路由清单（从 projects.py）：**
  - `GET /{novel_id}/chapters`
  - `GET /{novel_id}/chapters/{chapter_number}`
  - `PUT /{novel_id}/chapters/{chapter_number}`
  - `DELETE /{novel_id}/chapters/cleanup`
  - `DELETE /{novel_id}/chapters/{chapter_number}`
  - `POST /{novel_id}/chapters/{chapter_number}/rewrite`
  - `GET /{novel_id}/chapters/{chapter_number}/versions`
  - `GET /{novel_id}/chapters/{chapter_number}/versions/compare`
  - `GET /{novel_id}/chapters/{chapter_number}/versions/{version_number}`
  - `POST /{novel_id}/chapters/{chapter_number}/versions`
  - `POST /{novel_id}/chapters/{chapter_number}/versions/{version_number}/rollback`
  - `POST /{novel_id}/chapters/{chapter_number}/versions/{version_number}/activate`
  - `GET /{novel_id}/chapters/{chapter_number}/blueprint`
  - `PUT /{novel_id}/chapters/{chapter_number}/blueprint`
  - `POST /{novel_id}/chapters/{chapter_number}/blueprint/generate`
  - `POST /{novel_id}/chapters/{chapter_number}/targeted-rewrite`
  - `POST /{novel_id}/chapters/{chapter_number}/auto-improve`

- [ ] **Last Step: 从 NovelManager 和 projects.py 中删除已迁移的代码**

- [ ] **运行测试确认**

```bash
poetry run pytest tests/ --tb=short -q 2>&1 | tail -10
```

---

### Task 4: 拆角色 — CharacterService + routes/characters.py

**Files:**
- Create: `src/api/services/character_service.py`
- Create: `src/api/routes/characters.py`
- Modify: `src/api/routes/__init__.py`
- Modify: `src/api/main.py`

> 从 NovelManager 中移出：list_characters, create_character, get_character_by_name, update_character, delete_character
> 从 projects.py 中移出对应的路由

- [ ] **Step 1: 创建 CharacterService 并迁移 5 个方法**

- [ ] **Step 2: 创建 routes/characters.py 并迁移路由**

- [ ] **Step 3: 注册到 __init__.py + main.py**

- [ ] **Step 4: 从 NovelManager 和 projects.py 中删除**

- [ ] **Step 5: 运行测试确认**

---

### Task 5: 拆世界观 — WorldService + routes/world.py

**Files:**
- Create: `src/api/services/world_service.py`
- Create: `src/api/routes/world.py`
- Modify: `src/api/routes/__init__.py`
- Modify: `src/api/main.py`

> 从 NovelManager 中移出：get_world_setting, upsert_world_setting, list_power_systems, create_power_system, update_power_system, delete_power_system
> 从 projects.py 中移出对应的路由

- [ ] **Step 1: 创建 WorldService 并迁移 6 个方法**

- [ ] **Step 2: 创建 routes/world.py 并迁移路由**

- [ ] **Step 3: 注册**

- [ ] **Step 4: 从 NovelManager 和 projects.py 中删除**

- [ ] **Step 5: 运行测试确认**

---

### Task 6: 瘦身 NovelManager + 测试

**Files:**
- Modify: `src/api/services/novel_manager.py`
- Modify: `src/api/services/__init__.py`

> 经过 Task 2-5，NovelManager 只剩下 Novel CRUD 方法（create_novel, get_novel, list_novels, update_novel, delete_novel, _novel_to_dict, _novel_summary）

- [ ] **Step 1: 验证 NovelManager 剩余方法**

```bash
grep -n "^\s*\(async def \|def " src/api/services/novel_manager.py
```

确认只剩下 7 个方法（5 个 Novel CRUD + 2 个辅助方法）。

- [ ] **Step 2: 检查 `get_novel_manager()` 是否被多处引用**

```bash
grep -l "get_novel_manager" src/ --include="*.py"
```

如果引用较多（生成器、对话服务等）且它们只用了 Novel CRUD 方法，则无需更改。如果引用了已迁移的方法（应已由 Task 2-5 更新），确保全部已改为新的 service 调用。

- [ ] **Step 3: 运行测试确认不移除失败**

```bash
poetry run pytest tests/ --tb=short -q 2>&1 | tail -10
```

---

### Task 7: 清理 projects.py + novels.py 的路由重叠加

**Files:**
- Modify: `src/api/routes/projects.py`
- Modify: `src/api/routes/novels.py`

> 经过 Task 2-5，projects.py 只剩 Novel 基础 CRUD + 生成触发 + 生成卷/章节触发 的路由。
> novels.py 同样有 `GET /api/v1/novels` 路由作为任务管理入口，但不冲突，只是职能边界模糊。

- [ ] **Step 1: 确认 projects.py 剩余路由**

```bash
grep -n "@router\." src/api/routes/projects.py
```

- [ ] **Step 2: 删去 projects.py 中不再需要的 import**

检查 `projects.py` 的 import，删除不再使用的（如 `VolumeResponse`, `ChapterResponse`, `CreateVersionRequest`, `RewriteRequest` 等）。

- [ ] **Step 3: 确认 novels.py 不需要调整**

`novels.py` 前缀为 `/api/v1/novels`，`projects.py` 为 `/api/v1/projects`，路径不同，没有冲突。

- [ ] **Step 4: 运行测试确认**

```bash
poetry run pytest tests/ --tb=short -q 2>&1 | tail -10
```

---

### Task 8: 全局验证 + 清理

**Files:**
- Run: full test suite

- [ ] **Step 1: 全量测试**

```bash
poetry run pytest tests/ -v --tb=short 2>&1 | tail -40
```

对比 Task 1 记录的 baseline，确保没有测试倒退。

- [ ] **Step 2: 检查未使用的 import**

```bash
poetry run ruff check src/ --select=F401 2>&1
```

清理未使用的 import。

- [ ] **Step 3: 格式化代码**

```bash
poetry run ruff format src/
```

- [ ] **Step 4: 检查类型**

```bash
poetry run mypy src/ 2>&1 | tail -20
```

- [ ] **Step 5: 最终确认**

```bash
poetry run pytest tests/ -v --tb=short 2>&1
```

---

## 新文件总览

| 文件 | 来源 | 迁移方法数 |
|------|------|-----------|
| `src/api/services/volume_service.py` | NovelManager → VolumeService | 4 |
| `src/api/services/chapter_service.py` | NovelManager → ChapterService | ~16 |
| `src/api/services/character_service.py` | NovelManager → CharacterService | 5 |
| `src/api/services/world_service.py` | NovelManager → WorldService | 6 |
| `src/api/routes/volumes.py` | projects.py → volumes.py | 3 路由 |
| `src/api/routes/chapters.py` | projects.py → chapters.py | ~17 路由 |
| `src/api/routes/characters.py` | projects.py → characters.py | 4 路由 |
| `src/api/routes/world.py` | projects.py → world.py | 6 路由 |

## 风险点

1. **BlueprintService / RewriteLoopService 的循环依赖：** 它们在项目中引用 `get_novel_manager`，重构后如果只引用了 Novel CRUD，可以保持引用不变；如果引用了已迁移的方法，需要改成新的 service。
2. **`novel_generator.py` 中的引用：** 检查是否直接调用了 `NovelManager.list_chapters` 等方法，需改为 `ChapterService` 调用。
3. **`novels.py` 的路由冲突：** `novels.py` 也包含 `GET /{novel_id}/quality-report` 等端点，以 `novel_id` 为路径参数。`projects.py` 和 `novels.py` 前缀不同，不会冲突，但 `/api/v1/novels` 和 `/api/v1/projects` 语义上高度重叠。本次不调整 `novels.py`。
4. **不破坏 novels.py 的 `tasks_router`：** `novels.py` 里还定义了一个 `tasks_router = APIRouter(...)` 作为独立导出，`__init__.py` 中有 `from .novels import tasks_router`。重构时不要删除或误改。

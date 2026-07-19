"""共享鉴权工具：子路由通过 novel_id 校验当前用户是否 owner。

解决 P0-2：chapters/world/outline/characters 等子路由缺鉴权，
攻击者可读写他人的 novel 数据。

放在 src/api/ 层（而非 core/security），因为它依赖 novel_manager（api 层 service），
避免 core→api 层边界违规。

用法（子路由端点加 owner 校验）：
    from src.api.owner_guard import verify_novel_owner

    @router.get("/{novel_id}/chapters")
    async def list_chapters(
        novel_id: str,
        current_user: User = Depends(get_current_user),
    ):
        await verify_novel_owner(novel_id, current_user)
        ...
"""

from fastapi import HTTPException

from src.api.services.content.novel_manager import get_novel_manager
from src.core.auth_models import User


async def verify_novel_owner(novel_id: str, current_user: User) -> dict:
    """校验 novel 存在且 current_user 是其 owner。

    Args:
        novel_id: 小说 ID
        current_user: 当前登录用户

    Returns:
        novel dict（owner 校验通过）

    Raises:
        HTTPException 404: novel 不存在
        HTTPException 403: 当前用户非 owner
    """
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    if novel.get("owner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return novel


async def verify_task_owner(task_id: str, current_user: User) -> dict:
    """校验 task 存在且 current_user 是其 owner。

    历史任务 owner_id 为 NULL（迁移回填前的遗留）不得默认授权给普通用户：
    NULL != current_user.id 必然为真 → 403。管理员由调用方自行放行（见 require_admin_user）。

    Raises:
        HTTPException 404: task 不存在
        HTTPException 403: 当前用户非 owner（含 owner_id IS NULL 的历史任务）
    """
    from src.api.services.tasks.task_manager import get_task_manager

    manager = get_task_manager()
    task = await manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("owner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return task

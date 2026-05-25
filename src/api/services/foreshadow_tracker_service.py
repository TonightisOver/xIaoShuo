"""伏笔追踪服务

负责追踪小说中的伏笔种下与回收情况，
提供伏笔生命周期管理和悬挂伏笔检测。
"""

from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import StoryBible
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class ForeshadowTrackerService:
    """伏笔追踪服务"""

    async def track_foreshadows(
        self, novel_id: str
    ) -> dict[str, Any]:
        """Track all foreshadows in a novel.

        Args:
            novel_id: Novel ID

        Returns:
            Foreshadow tracking result dict
        """
        async with get_db_session() as session:
            # Get story bible
            stmt = select(StoryBible).where(StoryBible.novel_id == novel_id)
            result = await session.execute(stmt)
            bible = result.scalar_one_or_none()

            if not bible:
                return {
                    "novel_id": novel_id,
                    "total_foreshadows": 0,
                    "planted": [],
                    "resolved": [],
                    "dangling": [],
                    "resolution_rate": 0.0,
                }

            # Parse foreshadowing list from story bible
            foreshadowing_list = bible.foreshadowing_list or []
            unresolved_hooks = bible.unresolved_hooks or []

            # Categorize foreshadows
            planted = []
            resolved = []
            dangling = []

            for fs in foreshadowing_list:
                fs_entry = {
                    "name": fs.get("name", ""),
                    "description": fs.get("description", ""),
                    "planted_chapter": fs.get("planted_chapter"),
                    "resolved_chapter": fs.get("resolved_chapter"),
                    "status": fs.get("status", "active"),
                }

                if fs.get("resolved_chapter") or fs.get("status") == "resolved":
                    resolved.append(fs_entry)
                else:
                    planted.append(fs_entry)

            # Add unresolved hooks as dangling
            for hook in unresolved_hooks:
                dangling.append({
                    "name": hook.get("name", hook.get("hook", "")),
                    "description": hook.get("description", ""),
                    "planted_chapter": hook.get("chapter"),
                    "resolved_chapter": None,
                    "status": "dangling",
                })

            # Calculate resolution rate
            total = len(planted) + len(resolved) + len(dangling)
            resolution_rate = len(resolved) / total if total > 0 else 0.0

            return {
                "novel_id": novel_id,
                "total_foreshadows": total,
                "planted": planted,
                "resolved": resolved,
                "dangling": dangling,
                "resolution_rate": round(resolution_rate, 3),
            }

    async def get_dangling_foreshadows(
        self, novel_id: str
    ) -> list[dict[str, Any]]:
        """Get all dangling (unresolved) foreshadows.

        Args:
            novel_id: Novel ID

        Returns:
            List of dangling foreshadow dicts
        """
        result = await self.track_foreshadows(novel_id)
        return result.get("dangling", [])

    async def check_foreshadow_health(
        self, novel_id: str
    ) -> dict[str, Any]:
        """Check health of foreshadow management.

        Args:
            novel_id: Novel ID

        Returns:
            Health check result
        """
        tracking = await self.track_foreshadows(novel_id)

        total = tracking["total_foreshadows"]
        dangling = len(tracking["dangling"])
        resolution_rate = tracking["resolution_rate"]

        # Health assessment
        issues = []
        if dangling > 10:
            issues.append(f"悬挂伏笔过多: {dangling} 个（建议控制在 10 个以内）")
        if total > 0 and resolution_rate < 0.3:
            issues.append(f"伏笔回收率过低: {resolution_rate:.0%}（建议 > 30%）")
        if total == 0:
            issues.append("未发现伏笔，建议增加伏笔以提升故事深度")

        health_status = "good" if not issues else ("warning" if len(issues) <= 2 else "critical")

        return {
            "novel_id": novel_id,
            "health_status": health_status,
            "total_foreshadows": total,
            "dangling_count": dangling,
            "resolution_rate": resolution_rate,
            "issues": issues,
        }


_foreshadow_tracker_service: ForeshadowTrackerService | None = None


def get_foreshadow_tracker_service() -> ForeshadowTrackerService:
    """Get or create ForeshadowTrackerService singleton."""
    global _foreshadow_tracker_service
    if _foreshadow_tracker_service is None:
        _foreshadow_tracker_service = ForeshadowTrackerService()
    return _foreshadow_tracker_service

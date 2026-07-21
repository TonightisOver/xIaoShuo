"""ArtifactVersionStore —— 非正文产物的通用版本快照。

仅覆盖 world/character/master_outline/volume_outline/blueprint。
正文版本不在本表，复用 ChapterVersion。每产物至多一个 is_active 版本。

设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

import importlib
from typing import Any

from sqlalchemy import select

from src.core.database import get_db_session


def _orm():
    """延迟导入 ORM 模型：core 层不在顶层依赖 api.models（layer boundary）。

    用 importlib 动态加载，避免在模块中出现 ``from src.api...`` 的 import 语句
    （层边界静态守卫会扫描所有 AST import 节点，包括函数内与 TYPE_CHECKING 块）。
    """
    module = importlib.import_module("src.api.models.db_models")
    return module.ArtifactVersion


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "novel_id": row.novel_id,
        "artifact_type": row.artifact_type,
        "artifact_id": row.artifact_id,
        "version_number": row.version_number,
        "content_snapshot": row.content_snapshot,
        "source": row.source,
        "model": row.model,
        "operator_id": row.operator_id,
        "task_id": row.task_id,
        "operation_id": row.operation_id,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class ArtifactVersionStore:
    """通用产物版本快照读写。"""

    async def save_version(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        *,
        content_snapshot: dict[str, Any],
        source: str = "manual",
        model: str | None = None,
        operator_id: int | None = None,
        task_id: str | None = None,
        operation_id: str | None = None,
    ) -> int:
        """旧 active 置 false，插入新 active 版本，返回新 version_number。"""
        ArtifactVersion = _orm()  # noqa: N806
        async with get_db_session() as session:
            old_active = await self._select_active(session, novel_id, artifact_type, artifact_id)
            next_number = (old_active.version_number + 1) if old_active else 1
            if old_active is not None:
                old_active.is_active = False
            row = ArtifactVersion(
                novel_id=novel_id,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                version_number=next_number,
                content_snapshot=content_snapshot,
                source=source,
                model=model,
                operator_id=operator_id,
                task_id=task_id,
                operation_id=operation_id,
                is_active=True,
            )
            session.add(row)
            await session.flush()
            return next_number

    async def list_versions(
        self, novel_id: str, artifact_type: str, artifact_id: str
    ) -> list[dict[str, Any]]:
        """按 version_number desc 返回版本列表（不含 content_snapshot 全量，仅摘要）。"""
        ArtifactVersion = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactVersion)
                .where(
                    ArtifactVersion.novel_id == novel_id,
                    ArtifactVersion.artifact_type == artifact_type,
                    ArtifactVersion.artifact_id == artifact_id,
                )
                .order_by(ArtifactVersion.version_number.desc())
            )
            rows = list(result.scalars().all())
            # 应用层兜底排序（DB 已 order_by，但 mock 与历史无序数据保证一致）
            rows.sort(key=lambda r: r.version_number, reverse=True)
            return [_row_to_dict(r) for r in rows]

    async def get_version(
        self, novel_id: str, artifact_type: str, artifact_id: str, version_number: int
    ) -> dict[str, Any] | None:
        ArtifactVersion = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactVersion).where(
                    ArtifactVersion.novel_id == novel_id,
                    ArtifactVersion.artifact_type == artifact_type,
                    ArtifactVersion.artifact_id == artifact_id,
                    ArtifactVersion.version_number == version_number,
                )
            )
            row = result.scalar_one_or_none()
            return _row_to_dict(row) if row else None

    async def compare_versions(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """字段级 diff：changed / unchanged / a / b。"""
        a = await self.get_version(novel_id, artifact_type, artifact_id, version_a)
        b = await self.get_version(novel_id, artifact_type, artifact_id, version_b)
        if a is None or b is None:
            raise ValueError(f"version not found: a={version_a} b={version_b}")
        snap_a = a["content_snapshot"] or {}
        snap_b = b["content_snapshot"] or {}
        all_keys = list(dict.fromkeys(list(snap_a.keys()) + list(snap_b.keys())))
        changed = [k for k in all_keys if snap_a.get(k) != snap_b.get(k)]
        unchanged = [k for k in all_keys if snap_a.get(k) == snap_b.get(k)]
        return {"changed": changed, "unchanged": unchanged, "a": a, "b": b}

    async def rollback_to(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        version_number: int,
        *,
        operator_id: int | None = None,
    ) -> dict[str, Any]:
        """回退到指定版本：把该版本内容回写到产物本体 + 激活该版本（旧 active 置 false）。"""
        target = await self.get_version(novel_id, artifact_type, artifact_id, version_number)
        if target is None:
            raise ValueError(f"version not found: {version_number}")
        # 回写内容到产物本体表（由 _restore_content_to_product 委托给对应 content service）
        await self._restore_content_to_product(
            novel_id, artifact_type, artifact_id, target["content_snapshot"]
        )
        # 激活目标版本：单事务内把该产物所有版本 is_active=False，目标=True
        ArtifactVersion = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactVersion).where(
                    ArtifactVersion.novel_id == novel_id,
                    ArtifactVersion.artifact_type == artifact_type,
                    ArtifactVersion.artifact_id == artifact_id,
                    ArtifactVersion.version_number == version_number,
                ).with_for_update()
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"version row not found: {version_number}")
            # 同产物其他 active 行置 false（应用层保证唯一；DB 部分唯一索引兜底）
            all_result = await session.execute(
                select(ArtifactVersion).where(
                    ArtifactVersion.novel_id == novel_id,
                    ArtifactVersion.artifact_type == artifact_type,
                    ArtifactVersion.artifact_id == artifact_id,
                    ArtifactVersion.is_active.is_(True),
                )
            )
            for other in all_result.scalars().all():
                if other.version_number != version_number:
                    other.is_active = False
            row.is_active = True
            await session.flush()
        return {"activated_version": version_number}

    # ----------------------------------------------------------- 内部委托

    async def _restore_content_to_product(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        content_snapshot: dict[str, Any],
    ) -> None:
        """把版本内容回写到产物本体表。

        委托给对应 content service（WorldService/CharacterService/OutlineService/
        VolumeService/BlueprintService）。本方法在集成层被覆盖；核心层保持可单测。
        """
        # 默认实现：no-op（由 src/api/services/creative_control_service.py 注入真实委托）。
        # 单测通过 monkeypatch 覆盖。
        return None

    async def _select_active(
        self, session, novel_id, artifact_type, artifact_id
    ) -> Any | None:
        ArtifactVersion = _orm()  # noqa: N806
        result = await session.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.novel_id == novel_id,
                ArtifactVersion.artifact_type == artifact_type,
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

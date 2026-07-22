"""章节管理服务"""

import difflib
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update

from src.api.models.db_models import Chapter, ChapterVersion
from src.core.database import get_db_session
from src.core.exceptions import ArtifactConflictError, StaleChapterVersionError

logger = structlog.get_logger(__name__)


def chapter_idem_key(operation_id: str, kind: str, chapter_number: int) -> str:
    """构造可重放写操作的确定性幂等键。

    格式：``{operation_id}:{kind}:{chapter_number}``（见设计 §三 幂等键表）。
    kind 取自调用点语义：``baseline``（创建 baseline 非活跃版本）、``activate``
    （创建激活候选版本）。同一 operation_id + chapter 下，相同 kind 重放命中已存在
    版本，不同 kind 各自新建。Task 6 的 generate_volume_chapters 接入检查点时调用。
    """
    return f"{operation_id}:{kind}:{chapter_number}"


class ChapterService:
    """章节（Chapter）的 CRUD 及版本管理"""

    async def list_chapters(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number)
            )
            return [{"id": c.id, "chapter_number": c.chapter_number,
                     "volume_number": c.volume_number,
                     "title": c.title, "content": c.content,
                     "word_count": c.word_count, "status": c.status,
                     "updated_at": c.updated_at}
                    for c in result.scalars().all()]

    async def list_chapters_preview(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(
                    Chapter.id,
                    Chapter.chapter_number,
                    Chapter.volume_number,
                    Chapter.title,
                    Chapter.word_count,
                    Chapter.status,
                    Chapter.chapter_type,
                    Chapter.updated_at,
                )
                .where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number)
            )
            return [
                {
                    "id": row.id,
                    "chapter_number": row.chapter_number,
                    "volume_number": row.volume_number,
                    "title": row.title,
                    "word_count": row.word_count,
                    "status": row.status,
                    "chapter_type": row.chapter_type,
                    "updated_at": row.updated_at,
                }
                for row in result.all()
            ]

    async def get_chapter_tail(
        self, novel_id: str, chapter_number: int, tail_chars: int = 500
    ) -> str:
        async with get_db_session() as session:
            result = await session.execute(
                select(func.substr(Chapter.content, -tail_chars))
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .order_by(Chapter.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none() or ""

    async def get_chapter(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                ).order_by(Chapter.id.desc()).limit(1)
            )
            c = result.scalar_one_or_none()
            if not c:
                return None
            return {"id": c.id, "novel_id": c.novel_id,
                    "chapter_number": c.chapter_number,
                    "volume_number": c.volume_number,
                    "title": c.title, "content": c.content,
                    "word_count": c.word_count, "status": c.status,
                    "updated_at": c.updated_at}

    async def update_chapter(self, novel_id: str, chapter_number: int,
                             **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                ).order_by(Chapter.id.desc()).limit(1)
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            for k, v in kwargs.items():
                if hasattr(ch, k) and v is not None:
                    setattr(ch, k, v)
            if "content" in kwargs and kwargs["content"]:
                ch.word_count = len(kwargs["content"])
            ch.status = "edited"
            ch.updated_at = datetime.now(UTC)
        return True

    async def update_state_delta(
        self, novel_id: str, chapter_number: int, state_delta: dict
    ) -> bool:
        """更新章节的结构化状态增量（state_delta），不改变 chapter.status。

        Returns:
            True 若章节存在并更新成功，False 若章节不存在
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            ch.state_delta = state_delta
            ch.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def update_quality_status(
        self, novel_id: str, chapter_number: int, status: str
    ) -> bool:
        """更新章节的质量门禁状态（quality_status），不改变 chapter.status。

        quality_status 取值: verified / unverified / consistency_blocked / failed
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            ch.quality_status = status
            ch.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def delete_chapter(self, novel_id: str, chapter_number: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            await session.delete(ch)
        return True

    async def delete_failed_chapters(self, novel_id: str, min_words: int = 100) -> int:
        """批量删除 word_count < min_words 的失败章节"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.word_count < min_words,
                )
            )
            failed = result.scalars().all()
            for ch in failed:
                await session.delete(ch)
            return len(failed)

    # --- Chapter Versions ---

    async def create_chapter_version(
        self,
        novel_id: str,
        chapter_number: int,
        content: str,
        source: str = "manual",
        rewrite_instruction: str | None = None,
        quality_score: float | None = None,
        model_name: str | None = None,
        prompt_summary: str | None = None,
        diff_from_previous: str | None = None,
        kg_conflicts: dict | None = None,
        user_notes: str | None = None,
        is_active: bool = False,
        *,
        idempotency_key: str | None = None,
        quality_status: str | None = None,
    ) -> int:
        """创建章节版本快照。

        仅当 is_active=True 时，才清零同章其它版本的 is_active 并把内容写回
        Chapter.content / Chapter.word_count；is_active=False 只创建快照，
        不触碰当前活跃正文（供候选择优比较后再决定是否激活）。

        quality_status（可选）：仅当 is_active=True 时，在同一事务内一并写回
        Chapter.quality_status。手动编辑正文走此路径置 `unverified`，保证旧质量
        分数不会被当作新正文的当前分数（设计 §验收8 / 集成点4）。is_active=False
        时忽略此参数（候选快照不影响当前活跃正文的质量状态）。

        幂等（B18）：传入 idempotency_key 时先按键查重，命中已存在版本则直接返回
        其 version_number 而不新建——重试同一可重放写操作不会产生重复版本。
        幂等键来源：baseline 版本用 `{op}:baseline:{n}`，激活候选用 `{op}:activate:{n}`。
        未传 idempotency_key（手动/回滚路径）走原有 max+1 逻辑，每次新建。
        """
        async with get_db_session() as session:
            from src.core.creative_control.control_service import (
                CreativeControlService,
                has_generation_fence,
            )

            if has_generation_fence():
                await CreativeControlService().assert_generation_allowed_in_session(
                    session, novel_id, "chapter", str(chapter_number)
                )
            ch = (
                await session.execute(
                    select(Chapter)
                    .where(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number == chapter_number,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if ch is None:
                raise ValueError("Chapter not found")

            # 幂等查重：命中已存在版本则直接返回其 version_number
            if idempotency_key is not None:
                existing = await session.execute(
                    select(ChapterVersion)
                    .where(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                        ChapterVersion.idempotency_key == idempotency_key,
                    )
                    .with_for_update()
                )
                hit = existing.scalar_one_or_none()
                if hit is not None:
                    if is_active:
                        # baseline 已提交但 checkpoint 尚未推进时，下一次生成可能先
                        # 覆盖 Chapter。命中幂等键必须把真实正文和活跃状态恢复到已提交
                        # 版本，避免 Chapter 与 ChapterVersion 分裂。
                        current_active = (
                            await session.execute(
                                select(ChapterVersion)
                                .where(
                                    ChapterVersion.novel_id == novel_id,
                                    ChapterVersion.chapter_number == chapter_number,
                                    ChapterVersion.is_active.is_(True),
                                )
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if (
                            current_active is not None
                            and current_active.version_number != hit.version_number
                        ):
                            # checkpoint 重放期间若已有人工/其他操作激活的新版本，
                            # 不能静默回退到旧 baseline。
                            raise StaleChapterVersionError(
                                novel_id,
                                chapter_number,
                                hit.version_number,
                                current_active.version_number,
                            )
                        hit.is_active = True
                        ch.content = hit.content or ""
                        ch.word_count = hit.word_count
                        if quality_status is not None:
                            ch.quality_status = quality_status
                        ch.updated_at = datetime.now(UTC)
                    return hit.version_number

            max_ver_res = await session.execute(
                select(func.max(ChapterVersion.version_number)).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
            )
            max_ver = max_ver_res.scalar_one_or_none() or 0
            new_version = max_ver + 1

            word_count = len(content)

            version = ChapterVersion(
                novel_id=novel_id,
                chapter_number=chapter_number,
                version_number=new_version,
                content=content,
                word_count=word_count,
                source=source,
                rewrite_instruction=rewrite_instruction,
                quality_score=quality_score,
                model_name=model_name,
                prompt_summary=prompt_summary,
                diff_from_previous=diff_from_previous,
                kg_conflicts=kg_conflicts,
                user_notes=user_notes,
                is_active=is_active,
                idempotency_key=idempotency_key,
                created_at=datetime.now(UTC),
            )
            if is_active:
                await session.execute(
                    ChapterVersion.__table__.update()
                    .where(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                    )
                    .values(is_active=False)
                )
                # 部分唯一索引要求任意时刻最多一个 active；先提交清零到 DB，
                # 再把新 active 版本加入 session，避免 autoflush 先插入而冲突。
                await session.flush()
                ch.content = content
                ch.word_count = word_count
                if quality_status is not None:
                    ch.quality_status = quality_status
                ch.updated_at = datetime.now(UTC)
            session.add(version)
            await session.flush()
            return new_version

    async def finalize_chapter_version(
        self,
        novel_id: str,
        chapter_number: int,
        *,
        expected_active_version: int | None,
        selected_version: int,
        quality_status: str | None = None,
        quality_score: float | None = None,
        quality_scores: dict | None = None,
    ) -> bool:
        """原子激活指定章节版本（B10）。

        单事务内：
        1. with_for_update 锁 Chapter 行 + 该章所有 ChapterVersion 行（行锁防并发激活）。
        2. 乐观锁校验：当前活跃版本号必须 == expected_active_version，否则抛
           StaleChapterVersionError（调用方基于过期页面覆盖新修改）。
           expected_active_version=None 表示从无活跃态首次激活，要求当前确实无活跃版本。
        3. 仅激活 selected_version，清零其余版本 is_active。
        4. 写回 Chapter.content / word_count / quality_status（若传入）。

        幂等：若 selected_version 已是活跃且 expected 匹配，直接返回 True（恢复场景）。
        """
        async with get_db_session() as session:
            ch_res = await session.execute(
                select(Chapter)
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .with_for_update()
            )
            ch = ch_res.scalar_one_or_none()
            if not ch:
                raise ValueError("Chapter not found")

            vers_res = await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .with_for_update()
            )
            versions = vers_res.scalars().all()

            current_active = next(
                (v.version_number for v in versions if v.is_active), None
            )
            if current_active != expected_active_version:
                raise StaleChapterVersionError(
                    novel_id, chapter_number, expected_active_version, current_active
                )

            target = next(
                (v for v in versions if v.version_number == selected_version), None
            )
            if target is None:
                return False

            # 已是活跃且 expected 匹配 → 幂等返回，不重复写回
            already_active = target.is_active
            for v in versions:
                v.is_active = False
            await session.flush()
            target.is_active = True

            if target.content:
                ch.content = target.content
                ch.word_count = target.word_count
            if quality_status is not None:
                ch.status = quality_status
            if not already_active or quality_score is not None:
                target.quality_score = quality_score
            if quality_scores is not None:
                target.quality_scores = quality_scores
            ch.updated_at = datetime.now(UTC)
            await session.flush()
            return True

    async def list_chapter_versions(self, novel_id: str, chapter_number: int) -> list[dict]:
        """返回版本列表（不含 content），按 version_number 降序。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .order_by(ChapterVersion.version_number.desc())
            )
            return [
                {
                    "id": v.id,
                    "version_number": v.version_number,
                    "word_count": v.word_count,
                    "source": v.source,
                    "rewrite_instruction": v.rewrite_instruction,
                    "quality_score": v.quality_score,
                    "quality_scores": v.quality_scores,
                    "model_name": v.model_name,
                    "is_active": v.is_active,
                    "created_at": v.created_at,
                }
                for v in result.scalars().all()
            ]

    async def get_chapter_version(
        self, novel_id: str, chapter_number: int, version_number: int
    ) -> dict | None:
        """返回单个版本完整内容。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                    ChapterVersion.version_number == version_number,
                )
            )
            v = result.scalar_one_or_none()
            if not v:
                return None
            return {
                "id": v.id,
                "version_number": v.version_number,
                "content": v.content,
                "word_count": v.word_count,
                "source": v.source,
                "rewrite_instruction": v.rewrite_instruction,
                "quality_score": v.quality_score,
                "model_name": v.model_name,
                "prompt_summary": v.prompt_summary,
                "diff_from_previous": v.diff_from_previous,
                "kg_conflicts": v.kg_conflicts,
                "user_notes": v.user_notes,
                "is_active": v.is_active,
                "idempotency_key": v.idempotency_key,
                "created_at": v.created_at,
            }

    async def get_active_chapter_version(
        self, novel_id: str, chapter_number: int
    ) -> dict | None:
        """返回当前活跃版本及其操作幂等键，供恢复流程校验版本所有权。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                    ChapterVersion.is_active.is_(True),
                )
            )
            version = result.scalar_one_or_none()
            if version is None:
                return None
            return {
                "version_number": version.version_number,
                "content": version.content,
                "word_count": version.word_count,
                "source": version.source,
                "quality_score": version.quality_score,
                "quality_scores": version.quality_scores,
                "idempotency_key": version.idempotency_key,
            }

    async def rollback_chapter_version(
        self, novel_id: str, chapter_number: int, version_number: int
    ) -> int | None:
        """将指定版本内容写回 Chapter.content，并创建 source=rollback 的新版本。"""
        target = await self.get_chapter_version(novel_id, chapter_number, version_number)
        if not target:
            return None
        new_version = await self.create_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            content=target["content"] or "",
            source="rollback",
            rewrite_instruction=f"回滚自版本 {version_number}",
        )
        return new_version

    async def activate_chapter_version(
        self,
        novel_id: str,
        chapter_number: int,
        version_number: int,
        *,
        expected_active_version: int | None = None,
    ) -> bool | None:
        """将指定版本设为活跃版本，更新章节正文。

        若传入 expected_active_version，则先校验当前活跃版本号一致，否则抛
        ArtifactConflictError（路由映射 HTTP 409），防止基于过期页面覆盖新修改。
        未传 expected_active_version 时走向后兼容路径，不做乐观锁校验。
        """
        async with get_db_session() as session:
            # 乐观锁校验（可选）
            if expected_active_version is not None:
                active_res = await session.execute(
                    select(ChapterVersion.version_number).where(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                        ChapterVersion.is_active.is_(True),
                    )
                )
                current_active = active_res.scalar_one_or_none()
                if current_active != expected_active_version:
                    raise ArtifactConflictError(
                        novel_id, "chapter_version", str(chapter_number),
                        expected_active_version, current_active or 0,
                    )

            result = await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                    ChapterVersion.version_number == version_number,
                )
            )
            target = result.scalar_one_or_none()
            if not target:
                return None

            for v in (await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
            )).scalars().all():
                v.is_active = (v.version_number == version_number)

            ch_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            ch = ch_res.scalar_one_or_none()
            if ch and target.content:
                ch.content = target.content
                ch.word_count = target.word_count
                ch.updated_at = datetime.now(UTC)

        return True

    async def compare_chapter_versions(
        self, novel_id: str, chapter_number: int, v1: int, v2: int
    ) -> dict | None:
        """对比两个版本，返回两者内容和基本 diff 信息。"""
        ver1 = await self.get_chapter_version(novel_id, chapter_number, v1)
        ver2 = await self.get_chapter_version(novel_id, chapter_number, v2)
        if not ver1 or not ver2:
            return None

        content1 = ver1["content"] or ""
        content2 = ver2["content"] or ""
        diff = list(difflib.unified_diff(
            content1.splitlines(keepends=True),
            content2.splitlines(keepends=True),
            fromfile=f"v{v1}",
            tofile=f"v{v2}",
            lineterm="",
        ))
        return {
            "v1": {"version_number": v1, "word_count": ver1["word_count"], "source": ver1["source"], "created_at": ver1["created_at"]},
            "v2": {"version_number": v2, "word_count": ver2["word_count"], "source": ver2["source"], "created_at": ver2["created_at"]},
            "diff": "\n".join(diff),
            "word_count_change": ver2["word_count"] - ver1["word_count"],
        }

    async def fix_volume_numbers(self, novel_id: str) -> int:
        """根据卷的 chapter_start/chapter_end 为章节补充 volume_number。"""
        from src.api.services.content.volume_service import get_volume_service
        svc = get_volume_service()
        volumes = await svc.list_volumes(novel_id)
        fixed = 0
        async with get_db_session() as session:
            for vol in volumes:
                ch_start = vol.get("chapter_start")
                ch_end = vol.get("chapter_end")
                vol_num = vol.get("volume_number")
                if ch_start is None or ch_end is None or vol_num is None:
                    continue
                result = await session.execute(
                    update(Chapter)
                    .where(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number >= ch_start,
                        Chapter.chapter_number <= ch_end,
                        Chapter.volume_number.is_(None),
                    )
                    .values(volume_number=vol_num)
                )
                fixed += result.rowcount
        return fixed


_chapter_service: ChapterService | None = None


def get_chapter_service() -> ChapterService:
    global _chapter_service
    if _chapter_service is None:
        _chapter_service = ChapterService()
    return _chapter_service

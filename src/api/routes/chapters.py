"""章节管理 API 路由"""

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.models.responses import ChapterResponse, StatusResponse
from src.api.owner_guard import verify_novel_owner
from src.api.services.content.chapter_service import get_chapter_service
from src.api.services.content.novel_manager import get_novel_manager
from src.core.auth_models import User
from src.core.security.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["chapters"])



class ChapterUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None


class RewriteRequest(BaseModel):
    full_content: str
    selected_text: str = Field(..., min_length=1)
    selection_start: int
    selection_end: int
    instruction: str = Field(..., min_length=1)


class CreateVersionRequest(BaseModel):
    content: str
    source: Literal["manual", "ai_rewrite", "rollback"] = "manual"
    rewrite_instruction: str | None = None


class AutoImproveRequest(BaseModel):
    max_iterations: int = Field(default=3, ge=1, le=5)
    target_score: float = Field(default=0.6, ge=0.3, le=0.9)
    dimensions: list[str] | None = None


class TargetedRewriteRequest(BaseModel):
    rewrite_type: str = Field(..., description="改写类型")
    instruction: str = Field(default="", description="额外改写指令")
    auto_actions: bool = Field(default=False, description="是否自动执行所有改写动作")


class BlueprintUpdateRequest(BaseModel):
    chapter_type: str | None = None
    plot_goal: str | None = None
    hook_design: str | None = None
    foreshadow_actions: list[dict] | None = None
    cliffhanger: str | None = None
    pacing_target: str | None = None
    key_characters: list[str] | None = None
    word_target: int | None = None


class GenerateChaptersRequest(BaseModel):
    chapter_start: int = Field(..., ge=1)
    chapter_end: int = Field(..., ge=1)


# --- Chapter CRUD ---

@router.get("/{novel_id}/chapters")
async def list_chapters(novel_id: str, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    novel = await get_novel_manager().get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    service = get_chapter_service()
    return await service.list_chapters(novel_id)



@router.get("/{novel_id}/chapters/{chapter_number}", response_model=ChapterResponse)
async def get_chapter(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.put("/{novel_id}/chapters/{chapter_number}", response_model=StatusResponse)
async def update_chapter(novel_id: str, chapter_number: int, request: ChapterUpdateRequest, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    updated = await service.update_chapter(
        novel_id, chapter_number, **request.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/chapters/cleanup")
async def cleanup_failed_chapters(novel_id: str, min_words: int = Query(default=100, ge=1), current_user: User = Depends(get_current_user)):
    """批量删除生成失败的章节（word_count < min_words）"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    deleted_count = await service.delete_failed_chapters(novel_id, min_words=min_words)
    return {"deleted_count": deleted_count}


@router.delete("/{novel_id}/chapters/{chapter_number}")
async def delete_chapter(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    deleted = await service.delete_chapter(novel_id, chapter_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "deleted"}


# --- Chapter AI Rewrite ---

@router.post("/{novel_id}/chapters/{chapter_number}/rewrite")
async def rewrite_chapter_segment(novel_id: str, chapter_number: int, request: RewriteRequest, current_user: User = Depends(get_current_user)):
    """对章节中选中的文本片段进行 AI 改写。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    from src.api.services.quality.novel_context_service import NovelContextBuilder
    from src.core.database import get_db_session
    from src.core.llm.chapter_rewriter import rewrite_chapter_segment as do_rewrite

    async with get_db_session() as session:
        ctx = await NovelContextBuilder().build_rewrite_context(
            session, novel_id, chapter_number
        )
    context = {
        "world_setting": ctx.world_setting,
        "chapter_outline": ctx.chapter_outline,
        "prev_chapter_summary": ctx.prev_chapter_summary,
        "next_chapter_summary": ctx.next_chapter_summary,
        "characters": ctx.characters,
        "story_bible": ctx.story_bible,
        "writing_style": ctx.writing_style,
    }

    try:
        rewritten = await do_rewrite(
            novel_id=novel_id,
            chapter_number=chapter_number,
            full_content=request.full_content,
            selected_text=request.selected_text,
            instruction=request.instruction,
            context=context,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="AI rewrite timed out")
    except Exception as e:
        logger.error("rewrite_chapter_segment_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Rewrite failed")

    return {"rewritten_text": rewritten, "original_text": request.selected_text}


# --- Chapter Version Management ---

@router.get("/{novel_id}/chapters/{chapter_number}/versions")
async def list_chapter_versions(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    """返回章节版本列表（不含 content）。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return await service.list_chapter_versions(novel_id, chapter_number)


@router.get("/{novel_id}/chapters/{chapter_number}/versions/compare")
async def compare_chapter_versions(
    novel_id: str, chapter_number: int, v1: int, v2: int, current_user: User = Depends(get_current_user)
):
    """对比两个版本的内容差异。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    result = await service.compare_chapter_versions(novel_id, chapter_number, v1, v2)
    if result is None:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return result


@router.get("/{novel_id}/chapters/{chapter_number}/versions/{version_number}")
async def get_chapter_version(novel_id: str, chapter_number: int, version_number: int, current_user: User = Depends(get_current_user)):
    """返回单个版本完整内容。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    version = await service.get_chapter_version(novel_id, chapter_number, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{novel_id}/chapters/{chapter_number}/versions", status_code=201)
async def create_chapter_version_route(novel_id: str, chapter_number: int, request: CreateVersionRequest, current_user: User = Depends(get_current_user)):
    """手动创建章节版本快照。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    version_number = await service.create_chapter_version(
        novel_id=novel_id,
        chapter_number=chapter_number,
        content=request.content,
        source=request.source,
        rewrite_instruction=request.rewrite_instruction,
    )
    return {"version_number": version_number, "status": "created"}


@router.post("/{novel_id}/chapters/{chapter_number}/versions/{version_number}/rollback")
async def rollback_chapter_version(novel_id: str, chapter_number: int, version_number: int, current_user: User = Depends(get_current_user)):
    """回滚到指定版本。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    new_version = await service.rollback_chapter_version(novel_id, chapter_number, version_number)
    if new_version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "rolled_back", "new_version_number": new_version}


@router.post("/{novel_id}/chapters/{chapter_number}/versions/{version_number}/activate")
async def activate_chapter_version(novel_id: str, chapter_number: int, version_number: int, current_user: User = Depends(get_current_user)):
    """将指定版本设为活跃版本（更新章节正文为该版本内容）。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    result = await service.activate_chapter_version(novel_id, chapter_number, version_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "activated", "version_number": version_number}


@router.post("/{novel_id}/fix-volume-numbers")
async def fix_volume_numbers(novel_id: str, current_user: User = Depends(get_current_user)):
    """根据卷的章节范围为已有章节补充 volume_number。"""
    await verify_novel_owner(novel_id, current_user)
    service = get_chapter_service()
    fixed_count = await service.fix_volume_numbers(novel_id)
    return {"status": "fixed", "chapters_updated": fixed_count}


# --- Blueprint API ---

@router.get("/{novel_id}/chapters/{chapter_number}/blueprint")
async def get_blueprint(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    """获取章节蓝图"""
    await verify_novel_owner(novel_id, current_user)
    from src.api.services.content.blueprint_service import BlueprintService

    service = BlueprintService()
    blueprint = await service.get_blueprint(novel_id, chapter_number)
    if not blueprint:
        raise HTTPException(status_code=404, detail="该章节暂无蓝图")
    return blueprint


@router.put("/{novel_id}/chapters/{chapter_number}/blueprint")
async def update_blueprint(
    novel_id: str, chapter_number: int, request: BlueprintUpdateRequest, current_user: User = Depends(get_current_user)
):
    """用户手动编辑蓝图"""
    await verify_novel_owner(novel_id, current_user)
    from src.api.services.content.blueprint_service import BlueprintService

    service = BlueprintService()
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="无更新字段")
    result = await service.update_blueprint(novel_id, chapter_number, updates)
    return result


@router.post(
    "/{novel_id}/chapters/{chapter_number}/blueprint/generate",
    status_code=201,
)
async def generate_blueprint(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    """触发 LLM 生成蓝图（不触发章节生成）"""
    await verify_novel_owner(novel_id, current_user)
    from sqlalchemy import select

    from src.api.models.db_models import Outline
    from src.api.services.content.blueprint_service import BlueprintService
    from src.core.database import get_db_session

    async with get_db_session() as session:
        stmt = select(Outline).where(
            Outline.novel_id == novel_id,
            Outline.level == "chapter",
            Outline.chapter_number == chapter_number,
        )
        result = await session.execute(stmt)
        outline = result.scalar_one_or_none()

    chapter_outline = (
        outline.content
        if outline
        else {"chapter": chapter_number, "title": f"第{chapter_number}章"}
    )

    service = BlueprintService()
    blueprint = await service.generate_blueprint(
        novel_id, chapter_number, chapter_outline
    )
    return blueprint


# --- Targeted Rewrite API ---

@router.post("/{novel_id}/chapters/{chapter_number}/targeted-rewrite")
async def targeted_rewrite_chapter(
    novel_id: str, chapter_number: int, request: TargetedRewriteRequest, current_user: User = Depends(get_current_user)
):
    """定向改写章节"""
    await verify_novel_owner(novel_id, current_user)
    from src.api.services.quality.novel_context_service import NovelContextBuilder
    from src.core.database import get_db_session
    from src.core.llm.chapter_rewriter import (
        batch_targeted_rewrite,
        targeted_rewrite,
    )

    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if not chapter.get("content"):
        raise HTTPException(status_code=400, detail="章节无内容，无法改写")

    full_content = chapter["content"]

    async with get_db_session() as session:
        ctx = await NovelContextBuilder().build_rewrite_context(
            session, novel_id, chapter_number
        )
    context = {
        "world_setting": ctx.world_setting,
        "chapter_outline": ctx.chapter_outline,
        "prev_chapter_summary": ctx.prev_chapter_summary,
        "next_chapter_summary": ctx.next_chapter_summary,
        "characters": ctx.characters,
        "story_bible": ctx.story_bible,
        "writing_style": ctx.writing_style,
    }

    try:
        if request.auto_actions:
            from src.api.services.content.blueprint_service import BlueprintService

            bp_service = BlueprintService()
            bp = await bp_service.get_blueprint(novel_id, chapter_number)
            actions = (bp or {}).get("rewrite_actions", [])
            if not actions:
                raise HTTPException(
                    status_code=400, detail="蓝图中无改写动作，请先生成质量评估"
                )
            new_content = await batch_targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=full_content,
                actions=actions,
                context=context,
            )
        else:
            new_content = await targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=full_content,
                rewrite_type=request.rewrite_type,
                instruction=request.instruction,
                context=context,
            )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="AI rewrite timed out")
    except Exception as e:
        logger.error("targeted_rewrite_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Targeted rewrite failed")

    new_version = await service.create_chapter_version(
        novel_id=novel_id,
        chapter_number=chapter_number,
        content=new_content,
        source="ai_rewrite",
        rewrite_instruction=request.rewrite_type,
        is_active=True,
    )

    return {
        "new_version_number": new_version,
        "word_count": len(new_content),
        "rewrite_type": request.rewrite_type,
    }


# --- Auto Improve API ---

@router.post("/{novel_id}/chapters/{chapter_number}/auto-improve")
async def auto_improve_chapter(
    novel_id: str, chapter_number: int, request: AutoImproveRequest, current_user: User = Depends(get_current_user)
):
    """自动改善闭环"""
    await verify_novel_owner(novel_id, current_user)
    from src.api.services.quality.rewrite_loop_service import RewriteLoopService

    service = get_chapter_service()
    chapter = await service.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if not chapter.get("content"):
        raise HTTPException(status_code=400, detail="章节无内容，无法改善")

    loop_service = RewriteLoopService()
    try:
        result = await loop_service.auto_improve_chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            max_iterations=request.max_iterations,
            target_score=request.target_score,
            dimensions=request.dimensions,
        )
    except Exception as e:
        logger.error(
            "auto_improve_failed",
            novel_id=novel_id,
            chapter_number=chapter_number,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Auto improve failed: {str(e)}"
        )

    return result

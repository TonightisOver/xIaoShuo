"""导出 API 路由"""

from urllib.parse import quote

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from src.api.models.db_models import Chapter, Novel, Volume
from src.api.models.export_models import (
    ExportFormat,
    ExportRequest,
    ExportScope,
    ExportTemplate,
    TemplateInfo,
    TemplateOptions,
)
from src.api.services.export_service import (
    PRESET_TEMPLATES,
    ChapterData,
    DocxExporter,
    EpubExporter,
    FormatEngine,
    TxtExporter,
)
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["export"])

MIME_TYPES = {
    ExportFormat.txt: "text/plain; charset=utf-8",
    ExportFormat.epub: "application/epub+zip",
    ExportFormat.docx: (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
}

FILE_EXTENSIONS = {
    ExportFormat.txt: "txt",
    ExportFormat.epub: "epub",
    ExportFormat.docx: "docx",
}


@router.post("/novels/{novel_id}/export")
async def export_novel(novel_id: str, req: ExportRequest) -> StreamingResponse:
    async with get_db_session() as session:
        novel_result = await session.execute(
            select(Novel).where(Novel.novel_id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Novel not found")

        query = (
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .where(Chapter.status != "deleted")
            .order_by(Chapter.chapter_number)
        )

        if req.scope == ExportScope.volume:
            vol_result = await session.execute(
                select(Volume)
                .where(Volume.novel_id == novel_id)
                .where(Volume.volume_number == req.volume_number)
            )
            volume = vol_result.scalar_one_or_none()
            if not volume:
                raise HTTPException(status_code=404, detail="Volume not found")
            if volume.chapter_start and volume.chapter_end:
                query = query.where(
                    Chapter.chapter_number >= volume.chapter_start,
                    Chapter.chapter_number <= volume.chapter_end,
                )
            else:
                query = query.where(Chapter.volume_number == req.volume_number)

        elif req.scope == ExportScope.range:
            query = query.where(
                Chapter.chapter_number >= req.chapter_start,
                Chapter.chapter_number <= req.chapter_end,
            )

        result = await session.execute(query)
        chapters_db = result.scalars().all()

        if not chapters_db:
            raise HTTPException(status_code=400, detail="No chapters to export")

        vol_map: dict[int, str | None] = {}
        if any(ch.volume_number for ch in chapters_db):
            vol_result = await session.execute(
                select(Volume).where(Volume.novel_id == novel_id)
            )
            for v in vol_result.scalars().all():
                vol_map[v.volume_number] = v.title

    chapters = [
        ChapterData(
            number=ch.chapter_number,
            title=ch.title or "",
            content=ch.content or "",
            volume_number=ch.volume_number,
            volume_title=vol_map.get(ch.volume_number) if ch.volume_number else None,
        )
        for ch in chapters_db
    ]

    engine = FormatEngine(req.template, req.template_options)
    book_title = novel.title or "未命名小说"

    if req.format == ExportFormat.txt:
        buf = TxtExporter(engine).export(chapters)
    elif req.format == ExportFormat.epub:
        buf = EpubExporter(engine).export(chapters, title=book_title)
    else:
        buf = DocxExporter(engine).export(chapters, title=book_title)

    ext = FILE_EXTENSIONS[req.format]
    filename = f"{book_title}.{ext}"
    encoded_filename = quote(filename)

    return StreamingResponse(
        buf,
        media_type=MIME_TYPES[req.format],
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{encoded_filename}"
            ),
        },
    )


@router.get("/export/templates", response_model=list[TemplateInfo])
async def list_templates() -> list[TemplateInfo]:
    descriptions = {
        ExportTemplate.default: ("通用模板", "标准排版，适合本地阅读"),
        ExportTemplate.qidian: ("起点中文网", "段首缩进两格，段间空行，适配起点格式"),
        ExportTemplate.fanqie: ("番茄小说", "简洁排版，无多余空行"),
    }
    templates = []
    for tpl, options in PRESET_TEMPLATES.items():
        display_name, desc = descriptions[tpl]
        templates.append(
            TemplateInfo(
                name=tpl.value,
                display_name=display_name,
                description=desc,
                default_options=options,
            )
        )
    templates.append(
        TemplateInfo(
            name="custom",
            display_name="自定义模板",
            description="自定义段首缩进、段间距、章节标题格式",
            default_options=TemplateOptions(),
        )
    )
    return templates

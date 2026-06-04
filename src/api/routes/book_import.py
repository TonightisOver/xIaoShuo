"""Book import API routes."""

import structlog
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from src.api.services.book_import_service import get_book_import_service
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/import-book", tags=["book-import"])


@router.post("", status_code=202)
async def import_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if file.filename and not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only TXT files are supported")

    content = await file.read()
    text = _decode_txt(content)
    service = get_book_import_service()
    try:
        chapters = service.upload_and_parse(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task_id = service.create_task(chapters)
    background_tasks.add_task(service.run_analysis, task_id, get_llm_client())
    return {
        "task_id": task_id,
        "status": "pending",
        "chapter_count": len(chapters),
    }


@router.get("/{task_id}/status")
async def get_import_status(task_id: str):
    service = get_book_import_service()
    try:
        return service.get_status(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Book import task not found")


@router.post("/{task_id}/apply")
async def apply_import(task_id: str):
    service = get_book_import_service()
    try:
        return await service.apply_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Book import task not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("book_import_apply_failed", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create project")


def _decode_txt(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")

"""Migrate existing JSON tasks to PostgreSQL database"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from src.api.models.db_models import Task
from src.core.config import get_settings
from src.core.database import get_db_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_tasks() -> None:
    """Migrate tasks from JSON file to database"""
    settings = get_settings()
    json_path = Path(settings.TASK_STORAGE_PATH)

    if not json_path.exists():
        logger.warning(f"JSON file not found at {json_path}")
        return

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Load JSON data
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Found {len(data)} tasks in JSON file")

    # Migrate each task
    migrated = 0
    skipped = 0

    async with get_db_session() as session:
        for task_id, task_data in data.items():
            try:
                # Check if task already exists
                result = await session.execute(
                    select(Task).where(Task.task_id == task_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.info(f"Task {task_id} already exists, skipping")
                    skipped += 1
                    continue

                # Parse datetime fields
                created_at = datetime.fromisoformat(task_data["created_at"])
                started_at = (
                    datetime.fromisoformat(task_data["started_at"])
                    if task_data.get("started_at")
                    else None
                )
                completed_at = (
                    datetime.fromisoformat(task_data["completed_at"])
                    if task_data.get("completed_at")
                    else None
                )
                estimated_completion = (
                    datetime.fromisoformat(task_data["estimated_completion"])
                    if task_data.get("estimated_completion")
                    else None
                )

                # Create task
                task = Task(
                    task_id=task_id,
                    status=task_data["status"],
                    idea=task_data["idea"],
                    novel_type=task_data["novel_type"],
                    target_words=task_data["target_words"],
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    estimated_completion=estimated_completion,
                    progress=task_data.get("progress"),
                    result=task_data.get("result"),
                    errors=task_data.get("errors", []),
                )
                session.add(task)
                migrated += 1

                logger.info(f"Migrated task {task_id}")

            except Exception as e:
                logger.error(f"Failed to migrate task {task_id}: {e}")
                continue

        await session.commit()

    logger.info(f"Migration complete: {migrated} migrated, {skipped} skipped")

    # Backup JSON file
    backup_path = json_path.with_suffix(".json.backup")
    json_path.rename(backup_path)
    logger.info(f"Original JSON backed up to {backup_path}")


if __name__ == "__main__":
    asyncio.run(migrate_tasks())

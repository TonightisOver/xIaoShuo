"""章节读取压测任务"""

import random

from locust import TaskSet, task

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import NOVEL_IDS, CHAPTER_NUMBERS


class ChapterReadTasks(TaskSet):
    @task
    def get_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_number = random.choice(CHAPTER_NUMBERS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/chapters/{chapter_number}",
            catch_response=True,
            name="/api/v1/projects/[novel_id]/chapters/[chapter_number]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

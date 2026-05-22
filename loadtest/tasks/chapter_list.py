"""章节列表 + 小说详情压测任务"""

import random

from locust import TaskSet, task

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import NOVEL_IDS


class ChapterListTasks(TaskSet):
    @task(3)
    def list_chapters(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/chapters",
            catch_response=True,
            name="/api/v1/projects/[novel_id]/chapters",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def get_novel(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}",
            catch_response=True,
            name="/api/v1/projects/[novel_id]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

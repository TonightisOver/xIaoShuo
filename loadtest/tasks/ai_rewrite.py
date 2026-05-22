"""AI 改写压测任务（LLM 接口，超时设置较长）"""

import random

from locust import TaskSet, task

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import NOVEL_IDS, CHAPTER_NUMBERS


class AIRewriteTasks(TaskSet):
    @task
    def rewrite_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_number = random.choice(CHAPTER_NUMBERS)
        with self.client.post(
            f"/api/v1/projects/{novel_id}/chapters/{chapter_number}/rewrite",
            catch_response=True,
            timeout=120,
            name="/api/v1/projects/[novel_id]/chapters/[chapter_number]/rewrite",
        ) as resp:
            if resp.status_code in (200, 202, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

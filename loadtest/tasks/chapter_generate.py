"""章节生成压测任务（低频，模拟真实写作触发）"""

import random

from config import CHAPTER_NUMBERS, NOVEL_IDS
from locust import TaskSet, task


class ChapterGenerateTasks(TaskSet):
    @task
    def generate_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_num = random.choice(CHAPTER_NUMBERS) if CHAPTER_NUMBERS else 1
        with self.client.post(
            f"/api/v1/projects/{novel_id}/generate-chapters",
            json={"chapter_start": chapter_num, "chapter_end": chapter_num},
            catch_response=True,
            name="/api/v1/projects/[id]/generate-chapters",
        ) as resp:
            if resp.status_code in (200, 201, 202, 409):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

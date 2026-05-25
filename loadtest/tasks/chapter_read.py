"""章节读取压测任务"""

import random

from locust import TaskSet, task

from config import NOVEL_IDS, CHAPTER_NUMBERS


class ChapterReadTasks(TaskSet):
    @task(5)
    def get_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_number = random.choice(CHAPTER_NUMBERS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/chapters/{chapter_number}",
            catch_response=True,
            name="/api/v1/projects/[id]/chapters/[num]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_chapter_versions(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_number = random.choice(CHAPTER_NUMBERS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/chapters/{chapter_number}/versions",
            catch_response=True,
            name="/api/v1/projects/[id]/chapters/[num]/versions",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

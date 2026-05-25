"""章节编辑压测：模拟作者保存章节内容"""

import random

from locust import TaskSet, task

from config import NOVEL_IDS, CHAPTER_NUMBERS


class ChapterEditTasks(TaskSet):
    @task
    def update_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        chapter_number = random.choice(CHAPTER_NUMBERS)
        with self.client.put(
            f"/api/v1/projects/{novel_id}/chapters/{chapter_number}",
            json={"content": f"压测内容更新 - chapter {chapter_number} - {random.randint(1, 99999)}"},
            catch_response=True,
            name="/api/v1/projects/[id]/chapters/[num] (PUT)",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

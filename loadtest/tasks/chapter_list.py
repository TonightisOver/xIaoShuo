"""章节列表 + 小说详情 + 卷列表压测任务"""

import random

from config import NOVEL_IDS
from locust import TaskSet, task


class ChapterListTasks(TaskSet):
    @task(4)
    def list_chapters(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/chapters",
            catch_response=True,
            name="/api/v1/projects/[id]/chapters",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_novel_detail(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}",
            catch_response=True,
            name="/api/v1/projects/[id]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def list_volumes(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/volumes",
            catch_response=True,
            name="/api/v1/projects/[id]/volumes",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def list_novels(self):
        with self.client.get(
            "/api/v1/projects",
            catch_response=True,
            name="/api/v1/projects",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

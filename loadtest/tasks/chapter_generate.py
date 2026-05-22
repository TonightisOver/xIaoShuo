"""章节生成压测任务（低频，模拟真实写作触发）"""

import random

from locust import TaskSet, task

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import NOVEL_IDS


class ChapterGenerateTasks(TaskSet):
    @task
    def generate_chapter(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.post(
            f"/api/v1/projects/{novel_id}/generate-chapters",
            json={"start": 1, "end": 1},
            catch_response=True,
            name="/api/v1/projects/[novel_id]/generate-chapters",
        ) as resp:
            # 409 = 任务已在运行，属于正常业务状态，不算失败
            if resp.status_code in (200, 201, 202, 409):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

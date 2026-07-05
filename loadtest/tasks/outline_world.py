"""大纲与世界观压测：大纲获取、世界设定、角色列表"""

import random

from config import NOVEL_IDS
from locust import TaskSet, task


class OutlineWorldTasks(TaskSet):
    @task(3)
    def get_master_outline(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/outlines/master",
            catch_response=True,
            name="/api/v1/projects/[id]/outlines/master",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_world_setting(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/world",
            catch_response=True,
            name="/api/v1/projects/[id]/world",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def list_characters(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/characters",
            catch_response=True,
            name="/api/v1/projects/[id]/characters",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def get_story_bible(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/story-bible",
            catch_response=True,
            name="/api/v1/projects/[id]/story-bible",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def list_storylines(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/storylines",
            catch_response=True,
            name="/api/v1/projects/[id]/storylines",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

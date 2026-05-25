"""知识图谱压测：实体列表、三层图谱、可视化"""

import random

from locust import TaskSet, task

from config import NOVEL_IDS


class KnowledgeGraphTasks(TaskSet):
    @task(3)
    def list_entities(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            catch_response=True,
            name="/api/v1/projects/[id]/knowledge-graph/entities",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_three_layer(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/three-layer",
            catch_response=True,
            name="/api/v1/projects/[id]/knowledge-graph/three-layer",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_visualization(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/visualization",
            catch_response=True,
            name="/api/v1/projects/[id]/knowledge-graph/visualization",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def list_triples(self):
        novel_id = random.choice(NOVEL_IDS)
        with self.client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples",
            catch_response=True,
            name="/api/v1/projects/[id]/knowledge-graph/triples",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

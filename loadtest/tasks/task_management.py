"""任务管理压测：任务列表、任务详情、健康检查"""

import random

from locust import TaskSet, task

from config import TASK_IDS


class TaskManagementTasks(TaskSet):
    @task(3)
    def list_tasks(self):
        with self.client.get(
            "/api/v1/novels",
            params={"limit": 20},
            catch_response=True,
            name="/api/v1/novels (task list)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(2)
    def get_task_detail(self):
        if not TASK_IDS:
            return
        task_id = random.choice(TASK_IDS)
        with self.client.get(
            f"/api/v1/novels/{task_id}",
            catch_response=True,
            name="/api/v1/novels/[task_id]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

    @task(1)
    def health_check(self):
        with self.client.get(
            "/api/v1/health",
            catch_response=True,
            name="/api/v1/health",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status {resp.status_code}")

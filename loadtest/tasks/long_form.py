"""长篇小说生成相关接口压测"""

import random

from locust import TaskSet, task

from config import NOVEL_IDS


class LongFormCreateTasks(TaskSet):
    """创建长篇小说任务"""

    @task(1)
    def test_create_long_form(self):
        """POST /api/v1/novels/long-form"""
        self.client.post(
            "/api/v1/novels/long-form",
            json={
                "idea": "一个关于修仙者的长篇故事，主角从凡人一步步修炼成仙",
                "novel_type": "玄幻",
                "target_words": 100000,
                "volumes": 3,
                "chapters_per_volume": 10,
                "words_per_chapter": 3000,
                "writing_style": "现代白话",
            },
            name="/api/v1/novels/long-form [POST]",
        )


class LongFormProgressTasks(TaskSet):
    """长篇小说进度查询"""

    @task(3)
    def test_get_progress(self):
        """GET /api/v1/novels/{novel_id}/progress"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            self.client.get(
                f"/api/v1/novels/{novel_id}/progress",
                name="/api/v1/novels/[id]/progress [GET]",
            )


class LongFormQualityReportTasks(TaskSet):
    """质量报告查询"""

    @task(2)
    def test_get_quality_report(self):
        """GET /api/v1/novels/{novel_id}/quality-report"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            self.client.get(
                f"/api/v1/novels/{novel_id}/quality-report",
                name="/api/v1/novels/[id]/quality-report [GET]",
            )


class LongFormFillerDetectionTasks(TaskSet):
    """注水检测查询"""

    @task(2)
    def test_get_filler_detection(self):
        """GET /api/v1/novels/{novel_id}/filler-detection"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            self.client.get(
                f"/api/v1/novels/{novel_id}/filler-detection",
                name="/api/v1/novels/[id]/filler-detection [GET]",
            )


class LongFormForeshadowTrackerTasks(TaskSet):
    """伏笔追踪查询"""

    @task(2)
    def test_get_foreshadow_tracker(self):
        """GET /api/v1/novels/{novel_id}/foreshadow-tracker"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            self.client.get(
                f"/api/v1/novels/{novel_id}/foreshadow-tracker",
                name="/api/v1/novels/[id]/foreshadow-tracker [GET]",
            )


class LongFormVolumeControlTasks(TaskSet):
    """卷生成控制（暂停/恢复）"""

    @task(1)
    def test_generate_volume(self):
        """POST /api/v1/novels/{novel_id}/volumes/{volume_number}/generate"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            volume_number = random.randint(1, 3)
            self.client.post(
                f"/api/v1/novels/{novel_id}/volumes/{volume_number}/generate",
                json={"start_chapter": 1, "overwrite_existing": False},
                name="/api/v1/novels/[id]/volumes/[n]/generate [POST]",
            )

    @task(1)
    def test_pause_volume(self):
        """POST /api/v1/novels/{novel_id}/volumes/{volume_number}/pause"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            volume_number = random.randint(1, 3)
            self.client.post(
                f"/api/v1/novels/{novel_id}/volumes/{volume_number}/pause",
                name="/api/v1/novels/[id]/volumes/[n]/pause [POST]",
            )

    @task(1)
    def test_resume_volume(self):
        """POST /api/v1/novels/{novel_id}/volumes/{volume_number}/resume"""
        if NOVEL_IDS:
            novel_id = random.choice(NOVEL_IDS)
            volume_number = random.randint(1, 3)
            self.client.post(
                f"/api/v1/novels/{novel_id}/volumes/{volume_number}/resume",
                name="/api/v1/novels/[id]/volumes/[n]/resume [POST]",
            )

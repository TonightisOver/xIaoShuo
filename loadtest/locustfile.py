"""Locust 压测入口 - 四种用户画像

用法：
  # 交互式 Web UI（推荐）
  locust -f loadtest/locustfile.py

  # 无头模式：50 用户，每秒增加 10 个，运行 5 分钟
  locust -f loadtest/locustfile.py --headless -u 50 -r 10 --run-time 5m

  # 生成 HTML 报告
  locust -f loadtest/locustfile.py --headless -u 100 -r 20 --run-time 10m --html report.html
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import HOST
from locust import HttpUser, between
from tasks import (
    ChapterEditTasks,
    ChapterGenerateTasks,
    ChapterListTasks,
    ChapterReadTasks,
    KnowledgeGraphTasks,
    LongFormCreateTasks,
    LongFormFillerDetectionTasks,
    LongFormForeshadowTrackerTasks,
    LongFormProgressTasks,
    LongFormQualityReportTasks,
    LongFormVolumeControlTasks,
    OutlineWorldTasks,
    TaskManagementTasks,
)


class ReaderUser(HttpUser):
    """读者（50%）：高频浏览章节、列表、版本历史"""

    host = HOST
    wait_time = between(0.5, 2)
    weight = 5
    tasks = {
        ChapterReadTasks: 5,
        ChapterListTasks: 3,
        TaskManagementTasks: 1,
    }


class WriterUser(HttpUser):
    """作者（20%）：编辑章节、触发生成、查看任务"""

    host = HOST
    wait_time = between(2, 5)
    weight = 2
    tasks = {
        ChapterEditTasks: 4,
        ChapterGenerateTasks: 1,
        ChapterReadTasks: 2,
        TaskManagementTasks: 2,
    }


class AdminUser(HttpUser):
    """管理员（15%）：浏览大纲、世界观、知识图谱"""

    host = HOST
    wait_time = between(1, 3)
    weight = 2
    tasks = {
        OutlineWorldTasks: 4,
        KnowledgeGraphTasks: 3,
        ChapterListTasks: 2,
        TaskManagementTasks: 1,
    }


class LongFormUser(HttpUser):
    """长篇创作者（15%）：创建长篇任务、查看进度、质量报告、注水检测、伏笔追踪、卷控制"""

    host = HOST
    wait_time = between(2, 5)
    weight = 2
    tasks = {
        LongFormCreateTasks: 1,
        LongFormProgressTasks: 3,
        LongFormQualityReportTasks: 2,
        LongFormFillerDetectionTasks: 2,
        LongFormForeshadowTrackerTasks: 2,
        LongFormVolumeControlTasks: 1,
    }

"""Locust 压测入口 - 三种用户画像

用法：
  # 交互式 Web UI（推荐）
  locust -f loadtest/locustfile.py

  # 无头模式：50 用户，每秒增加 10 个，运行 5 分钟
  locust -f loadtest/locustfile.py --headless -u 50 -r 10 --run-time 5m

  # 生成 HTML 报告
  locust -f loadtest/locustfile.py --headless -u 100 -r 20 --run-time 10m --html report.html
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from locust import HttpUser, between

from tasks import (
    ChapterReadTasks,
    ChapterListTasks,
    ChapterEditTasks,
    ChapterGenerateTasks,
    AIRewriteTasks,
    TaskManagementTasks,
    OutlineWorldTasks,
    KnowledgeGraphTasks,
)
from config import HOST


class ReaderUser(HttpUser):
    """读者（60%）：高频浏览章节、列表、版本历史"""

    host = HOST
    wait_time = between(0.5, 2)
    weight = 6
    tasks = {
        ChapterReadTasks: 5,
        ChapterListTasks: 3,
        TaskManagementTasks: 1,
    }


class WriterUser(HttpUser):
    """作者（25%）：编辑章节、触发生成、查看任务"""

    host = HOST
    wait_time = between(2, 5)
    weight = 3
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

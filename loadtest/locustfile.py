"""Locust 压测入口

用法：
  locust -f loadtest/locustfile.py --host http://localhost:8000

或指定目标：
  LOADTEST_HOST=http://staging.example.com locust -f loadtest/locustfile.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from locust import HttpUser, between

from tasks.chapter_read import ChapterReadTasks
from tasks.chapter_list import ChapterListTasks
from tasks.chapter_generate import ChapterGenerateTasks
from config import HOST


class ReadHeavyUser(HttpUser):
    """模拟读者：高频读取章节和列表"""

    host = HOST
    wait_time = between(0.5, 2)
    tasks = {ChapterReadTasks: 7, ChapterListTasks: 3}


class GenerateUser(HttpUser):
    """模拟作者：低频触发章节生成"""

    host = HOST
    wait_time = between(30, 120)
    tasks = {ChapterGenerateTasks: 1}

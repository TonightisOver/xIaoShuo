"""TokenTracker 单元测试"""

import pytest

from src.core.llm.token_tracker import TokenRecord, TokenTracker, get_token_tracker


class TestTokenTracker:
    """TokenTracker 基础功能测试"""

    def setup_method(self):
        """每个测试前创建新的 tracker 实例（不依赖全局单例）"""
        self.tracker = TokenTracker()

    def test_initial_state(self):
        """初始状态：无记录，无跳过"""
        stats = self.tracker.get_stats()
        assert stats["total_calls"] == 0
        assert stats["records_skipped"] == 0
        assert stats["total_prompt_tokens"] == 0
        assert stats["total_completion_tokens"] == 0
        assert stats["total_tokens"] == 0
        assert stats["by_model"] == {}
        assert stats["recent_records"] == []

    def test_record_single(self):
        """记录单次调用"""
        self.tracker.record(
            model="deepseek-v4-pro",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        stats = self.tracker.get_stats()
        assert stats["total_calls"] == 1
        assert stats["total_prompt_tokens"] == 10
        assert stats["total_completion_tokens"] == 20
        assert stats["total_tokens"] == 30

    def test_record_multiple(self):
        """多次记录累加"""
        self.tracker.record("model-a", 100, 200, 300)
        self.tracker.record("model-b", 50, 100, 150)
        stats = self.tracker.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_prompt_tokens"] == 150
        assert stats["total_completion_tokens"] == 300
        assert stats["total_tokens"] == 450

    def test_skip_increments_counter(self):
        """skip() 增加 records_skipped"""
        self.tracker.skip()
        self.tracker.skip()
        stats = self.tracker.get_stats()
        assert stats["records_skipped"] == 2
        assert stats["total_calls"] == 0

    def test_by_model_grouping(self):
        """按模型分组统计"""
        self.tracker.record("flash", 10, 20, 30)
        self.tracker.record("flash", 5, 10, 15)
        self.tracker.record("pro", 100, 200, 300)

        stats = self.tracker.get_stats()
        assert "flash" in stats["by_model"]
        assert "pro" in stats["by_model"]

        flash = stats["by_model"]["flash"]
        assert flash["calls"] == 2
        assert flash["prompt_tokens"] == 15
        assert flash["completion_tokens"] == 30
        assert flash["total_tokens"] == 45

        pro = stats["by_model"]["pro"]
        assert pro["calls"] == 1
        assert pro["total_tokens"] == 300

    def test_recent_records_limit_50(self):
        """recent_records 最多返回 50 条"""
        for i in range(60):
            self.tracker.record("model", i, i, i * 2)
        stats = self.tracker.get_stats()
        assert len(stats["recent_records"]) == 50

    def test_maxlen_1000_drops_old_records(self):
        """超过 1000 条时旧记录被自动丢弃"""
        for i in range(1100):
            self.tracker.record("model", i, i, i * 2)
        stats = self.tracker.get_stats()
        # deque(maxlen=1000) 保留最新 1000 条
        assert stats["total_calls"] == 1000

    def test_recent_records_format(self):
        """recent_records 包含正确字段"""
        self.tracker.record("deepseek-v4-flash", 10, 20, 30)
        stats = self.tracker.get_stats()
        rec = stats["recent_records"][0]
        assert "timestamp" in rec
        assert rec["model"] == "deepseek-v4-flash"
        assert rec["prompt_tokens"] == 10
        assert rec["completion_tokens"] == 20
        assert rec["total_tokens"] == 30

    def test_records_skipped_in_stats(self):
        """get_stats() 返回值包含 records_skipped 字段"""
        self.tracker.skip()
        stats = self.tracker.get_stats()
        assert "records_skipped" in stats
        assert stats["records_skipped"] == 1


class TestGetTokenTracker:
    """全局单例工厂函数测试"""

    def test_singleton(self):
        """get_token_tracker() 返回同一实例"""
        import src.core.llm.token_tracker as tt_module

        # 重置全局单例
        tt_module._tracker = None

        t1 = get_token_tracker()
        t2 = get_token_tracker()
        assert t1 is t2

    def test_singleton_persists_state(self):
        """单例状态在多次调用间持久"""
        import src.core.llm.token_tracker as tt_module

        tt_module._tracker = None
        tracker = get_token_tracker()
        tracker.record("model", 1, 2, 3)

        same_tracker = get_token_tracker()
        assert same_tracker.get_stats()["total_calls"] == 1

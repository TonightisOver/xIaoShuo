"""Token 用量追踪器 — 内存聚合，进程重启后清零"""

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class TokenRecord:
    """单次 LLM 调用的 token 记录"""

    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TokenTracker:
    """内存 token 聚合器（单例）

    最多保留最近 1000 条记录（循环覆盖）。
    若 API 响应中不含 token 信息，则 records_skipped 加 1。
    """

    def __init__(self) -> None:
        self._records: deque[TokenRecord] = deque(maxlen=1000)
        self.records_skipped: int = 0

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """追加一条 token 记录。

        Args:
            model: 实际使用的模型名
            prompt_tokens: prompt token 数
            completion_tokens: completion token 数
            total_tokens: 总 token 数
        """
        self._records.append(
            TokenRecord(
                timestamp=datetime.now(UTC),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        )

    def skip(self) -> None:
        """记录一次因缺少 token 字段而跳过的调用。"""
        self.records_skipped += 1

    def get_stats(self) -> dict[str, Any]:
        """返回聚合统计数据。

        Returns:
            dict 包含:
            - total_calls: 已记录的调用次数（不含跳过）
            - records_skipped: 跳过次数
            - total_prompt_tokens: 累计 prompt tokens
            - total_completion_tokens: 累计 completion tokens
            - total_tokens: 累计总 tokens
            - by_model: 按模型分组统计 dict
            - recent_records: 最近 50 条记录列表
        """
        records = list(self._records)
        total_prompt = sum(r.prompt_tokens for r in records)
        total_completion = sum(r.completion_tokens for r in records)
        total_tokens = sum(r.total_tokens for r in records)

        by_model: dict[str, dict[str, int]] = {}
        for r in records:
            if r.model not in by_model:
                by_model[r.model] = {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            by_model[r.model]["calls"] += 1
            by_model[r.model]["prompt_tokens"] += r.prompt_tokens
            by_model[r.model]["completion_tokens"] += r.completion_tokens
            by_model[r.model]["total_tokens"] += r.total_tokens

        recent = records[-50:] if len(records) > 50 else records
        recent_records = [
            {
                "timestamp": r.timestamp.isoformat(),
                "model": r.model,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
            }
            for r in recent
        ]

        return {
            "total_calls": len(records),
            "records_skipped": self.records_skipped,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "by_model": by_model,
            "recent_records": recent_records,
        }


# 全局单例
_tracker: TokenTracker | None = None


def get_token_tracker() -> TokenTracker:
    """返回全局 TokenTracker 单例。"""
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker

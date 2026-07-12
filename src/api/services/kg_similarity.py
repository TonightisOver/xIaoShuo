"""知识图谱相似度计算工具（纯函数）。

从 knowledge_graph_service.py 提取的余弦相似度计算，便于独立单元测试。
"""
from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。

    Args:
        a: 第一个向量。
        b: 第二个向量。

    Returns:
        相似度值 [-1, 1]；任一向量为零向量时返回 0.0。
    """
    dot = sum(av * bv for av, bv in zip(a, b))
    norm_a = math.sqrt(sum(av * av for av in a))
    norm_b = math.sqrt(sum(bv * bv for bv in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

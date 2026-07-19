"""kg_similarity.cosine_similarity 纯函数单元测试。"""
from __future__ import annotations

import math

from src.api.services.knowledge.kg_similarity import cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0

    def test_orthogonal_vectors_return_zero(self):
        assert cosine_similarity([1, 0], [0, 1]) == 0.0

    def test_opposite_vectors_return_negative_one(self):
        assert cosine_similarity([1, 0], [-1, 0]) == -1.0

    def test_zero_vector_returns_zero(self):
        """任一零向量时返回 0.0，避免除零。"""
        assert cosine_similarity([0, 0, 0], [1, 1, 1]) == 0.0
        assert cosine_similarity([1, 1, 1], [0, 0, 0]) == 0.0

    def test_known_value(self):
        """[1,2,3] vs [4,5,6] 的余弦相似度应约为 0.9746。"""
        result = cosine_similarity([1, 2, 3], [4, 5, 6])
        expected = (1 * 4 + 2 * 5 + 3 * 6) / (
            math.sqrt(1 + 4 + 9) * math.sqrt(16 + 25 + 36)
        )
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_different_length_vectors_zip_truncates(self):
        """长度不等时按 zip 截断（与原内联实现行为一致）。"""
        # zip([1,2],[3,4,5]) → (1,3),(2,4)；norm 仍按各自全长算
        result = cosine_similarity([1, 2], [3, 4, 5])
        assert isinstance(result, float)

    def test_threshold_usage_pattern(self):
        """模拟 retrieve_context 中的阈值判断用法。"""
        vec = [0.9, 0.1, 0.0]
        embedding = [0.8, 0.2, 0.1]
        sim = cosine_similarity(vec, embedding)
        assert 0.0 <= sim <= 1.0
        # SIMILARITY_THRESHOLD = 0.5 时的判断
        assert sim >= 0.5

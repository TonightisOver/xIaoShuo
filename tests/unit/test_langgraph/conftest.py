"""langgraph 测试 conftest：autouse patch 各 node/quality 模块的 get_llm_client 返回 FakeLLMClient。

不打外网。覆盖 idea_expansion/world_building/character_design/outline_generation/
chapter_generation 五个 node，以及 quality/state_delta、quality/evaluator 两个
在端到端流程中可能被质量门禁触发的模块。
"""

import pytest

from tests.unit.test_langgraph.fake_llm import FakeLLMClient

# 需 patch 的模块（每个都 `from src.core.llm.client import get_llm_client`）
_LLM_MODULES = [
    "src.core.langgraph.nodes.idea_expansion",
    "src.core.langgraph.nodes.world_building",
    "src.core.langgraph.nodes.character_design",
    "src.core.langgraph.nodes.outline_generation",
    "src.core.langgraph.nodes.chapter_generation",
    "src.core.quality.state_delta",
    "src.core.quality.evaluator",
]


@pytest.fixture
def fake_llm(monkeypatch):
    """显式请求时注入 FakeLLMClient，不打外网。

    非 autouse：避免污染同目录既有 test_nodes.py / test_graph.py（它们各自 mock 或
    不调 LLM）。需 mock 的契约测试在函数签名加 `fake_llm` 参数即可。
    返回 client 供断言调用次数/顺序。
    """
    client = FakeLLMClient()
    for mod in _LLM_MODULES:
        monkeypatch.setattr(f"{mod}.get_llm_client", lambda c=client: c)
    yield client

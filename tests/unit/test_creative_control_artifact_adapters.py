"""创作控制产物适配器必须返回真实业务标识和内容。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_character_adapter_lists_database_ids_and_loads_content() -> None:
    from src.api.services.creative_control.artifact_adapters import (
        ArtifactAdapterRegistry,
    )

    character_service = SimpleNamespace(
        list_characters=AsyncMock(
            return_value=[{"id": 42, "name": "林舟", "role": "主角"}]
        ),
        get_character=AsyncMock(
            return_value={"id": 42, "name": "林舟", "role": "主角"}
        ),
    )
    with patch(
        "src.api.services.creative_control.artifact_adapters.get_character_service",
        return_value=character_service,
    ):
        registry = ArtifactAdapterRegistry()
        artifacts = await registry.list_artifacts("novel-1", "character")
        content = await registry.load("novel-1", "character", "42")

    assert artifacts == [{"artifact_id": "42", "label": "林舟"}]
    assert content["name"] == "林舟"


@pytest.mark.asyncio
async def test_volume_outline_adapter_uses_volume_number() -> None:
    from src.api.services.creative_control.artifact_adapters import (
        ArtifactAdapterRegistry,
    )

    outline_service = SimpleNamespace(
        get_volume_outlines=AsyncMock(
            return_value=[
                {"id": 8, "volume_number": 2, "content": {"title": "风起"}}
            ]
        )
    )
    with patch(
        "src.api.services.creative_control.artifact_adapters.get_outline_service",
        return_value=outline_service,
    ):
        registry = ArtifactAdapterRegistry()
        artifacts = await registry.list_artifacts("novel-1", "volume_outline")
        content = await registry.load("novel-1", "volume_outline", "2")

    assert artifacts == [{"artifact_id": "2", "label": "第2卷"}]
    assert content == {"title": "风起"}


@pytest.mark.asyncio
async def test_adapter_rejects_unknown_artifact_type() -> None:
    from src.api.services.creative_control.artifact_adapters import (
        ArtifactAdapterRegistry,
    )

    with pytest.raises(ValueError, match="unsupported artifact type"):
        await ArtifactAdapterRegistry().load("novel-1", "unknown", "x")


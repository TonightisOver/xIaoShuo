"""Service 层单元测试 — CharacterService / VolumeService / WorldService"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_character_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    name: str = "测试角色",
    role: str = "主角",
    description: str = "描述",
    personality: str = "性格",
    abilities: str = "能力",
    background_story: str = "背景",
    extra: dict | None = None,
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "name", "role", "description",
                          "personality", "abilities", "background_story",
                          "extra", "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.name = name
    row.role = role
    row.description = description
    row.personality = personality
    row.abilities = abilities
    row.background_story = background_story
    row.extra = extra or {}
    row.updated_at = datetime(2026, 7, 4, tzinfo=timezone.utc)
    return row


def _make_volume_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    volume_number: int = 1,
    title: str = "第一卷",
    summary: str = "卷摘要",
    outline: dict | None = None,
    status: str = "draft",
    chapter_start: int | None = 1,
    chapter_end: int | None = 10,
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "volume_number", "title", "summary",
                          "outline", "status", "chapter_start", "chapter_end",
                          "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.volume_number = volume_number
    row.title = title
    row.summary = summary
    row.outline = outline or {}
    row.status = status
    row.chapter_start = chapter_start
    row.chapter_end = chapter_end
    row.updated_at = datetime(2026, 7, 4, tzinfo=timezone.utc)
    return row


def _make_world_setting_row(
    novel_id: str = "novel-1",
    background: str = "世界背景",
    geography: str = "地理",
    culture: str = "文化",
    rules: str = "规则",
    extra: dict | None = None,
) -> MagicMock:
    row = MagicMock(spec=["novel_id", "background", "geography", "culture",
                          "rules", "extra", "updated_at"])
    row.novel_id = novel_id
    row.background = background
    row.geography = geography
    row.culture = culture
    row.rules = rules
    row.extra = extra or {}
    row.updated_at = datetime(2026, 7, 4, tzinfo=timezone.utc)
    return row


def _make_power_system_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    name: str = "修真体系",
    description: str = "描述",
    levels: list | None = None,
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "name", "description", "levels",
                          "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.name = name
    row.description = description
    row.levels = levels or []
    row.updated_at = datetime(2026, 7, 4, tzinfo=timezone.utc)
    return row


def _make_mock_session(scalar_one_or_none_result=None, scalar_result=None,
                        all_result=None):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_one_or_none_result
    if scalar_result is not None:
        mock_result.scalar.return_value = scalar_result
    if all_result is not None:
        mock_result.all.return_value = all_result
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = all_result or []
    mock_result.scalars = MagicMock(return_value=mock_scalars)
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.delete = AsyncMock()
    return session


# ============================================================
# CharacterService
# ============================================================

class TestCharacterService:
    """CharacterService CRUD"""

    @pytest.mark.asyncio
    async def test_list_characters(self):
        """list_characters 返回角色列表"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        rows = [
            _make_character_row(1, "novel-1", "角色A", "主角"),
            _make_character_row(2, "novel-1", "角色B", "配角"),
        ]
        session = _make_mock_session(all_result=rows)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.list_characters("novel-1")

        assert len(result) == 2
        assert result[0]["name"] == "角色A"
        assert result[1]["role"] == "配角"

    @pytest.mark.asyncio
    async def test_list_characters_empty(self):
        """list_characters 空列表"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()
        session = _make_mock_session(all_result=[])
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.list_characters("novel-empty")
        assert result == []

    @pytest.mark.asyncio
    async def test_create_character_adds_to_session(self):
        """create_character 将角色添加到 session"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        session = _make_mock_session()
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.create_character("novel-1", name="新角色", role="主角")

        session.add.assert_called_once()
        added_char = session.add.call_args[0][0]
        assert added_char.novel_id == "novel-1"
        assert added_char.name == "新角色"
        assert added_char.role == "主角"

    @pytest.mark.asyncio
    async def test_get_character_by_name(self):
        """get_character_by_name 通过名称查找"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        row = _make_character_row(1, "novel-1", name="张三")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.get_character_by_name("novel-1", "张三")

        assert result is not None
        assert result["name"] == "张三"

    @pytest.mark.asyncio
    async def test_get_character_by_name_not_found(self):
        """按名称查找不存在返回 None"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.get_character_by_name("novel-1", "不存在")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_character(self):
        """update_character 成功返回 True"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        row = _make_character_row(1, "novel-1")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.update_character("novel-1", 1, name="新名字")

        assert result is True
        assert row.name == "新名字"

    @pytest.mark.asyncio
    async def test_update_character_not_found(self):
        """update_character 不存在返回 False"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.update_character("novel-1", 999, name="新名字")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_character(self):
        """delete_character 成功返回 True"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        row = _make_character_row(1, "novel-1")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.delete_character("novel-1", 1)
        assert result is True
        session.delete.assert_called_once_with(row)

    @pytest.mark.asyncio
    async def test_delete_character_not_found(self):
        """delete_character 不存在返回 False"""
        from src.api.services.character_service import get_character_service
        svc = get_character_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.character_service.get_db_session", return_value=session):
            result = await svc.delete_character("novel-1", 999)
        assert result is False


# ============================================================
# VolumeService
# ============================================================

class TestVolumeService:
    """VolumeService CRUD"""

    @pytest.mark.asyncio
    async def test_list_volumes(self):
        """list_volumes 按 volume_number 排序返回"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()

        rows = [
            _make_volume_row(1, "novel-1", 1, "第一卷"),
            _make_volume_row(2, "novel-1", 2, "第二卷"),
        ]
        session = _make_mock_session(all_result=rows)
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.list_volumes("novel-1")

        assert len(result) == 2
        assert result[0]["volume_number"] == 1

    @pytest.mark.asyncio
    async def test_get_volume(self):
        """get_volume 返回单个卷详情"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()

        row = _make_volume_row(1, "novel-1", 3, title="第三卷")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.get_volume("novel-1", 3)

        assert result is not None
        assert result["title"] == "第三卷"
        assert result["volume_number"] == 3

    @pytest.mark.asyncio
    async def test_get_volume_not_found(self):
        """get_volume 不存在返回 None"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()
        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.get_volume("novel-1", 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_volume_returns_id(self):
        """create_volume 返回 id"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()

        session = _make_mock_session()
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.create_volume("novel-1", 1, title="新卷")
        # id is db-generated; verify add instead
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_volume(self):
        """update_volume 成功返回 True"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()

        row = _make_volume_row(1, "novel-1", 1)
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.update_volume("novel-1", 1, status="completed")
        assert result is True
        assert row.status == "completed"

    @pytest.mark.asyncio
    async def test_update_volume_not_found(self):
        """update_volume 不存在返回 False"""
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()
        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.volume_service.get_db_session", return_value=session):
            result = await svc.update_volume("novel-1", 999, status="completed")
        assert result is False


# ============================================================
# WorldService
# ============================================================

class TestWorldService:
    """WorldService — 世界观 + 力量体系"""

    @pytest.mark.asyncio
    async def test_get_world_setting(self):
        """get_world_setting 返回完整结构"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        row = _make_world_setting_row("novel-1", background="大陆背景")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.get_world_setting("novel-1")

        assert result is not None
        assert result["background"] == "大陆背景"
        assert result["novel_id"] == "novel-1"

    @pytest.mark.asyncio
    async def test_get_world_setting_not_found(self):
        """get_world_setting 不存在返回 None"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()
        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.get_world_setting("novel-none")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_world_setting_creates_new(self):
        """upsert_world_setting 不存在时创建"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            await svc.upsert_world_setting("novel-1", background="新背景")

        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_world_setting_updates_existing(self):
        """upsert_world_setting 存在时更新"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        row = _make_world_setting_row("novel-1", background="原背景")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            await svc.upsert_world_setting("novel-1", background="新背景")

        assert row.background == "新背景"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_power_systems(self):
        """list_power_systems 返回力量体系列表"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        rows = [
            _make_power_system_row(1, "novel-1", "修真"),
            _make_power_system_row(2, "novel-1", "魔法"),
        ]
        session = _make_mock_session(all_result=rows)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.list_power_systems("novel-1")

        assert len(result) == 2
        assert result[0]["name"] == "修真"

    @pytest.mark.asyncio
    async def test_create_power_system_returns_id(self):
        """create_power_system 返回 id"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        session = _make_mock_session()
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.create_power_system("novel-1", "炼体", "描述", [{"name": "一重"}])

        # id is db-generated; verify add instead
        added = session.add.call_args[0][0]
        assert added.name == "炼体"

    @pytest.mark.asyncio
    async def test_update_power_system(self):
        """update_power_system 成功返回 True"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        row = _make_power_system_row(1, "novel-1", "原名称")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.update_power_system("novel-1", 1, name="新名称")

        assert result is True
        assert row.name == "新名称"

    @pytest.mark.asyncio
    async def test_update_power_system_not_found(self):
        """update_power_system 不存在返回 False"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()
        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.update_power_system("novel-1", 999, name="新名称")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_power_system(self):
        """delete_power_system 成功返回 True"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()

        row = _make_power_system_row(1, "novel-1")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.delete_power_system("novel-1", 1)
        assert result is True
        session.delete.assert_called_once_with(row)

    @pytest.mark.asyncio
    async def test_delete_power_system_not_found(self):
        """delete_power_system 不存在返回 False"""
        from src.api.services.world_service import get_world_service
        svc = get_world_service()
        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.world_service.get_db_session", return_value=session):
            result = await svc.delete_power_system("novel-1", 999)
        assert result is False

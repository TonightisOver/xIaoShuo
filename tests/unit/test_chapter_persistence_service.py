"""章节持久化服务单元测试

覆盖范围：
- persist_generated_chapters: 批量写入生成章节到 DB（主路径 + 空 list + volume_number 回退）
- persist_chapters_with_replace: 删除旧章节后写入新章节 + 版本记录 + StoryBible 回写
  （主路径 + 无效章节过滤 + volume 查找 + manager 异常吞掉 + bible 异常吞掉）
- persist_langgraph_result: LangGraph 结果落库
  （world_setting/characters/volumes/chapters + 版本 + 状态更新 + 异常转 PersistenceError）
- persist_quality_to_version: 质量评分回写活跃版本
  （命中版本回写 + 未命中版本不报错 + 异常吞掉）

被测方法本身的逻辑（Chapter 实例化、delete/select 构造、字段过滤）真实执行；
仅 mock 外部依赖：get_db_session、各 service 单例 getter、story_bible 回写。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.chapter_persistence_service import (
    persist_chapters_with_replace,
    persist_generated_chapters,
    persist_langgraph_result,
    persist_quality_to_version,
    record_chapter_artifacts,
)


def _make_mock_session():
    """构造一个 async context manager 形式的 mock session。

    get_db_session() 返回的 async generator 在 `async with` 下会产出该 session。
    """
    session = AsyncMock()
    # execute 返回的结果链：.scalar_one_or_none() → None（模拟行不存在，走 INSERT 分支）
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    # 作为 async context manager
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _make_chapter_dict(chapter: int = 1, content: str = "正文", word_count: int = 100,
                       title: str = "标题", volume_number=None) -> dict:
    return {
        "chapter": chapter,
        "title": title,
        "content": content,
        "word_count": word_count,
        "volume_number": volume_number,
        "chapter_type": "normal",
    }


def _make_version_row(chapter_number: int = 1, version_number: int = 1):
    """构造一个真实-ish 的 ChapterVersion mock 行，支持属性赋值。"""
    row = MagicMock()
    row.novel_id = "novel-1"
    row.chapter_number = chapter_number
    row.version_number = version_number
    row.quality_score = None
    row.quality_scores = None
    row.kg_conflicts = None
    return row


# ============================================================
# persist_generated_chapters
# ============================================================

class TestPersistGeneratedChapters:
    """persist_generated_chapters() — 批量写入生成章节主路径"""

    @pytest.mark.asyncio
    async def test_persists_all_chapters_with_default_status(self):
        """正常路径：为每个章节构造 Chapter 并 session.add，status 默认 generated"""
        session, cm = _make_mock_session()
        chapters = [
            _make_chapter_dict(chapter=1, volume_number=1),
            _make_chapter_dict(chapter=2, volume_number=1),
        ]

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_generated_chapters("novel-1", chapters, volume_number=1)

        assert session.add.call_count == 2
        added = [call.args[0] for call in session.add.call_args_list]
        assert [c.chapter_number for c in added] == [1, 2]
        assert all(c.novel_id == "novel-1" for c in added)
        assert all(c.status == "generated" for c in added)
        assert all(c.volume_number == 1 for c in added)

    @pytest.mark.asyncio
    async def test_empty_chapter_list_adds_nothing(self):
        """边界：空列表不调用 session.add"""
        session, cm = _make_mock_session()

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_generated_chapters("novel-1", [])

        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_status_propagated_to_chapters(self):
        """分支：自定义 status 写入每个章节"""
        session, cm = _make_mock_session()
        chapters = [_make_chapter_dict(chapter=5)]

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_generated_chapters("novel-1", chapters, status="draft")

        added = session.add.call_args_list[0].args[0]
        assert added.status == "draft"

    @pytest.mark.asyncio
    async def test_volume_number_falls_back_to_chapter_field(self):
        """分支：volume_number=None 时回退到章节自身的 volume_number 字段"""
        session, cm = _make_mock_session()
        chapters = [_make_chapter_dict(chapter=3, volume_number=7)]

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_generated_chapters("novel-1", chapters, volume_number=None)

        added = session.add.call_args_list[0].args[0]
        assert added.volume_number == 7

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_row_not_insert(self):
        """upsert：同 novel_id+chapter_number 已存在时 UPDATE，不 session.add（避免唯一约束冲突）"""
        session, cm = _make_mock_session()
        # 模拟已有行：scalar_one_or_none 返回一个 mock 行对象
        existing_row = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none = MagicMock(return_value=existing_row)
        session.execute = AsyncMock(return_value=exec_result)
        chapters = [_make_chapter_dict(chapter=1, volume_number=1, content="新内容")]

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_generated_chapters("novel-1", chapters, volume_number=1)

        # 已存在 → 不 add，而是 setattr 更新已有行
        session.add.assert_not_called()
        # 验证关键字段被更新到已有行
        assert existing_row.content == "新内容"
        assert existing_row.status == "generated"


# ============================================================
# persist_chapters_with_replace
# ============================================================

class TestPersistChaptersWithReplace:
    """persist_chapters_with_replace() — 删除旧 + 写新 + 版本 + StoryBible"""

    @pytest.mark.asyncio
    async def test_deletes_then_adds_successful_chapters(self):
        """正常路径：先 delete 旧章节，再 add 新章节，最后调用版本创建与 bible 回写"""
        session, cm = _make_mock_session()
        chapters = [
            _make_chapter_dict(chapter=1, content="c1", word_count=10),
            _make_chapter_dict(chapter=2, content="c2", word_count=20),
        ]
        volumes = [{"volume_number": 1, "outline": {"chapters": [{"chapter": 1}, {"chapter": 2}]}}]

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock) as mock_bible:
            await persist_chapters_with_replace("novel-1", chapters, volumes)

        # 每个章节都先 delete 再 add
        assert session.execute.call_count == 2  # 2 次 delete
        assert session.add.call_count == 2
        # 版本创建被调用 2 次
        assert mock_manager.create_chapter_version.call_count == 2
        # fix_volume_numbers 被调用 1 次
        mock_manager.fix_volume_numbers.assert_awaited_once_with("novel-1")
        # bible 回写被调用 2 次
        assert mock_bible.call_count == 2

    @pytest.mark.asyncio
    async def test_filters_out_empty_and_zero_wordcount_chapters(self):
        """边界：content 为空或 word_count=0 的章节被过滤，不写库、不创建版本"""
        session, cm = _make_mock_session()
        chapters = [
            _make_chapter_dict(chapter=1, content="", word_count=100),   # 无 content
            _make_chapter_dict(chapter=2, content="c", word_count=0),    # word_count=0
            _make_chapter_dict(chapter=3, content="c3", word_count=30),  # 有效
        ]
        volumes = []

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock):
            await persist_chapters_with_replace("novel-1", chapters, volumes)

        assert session.add.call_count == 1
        added = session.add.call_args_list[0].args[0]
        assert added.chapter_number == 3
        assert mock_manager.create_chapter_version.call_count == 1

    @pytest.mark.asyncio
    async def test_volume_number_fallback_to_chapter_start_end(self):
        """分支：outline 里找不到时回退到 volume 的 chapter_start/chapter_end 区间"""
        session, cm = _make_mock_session()
        chapters = [_make_chapter_dict(chapter=5, content="c5", word_count=10)]
        # outline 里没有 chapter=5，但 chapter_start=4 chapter_end=8 覆盖
        volumes = [{"volume_number": 9, "outline": {}, "chapter_start": 4, "chapter_end": 8}]

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock):
            await persist_chapters_with_replace("novel-1", chapters, volumes)

        added = session.add.call_args_list[0].args[0]
        assert added.volume_number == 9

    @pytest.mark.asyncio
    async def test_create_chapter_version_exception_swallowed(self):
        """错误处理：create_chapter_version 抛异常被吞掉，不中断流程"""
        session, cm = _make_mock_session()
        chapters = [_make_chapter_dict(chapter=1, content="c1", word_count=10)]
        volumes = []

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock(
            side_effect=ValueError("boom"))

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock) as mock_bible:
            # 不应抛异常
            await persist_chapters_with_replace("novel-1", chapters, volumes)

        # 章节仍被 add；bible 回写仍被调用（异常处理在版本创建之后）
        assert session.add.call_count == 1
        mock_bible.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_story_bible_update_exception_swallowed(self):
        """错误处理：update_bible_after_generation 抛异常被吞掉，不中断流程"""
        session, cm = _make_mock_session()
        chapters = [_make_chapter_dict(chapter=1, content="c1", word_count=10)]
        volumes = []

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock, side_effect=RuntimeError("bible boom")):
            # 不应抛异常
            await persist_chapters_with_replace("novel-1", chapters, volumes)

        # 章节仍被 add
        assert session.add.call_count == 1


# ============================================================
# persist_langgraph_result
# ============================================================

class TestPersistLanggraphResult:
    """persist_langgraph_result() — LangGraph 结果落库"""

    @pytest.mark.asyncio
    async def test_full_result_persists_all_sections(self):
        """正常路径：world_setting / characters / volumes / chapters 全部写入，状态更新为 completed"""
        session, cm = _make_mock_session()
        result = {
            "world_setting": {
                "background": "世界背景",
                "geography": "地理",
                "culture": "文化",
                "rules": "规则",
                "extra_field": "额外",
            },
            "characters": [
                {"name": "主角", "role": "hero", "description": "描述"},
            ],
            "volumes": [
                {"volume_number": 1, "title": "卷一", "summary": "概要",
                 "chapters": [{"chapter": 1}, {"chapter": 2}]},
            ],
            "chapters": [
                {"chapter": 1, "title": "t1", "content": "c1", "word_count": 10},
                {"chapter": 2, "title": "t2", "content": "c2", "word_count": 20},
            ],
        }

        mock_manager = MagicMock()
        mock_manager.upsert_world_setting = AsyncMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()
        mock_manager.update_novel = AsyncMock()

        mock_char_svc = MagicMock()
        mock_char_svc.get_character_by_name = AsyncMock(return_value=None)
        mock_char_svc.create_character = AsyncMock()

        mock_volume_svc = MagicMock()
        mock_volume_svc.create_volume = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.character_service.get_character_service", return_value=mock_char_svc), \
             patch("src.api.services.volume_service.get_volume_service", return_value=mock_volume_svc):
            await persist_langgraph_result("novel-1", result)

        # world_setting upsert 调用 1 次
        mock_manager.upsert_world_setting.assert_awaited_once()
        # 角色新建 1 次（不存在则 create）
        mock_char_svc.create_character.assert_awaited_once()
        # volume 创建 1 次
        assert mock_volume_svc.create_volume.call_count == 1
        # 章节写入 2 次（delete + add 循环 2 次）
        assert session.execute.call_count == 2  # 2 次 delete
        assert session.add.call_count == 2
        # 版本创建 2 次（每章 content 都创建版本）
        assert mock_manager.create_chapter_version.call_count == 2
        # 状态更新为 completed
        mock_manager.update_novel.assert_awaited_once_with("novel-1", status="completed")
        # fix_volume_numbers 调用
        mock_manager.fix_volume_numbers.assert_awaited_once_with("novel-1")

    @pytest.mark.asyncio
    async def test_existing_character_updated_not_created(self):
        """分支：角色已存在则走 update 路径而非 create"""
        session, cm = _make_mock_session()
        result = {
            "characters": [{"name": "主角", "role": "hero"}],
        }

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()
        mock_manager.update_novel = AsyncMock()
        mock_manager.upsert_world_setting = AsyncMock()

        existing_char = {"id": "char-99", "name": "主角"}
        mock_char_svc = MagicMock()
        mock_char_svc.get_character_by_name = AsyncMock(return_value=existing_char)
        mock_char_svc.update_character = AsyncMock()
        mock_char_svc.create_character = AsyncMock()

        mock_volume_svc = MagicMock()
        mock_volume_svc.create_volume = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.character_service.get_character_service", return_value=mock_char_svc), \
             patch("src.api.services.volume_service.get_volume_service", return_value=mock_volume_svc):
            await persist_langgraph_result("novel-1", result)

        # 已存在 → update，未 → create
        mock_char_svc.update_character.assert_awaited_once()
        mock_char_svc.create_character.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_result_still_updates_status(self):
        """边界：空 result 仍会调用 fix_volume_numbers 和 update_novel"""
        session, cm = _make_mock_session()

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock()
        mock_manager.update_novel = AsyncMock()
        mock_manager.upsert_world_setting = AsyncMock()

        mock_char_svc = MagicMock()
        mock_volume_svc = MagicMock()
        mock_volume_svc.create_volume = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.character_service.get_character_service", return_value=mock_char_svc), \
             patch("src.api.services.volume_service.get_volume_service", return_value=mock_volume_svc):
            await persist_langgraph_result("novel-1", {})

        # 没有任何章节写入
        session.add.assert_not_called()
        session.execute.assert_not_called()
        # 但状态更新与 fix 仍调用
        mock_manager.fix_volume_numbers.assert_awaited_once_with("novel-1")
        mock_manager.update_novel.assert_awaited_once_with("novel-1", status="completed")
        # 无章节则无版本创建
        mock_manager.create_chapter_version.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_chapter_version_exception_swallowed_in_langgraph(self):
        """错误处理：单章节版本创建抛异常被吞掉，状态仍更新"""
        session, cm = _make_mock_session()
        result = {
            "chapters": [{"chapter": 1, "content": "c1", "word_count": 10}],
        }

        mock_manager = MagicMock()
        mock_manager.fix_volume_numbers = AsyncMock()
        mock_manager.create_chapter_version = AsyncMock(side_effect=ValueError("v boom"))
        mock_manager.update_novel = AsyncMock()

        mock_char_svc = MagicMock()
        mock_volume_svc = MagicMock()
        mock_volume_svc.create_volume = AsyncMock()

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.character_service.get_character_service", return_value=mock_char_svc), \
             patch("src.api.services.volume_service.get_volume_service", return_value=mock_volume_svc):
            # 不应抛异常
            await persist_langgraph_result("novel-1", result)

        # 章节仍写入
        assert session.add.call_count == 1
        # 状态仍更新
        mock_manager.update_novel.assert_awaited_once_with("novel-1", status="completed")

    @pytest.mark.asyncio
    async def test_inner_exception_wrapped_as_persistence_error(self):
        """错误处理：内部异常被包装为 PersistenceError"""
        session, cm = _make_mock_session()
        # 让 world_setting upsert 抛异常（在 try 块内最早可触发点）
        mock_manager = MagicMock()
        mock_manager.upsert_world_setting = AsyncMock(side_effect=RuntimeError("inner boom"))

        with patch("src.core.database.get_db_session", return_value=cm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager):
            from src.core.exceptions import PersistenceError
            with pytest.raises(PersistenceError):
                await persist_langgraph_result("novel-1", {"world_setting": {"background": "x"}})


# ============================================================
# persist_quality_to_version
# ============================================================

class TestPersistQualityToVersion:
    """persist_quality_to_version() — 质量评分回写活跃版本"""

    @pytest.mark.asyncio
    async def test_writes_quality_to_active_version_and_commits(self):
        """正常路径：命中活跃版本，回写 quality_score/quality_scores/kg_conflicts 并 commit"""
        version_row = _make_version_row(chapter_number=1, version_number=1)
        session, cm = _make_mock_session()

        # execute 返回的结果对象其 scalar_one_or_none 返回 version_row
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version_row
        session.execute.return_value = mock_result

        quality_scores = {"overall": 0.85, "fluency": 0.9}
        consistency_warnings = [{"type": "conflict"}]

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_quality_to_version("novel-1", 1, quality_scores, consistency_warnings)

        assert version_row.quality_score == 0.85
        assert version_row.quality_scores == quality_scores
        assert version_row.kg_conflicts == consistency_warnings
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_active_version_does_not_commit(self):
        """边界：没有活跃版本时，不 commit、不抛异常"""
        session, cm = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        with patch("src.core.database.get_db_session", return_value=cm):
            # 不应抛异常
            await persist_quality_to_version("novel-1", 99, {"overall": 0.5}, [])

        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_consistency_warnings_set_to_none(self):
        """分支：consistency_warnings 为空 list 时 kg_conflicts 被设为 None"""
        version_row = _make_version_row(chapter_number=2, version_number=1)
        session, cm = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = version_row
        session.execute.return_value = mock_result

        with patch("src.core.database.get_db_session", return_value=cm):
            await persist_quality_to_version("novel-1", 2, {"overall": 0.7}, [])

        assert version_row.kg_conflicts is None

    @pytest.mark.asyncio
    async def test_session_exception_swallowed(self):
        """错误处理：session.execute 抛异常被吞掉，不向上传播"""
        session, cm = _make_mock_session()
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))

        with patch("src.core.database.get_db_session", return_value=cm):
            # 不应抛异常
            await persist_quality_to_version("novel-1", 1, {"overall": 0.5}, [])


# ============================================================
# record_chapter_artifacts
# ============================================================
class TestRecordChapterArtifacts:
    """record_chapter_artifacts() — 版本记录 + StoryBible 反向更新（逐章/批量复用）"""

    @pytest.mark.asyncio
    async def test_creates_version_and_bible_for_each_successful_chapter(self):
        """每成功章调一次 create_chapter_version + update_bible_after_generation"""
        chapters = [
            _make_chapter_dict(chapter=1, content="c1", word_count=10),
            _make_chapter_dict(chapter=2, content="c2", word_count=20),
        ]
        mock_manager = MagicMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock) as mock_bible:
            await record_chapter_artifacts("novel-1", chapters)

        assert mock_manager.create_chapter_version.call_count == 2
        assert mock_bible.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_chapters_without_content_or_wordcount(self):
        """空内容/零字数的章节不创建版本也不回写 bible"""
        chapters = [
            _make_chapter_dict(chapter=1, content="c1", word_count=10),
            {"chapter": 2, "title": "空", "content": "", "word_count": 0},  # 跳过
            {"chapter": 3, "title": "无字数", "content": "c3", "word_count": 0},  # 跳过
        ]
        mock_manager = MagicMock()
        mock_manager.create_chapter_version = AsyncMock()

        with patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock) as mock_bible:
            await record_chapter_artifacts("novel-1", chapters)

        assert mock_manager.create_chapter_version.call_count == 1
        assert mock_bible.call_count == 1

    @pytest.mark.asyncio
    async def test_bible_failure_does_not_block_subsequent_chapters(self):
        """某章 bible 回写异常不阻断后续章"""
        chapters = [
            _make_chapter_dict(chapter=1, content="c1", word_count=10),
            _make_chapter_dict(chapter=2, content="c2", word_count=20),
        ]
        mock_manager = MagicMock()
        mock_manager.create_chapter_version = AsyncMock(side_effect=[None, ValueError("x")])

        with patch("src.api.services.novel_manager.get_novel_manager", return_value=mock_manager), \
             patch("src.api.services.story_bible_service.update_bible_after_generation",
                   new_callable=AsyncMock) as mock_bible:
            # 不应抛异常
            await record_chapter_artifacts("novel-1", chapters)

        # 版本即便第二章抛错，bible 仍对两章都尝试
        assert mock_bible.call_count == 2

"""读者视角模拟服务单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.reader_simulation_service import (
    READER_PERSONAS,
    ReaderSimulationService,
)


@pytest.fixture
def service():
    return ReaderSimulationService()


class TestPersonas:
    def test_all_personas_have_required_fields(self):
        for pid, persona in READER_PERSONAS.items():
            assert persona["id"] == pid
            assert "name" in persona
            assert "description" in persona
            assert "prompt" in persona
            assert len(persona["prompt"]) > 50

    def test_four_personas_defined(self):
        assert len(READER_PERSONAS) == 4
        assert "hardcore_fan" in READER_PERSONAS
        assert "casual_reader" in READER_PERSONAS
        assert "critic" in READER_PERSONAS
        assert "veteran_reader" in READER_PERSONAS


class TestRunSimulation:
    @pytest.mark.asyncio
    async def test_creates_pending_record(self, service):
        with patch(
            "src.api.services.reader_simulation_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session.__aexit__ = AsyncMock(return_value=None)

            def set_id(obj):
                obj.id = 42

            mock_session.add = MagicMock(side_effect=set_id)
            mock_session.flush = AsyncMock()
            mock_db.return_value = mock_session

            sim_id = await service.run_simulation(
                "novel-1", 5, None
            )
            assert sim_id == 42
            added = mock_session.add.call_args[0][0]
            assert added.novel_id == "novel-1"
            assert added.chapter_number == 5
            assert added.status == "pending"
            assert len(added.personas_used) == 4

    @pytest.mark.asyncio
    async def test_filters_invalid_personas(self, service):
        with patch(
            "src.api.services.reader_simulation_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_db.return_value = mock_session

            await service.run_simulation(
                "novel-1", 1, ["hardcore_fan", "invalid_one"]
            )
            added = mock_session.add.call_args[0][0]
            assert added.personas_used == ["hardcore_fan"]


class TestExecuteSimulation:
    @pytest.mark.asyncio
    async def test_missing_sim_returns_early(self, service):
        with patch(
            "src.api.services.reader_simulation_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(
                return_value=mock_result
            )
            mock_session.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            await service.execute_simulation(999)

    @pytest.mark.asyncio
    async def test_empty_chapter_marks_failed(self, service):
        with patch(
            "src.api.services.reader_simulation_service.get_db_session"
        ) as mock_db:
            mock_sim = MagicMock()
            mock_sim.id = 1
            mock_sim.novel_id = "novel-1"
            mock_sim.chapter_number = 5
            mock_sim.personas_used = ["hardcore_fan"]
            mock_sim.status = "pending"

            call_count = [0]

            def make_session():
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_session.__aexit__ = AsyncMock(
                    return_value=None
                )

                async def execute_side_effect(*args, **kwargs):
                    call_count[0] += 1
                    result = MagicMock()
                    if call_count[0] == 1:
                        result.scalar_one_or_none.return_value = (
                            mock_sim
                        )
                    elif call_count[0] == 2:
                        result.scalar_one_or_none.return_value = (
                            None
                        )
                    elif call_count[0] == 3:
                        result.scalar_one_or_none.return_value = (
                            mock_sim
                        )
                    return result

                mock_session.execute = AsyncMock(
                    side_effect=execute_side_effect
                )
                return mock_session

            mock_db.return_value = make_session()

            await service.execute_simulation(1)
            assert mock_sim.status == "failed"

    @pytest.mark.asyncio
    async def test_successful_simulation(self, service):
        with (
            patch(
                "src.api.services.reader_simulation_service.get_db_session"
            ) as mock_db,
            patch(
                "src.api.services.reader_simulation_service.get_llm_client"
            ) as mock_llm_fn,
        ):
            mock_sim = MagicMock()
            mock_sim.id = 1
            mock_sim.novel_id = "novel-1"
            mock_sim.chapter_number = 3
            mock_sim.personas_used = ["casual_reader"]
            mock_sim.status = "pending"
            mock_sim.results = []

            mock_chapter = MagicMock()
            mock_chapter.content = "这是一段测试正文内容" * 100
            mock_chapter.title = "测试章节"

            call_count = [0]

            def make_session():
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_session.__aexit__ = AsyncMock(
                    return_value=None
                )

                async def execute_side_effect(*args, **kwargs):
                    call_count[0] += 1
                    result = MagicMock()
                    if call_count[0] == 1:
                        result.scalar_one_or_none.return_value = (
                            mock_sim
                        )
                    elif call_count[0] == 2:
                        result.scalar_one_or_none.return_value = (
                            mock_chapter
                        )
                    elif call_count[0] == 3:
                        result.scalar_one_or_none.return_value = (
                            None
                        )
                    elif call_count[0] == 4:
                        result.scalar_one_or_none.return_value = (
                            mock_sim
                        )
                    return result

                mock_session.execute = AsyncMock(
                    side_effect=execute_side_effect
                )
                return mock_session

            mock_db.return_value = make_session()

            llm_response = (
                '{"engagement_score": 0.8,'
                ' "would_continue_reading": true,'
                ' "emotional_response": "不错",'
                ' "pacing_assessment": "good",'
                ' "character_consistency": "consistent",'
                ' "satisfaction_points": ["节奏好"],'
                ' "pain_points": [],'
                ' "overall_comment": "总评"}'
            )
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(
                return_value=llm_response
            )
            mock_llm_fn.return_value = mock_llm

            await service.execute_simulation(1)
            assert mock_sim.status == "completed"
            assert len(mock_sim.results) == 1
            assert (
                mock_sim.results[0]["engagement_score"] == 0.8
            )


class TestListSimulations:
    @pytest.mark.asyncio
    async def test_returns_list(self, service):
        with patch(
            "src.api.services.reader_simulation_service.get_db_session"
        ) as mock_db:
            mock_row = MagicMock()
            mock_row.id = 1
            mock_row.chapter_number = 5
            mock_row.personas_used = ["hardcore_fan"]
            mock_row.status = "completed"
            mock_row.duration_ms = 5000
            mock_row.created_at = None

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [
                mock_row
            ]
            mock_session.execute = AsyncMock(
                return_value=mock_result
            )
            mock_session.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            result = await service.list_simulations(
                "novel-1", 5
            )
            assert len(result) == 1
            assert result[0]["id"] == 1
            assert result[0]["status"] == "completed"

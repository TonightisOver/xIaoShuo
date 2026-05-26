"""读者视角模拟 API 路由"""

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.api.services.reader_simulation_service import (
    READER_PERSONAS,
    get_reader_simulation_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["reader-simulation"])


class SimulationRequest(BaseModel):
    personas: list[str] | None = Field(
        default=None,
        description="要模拟的读者人设ID列表，为空则使用全部",
    )


@router.post(
    "/{novel_id}/chapters/{chapter_number}/reader-simulation",
    status_code=202,
)
async def trigger_simulation(
    novel_id: str,
    chapter_number: int,
    req: SimulationRequest,
    background_tasks: BackgroundTasks,
):
    service = get_reader_simulation_service()
    sim_id = await service.run_simulation(
        novel_id=novel_id,
        chapter_number=chapter_number,
        personas=req.personas,
    )
    background_tasks.add_task(service.execute_simulation, sim_id)
    return {
        "simulation_id": sim_id,
        "status": "running",
        "message": "读者模拟已启动",
    }


@router.get(
    "/{novel_id}/chapters/{chapter_number}/reader-simulations"
)
async def list_simulations(novel_id: str, chapter_number: int):
    service = get_reader_simulation_service()
    simulations = await service.list_simulations(
        novel_id, chapter_number
    )
    return {"simulations": simulations}


@router.get("/{novel_id}/reader-simulations/{simulation_id}")
async def get_simulation(novel_id: str, simulation_id: int):
    service = get_reader_simulation_service()
    sim = await service.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


@router.get("/{novel_id}/reader-simulation/personas")
async def list_personas(novel_id: str):
    return {
        "personas": [
            {
                "id": p["id"],
                "name": p["name"],
                "description": p["description"],
            }
            for p in READER_PERSONAS.values()
        ]
    }

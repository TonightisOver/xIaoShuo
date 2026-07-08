"""知识图谱 API 路由"""

import uuid
from datetime import UTC

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, delete, select

from src.api.models.db_models import (
    KnowledgeEntity,
    KnowledgeEntityState,
    KnowledgeExtractionLog,
    KnowledgeTriple,
)
from src.api.services.knowledge_graph_service import get_knowledge_graph_service
from src.core.database import get_db_session

router = APIRouter(
    prefix="/api/v1/projects/{novel_id}/knowledge-graph",
    tags=["knowledge-graph"],
)


# --- Request/Response Models ---

class EntityCreate(BaseModel):
    entity_type: str
    name: str
    aliases: list[str] = []
    attributes: dict = {}
    first_chapter: int


class EntityUpdate(BaseModel):
    entity_type: str | None = None
    name: str | None = None
    aliases: list[str] | None = None
    attributes: dict | None = None


class EntityResponse(BaseModel):
    id: str
    entity_type: str
    name: str
    aliases: list[str]
    attributes: dict
    first_chapter: int
    last_chapter: int | None
    source: str


class TripleCreate(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    chapter_number: int
    confidence: float = 1.0


class TripleUpdate(BaseModel):
    predicate: str | None = None
    confidence: float | None = None
    status: str | None = None



class TripleResponse(BaseModel):
    id: str
    subject: EntityResponse
    predicate: str
    object: EntityResponse
    chapter_number: int
    confidence: float
    status: str


class VisualizationResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class ConsistencyResult(BaseModel):
    conflicts: list[dict]
    checked_at: str


class StateSnapshotResponse(BaseModel):
    id: str
    novel_id: str
    entity_id: str
    chapter_number: int
    attributes: dict
    created_at: str


def _entity_to_response(e: KnowledgeEntity) -> EntityResponse:
    return EntityResponse(
        id=e.id, entity_type=e.entity_type, name=e.name,
        aliases=e.aliases or [], attributes=e.attributes or {},
        first_chapter=e.first_chapter, last_chapter=e.last_chapter,
        source=e.source,
    )


# --- Entity Endpoints ---

@router.get("/entities", response_model=list[EntityResponse])
async def list_entities(
    novel_id: str,
    entity_type: str | None = Query(None),
    name: str | None = Query(None),
):
    """查询实体列表"""
    async with get_db_session() as session:
        stmt = select(KnowledgeEntity).where(KnowledgeEntity.novel_id == novel_id)
        if entity_type:
            stmt = stmt.where(KnowledgeEntity.entity_type == entity_type)
        if name:
            stmt = stmt.where(KnowledgeEntity.name.contains(name))
        result = await session.execute(stmt)
        entities = result.scalars().all()
        return [_entity_to_response(e) for e in entities]


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(novel_id: str, entity_id: str):
    """查询单个实体详情"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeEntity).where(and_(
                KnowledgeEntity.id == entity_id,
                KnowledgeEntity.novel_id == novel_id,
            ))
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return _entity_to_response(entity)


@router.get("/entities/{entity_id}/history", response_model=list[StateSnapshotResponse])
async def get_entity_history(novel_id: str, entity_id: str):
    """查询单个实体的历史状态演化轨迹"""
    async with get_db_session() as session:
        # Check if entity exists and is in the current novel project
        ent_result = await session.execute(
            select(KnowledgeEntity).where(and_(
                KnowledgeEntity.id == entity_id,
                KnowledgeEntity.novel_id == novel_id,
            ))
        )
        entity = ent_result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Query all states in ascending order of chapters
        states_result = await session.execute(
            select(KnowledgeEntityState)
            .where(and_(
                KnowledgeEntityState.entity_id == entity_id,
                KnowledgeEntityState.novel_id == novel_id,
            ))
            .order_by(KnowledgeEntityState.chapter_number.asc())
        )
        states = states_result.scalars().all()

        return [
            StateSnapshotResponse(
                id=s.id,
                novel_id=s.novel_id,
                entity_id=s.entity_id,
                chapter_number=s.chapter_number,
                attributes=s.attributes or {},
                created_at=s.created_at.isoformat()
            )
            for s in states
        ]


@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(novel_id: str, body: EntityCreate):
    """手动创建实体"""
    entity_id = str(uuid.uuid4())
    async with get_db_session() as session:
        entity = KnowledgeEntity(
            id=entity_id, novel_id=novel_id,
            entity_type=body.entity_type, name=body.name,
            aliases=body.aliases, attributes=body.attributes,
            first_chapter=body.first_chapter, source="manual",
        )
        session.add(entity)
        session.add(
            KnowledgeEntityState(
                id=str(uuid.uuid4()),
                novel_id=novel_id,
                entity_id=entity_id,
                chapter_number=body.first_chapter,
                attributes=body.attributes,
            )
        )
    return EntityResponse(
        id=entity_id, entity_type=body.entity_type, name=body.name,
        aliases=body.aliases, attributes=body.attributes,
        first_chapter=body.first_chapter, last_chapter=None, source="manual",
    )



@router.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(novel_id: str, entity_id: str, body: EntityUpdate):
    """手动修正实体"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeEntity).where(and_(
                KnowledgeEntity.id == entity_id,
                KnowledgeEntity.novel_id == novel_id,
            ))
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        if body.entity_type is not None:
            entity.entity_type = body.entity_type
        if body.name is not None:
            entity.name = body.name
        if body.aliases is not None:
            entity.aliases = body.aliases
        if body.attributes is not None:
            entity.attributes = body.attributes
        session.add(entity)

    return _entity_to_response(entity)


@router.delete("/entities/{entity_id}", status_code=204)
async def delete_entity(novel_id: str, entity_id: str):
    """删除实体（级联删除关联三元组）"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeEntity).where(and_(
                KnowledgeEntity.id == entity_id,
                KnowledgeEntity.novel_id == novel_id,
            ))
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        await session.execute(
            delete(KnowledgeTriple).where(
                (KnowledgeTriple.subject_id == entity_id)
                | (KnowledgeTriple.object_id == entity_id)
            )
        )
        await session.delete(entity)


# --- Triple Endpoints ---

@router.get("/triples")
async def list_triples(
    novel_id: str,
    subject_id: str | None = Query(None),
    object_id: str | None = Query(None),
    predicate: str | None = Query(None),
    chapter: int | None = Query(None),
):
    """查询三元组列表"""
    async with get_db_session() as session:
        stmt = select(KnowledgeTriple).where(KnowledgeTriple.novel_id == novel_id)
        if subject_id:
            stmt = stmt.where(KnowledgeTriple.subject_id == subject_id)
        if object_id:
            stmt = stmt.where(KnowledgeTriple.object_id == object_id)
        if predicate:
            stmt = stmt.where(KnowledgeTriple.predicate == predicate)
        if chapter:
            stmt = stmt.where(KnowledgeTriple.chapter_number == chapter)
        stmt = stmt.where(KnowledgeTriple.status != "deleted")
        result = await session.execute(stmt.limit(100))
        triples = result.scalars().all()
        return [
            {
                "id": t.id, "subject_id": t.subject_id,
                "predicate": t.predicate, "object_id": t.object_id,
                "chapter_number": t.chapter_number,
                "confidence": t.confidence, "status": t.status,
            }
            for t in triples
        ]



@router.post("/triples", status_code=201)
async def create_triple(novel_id: str, body: TripleCreate):
    """手动创建三元组"""
    triple_id = str(uuid.uuid4())
    async with get_db_session() as session:
        triple = KnowledgeTriple(
            id=triple_id, novel_id=novel_id,
            subject_id=body.subject_id, predicate=body.predicate,
            object_id=body.object_id, chapter_number=body.chapter_number,
            confidence=body.confidence, status="active",
            metadata_={}, source="manual",
        )
        session.add(triple)
    return {"id": triple_id, "status": "created"}


@router.put("/triples/{triple_id}")
async def update_triple(novel_id: str, triple_id: str, body: TripleUpdate):
    """修正三元组"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeTriple).where(and_(
                KnowledgeTriple.id == triple_id,
                KnowledgeTriple.novel_id == novel_id,
            ))
        )
        triple = result.scalar_one_or_none()
        if not triple:
            raise HTTPException(status_code=404, detail="Triple not found")
        if body.predicate is not None:
            triple.predicate = body.predicate
        if body.confidence is not None:
            triple.confidence = body.confidence
        if body.status is not None:
            triple.status = body.status
        session.add(triple)
    return {"id": triple_id, "status": "updated"}


@router.delete("/triples/{triple_id}", status_code=204)
async def delete_triple(novel_id: str, triple_id: str):
    """删除三元组（标记 status=deleted）"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeTriple).where(and_(
                KnowledgeTriple.id == triple_id,
                KnowledgeTriple.novel_id == novel_id,
            ))
        )
        triple = result.scalar_one_or_none()
        if not triple:
            raise HTTPException(status_code=404, detail="Triple not found")
        triple.status = "deleted"
        session.add(triple)


# --- Extraction Endpoints ---

@router.post("/extract/{chapter_number}")
async def extract_chapter(novel_id: str, chapter_number: int):
    """手动触发单章抽取"""
    from src.api.models.db_models import Chapter

    async with get_db_session() as session:
        result = await session.execute(
            select(Chapter).where(and_(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number,
            ))
        )
        chapter = result.scalar_one_or_none()
        if not chapter or not chapter.content:
            raise HTTPException(status_code=404, detail="Chapter not found or empty")
        chapter_text = chapter.content

    service = get_knowledge_graph_service()
    result_data = await service.extract_from_chapter(
        novel_id, chapter_number, chapter_text
    )
    return result_data


@router.post("/extract-all")
async def extract_all(novel_id: str):
    """全量重新抽取"""
    from src.api.models.db_models import Chapter

    async with get_db_session() as session:
        # 清除已有数据（entities CASCADE 自动删除关联 triples）
        await session.execute(
            delete(KnowledgeEntity).where(KnowledgeEntity.novel_id == novel_id)
        )
        await session.execute(
            delete(KnowledgeExtractionLog).where(
                KnowledgeExtractionLog.novel_id == novel_id
            )
        )

    # 逐章抽取
    async with get_db_session() as session:
        result = await session.execute(
            select(Chapter).where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = list(result.scalars().all())

    service = get_knowledge_graph_service()
    total_entities = 0
    total_triples = 0
    for ch in chapters:
        if ch.content:
            r = await service.extract_from_chapter(
                novel_id, ch.chapter_number, ch.content
            )
            total_entities += r.get("entities_count", 0)
            total_triples += r.get("triples_count", 0)

    return {
        "chapters_processed": len(chapters),
        "total_entities": total_entities,
        "total_triples": total_triples,
    }



@router.get("/extraction-logs")
async def list_extraction_logs(novel_id: str):
    """查询抽取日志"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeExtractionLog)
            .where(KnowledgeExtractionLog.novel_id == novel_id)
            .order_by(KnowledgeExtractionLog.chapter_number)
        )
        logs = result.scalars().all()
        return [
            {
                "id": log.id, "chapter_number": log.chapter_number,
                "status": log.status, "entities_count": log.entities_count,
                "triples_count": log.triples_count, "duration_ms": log.duration_ms,
                "error_message": log.error_message,
            }
            for log in logs
        ]


@router.get("/logs")
async def list_knowledge_graph_logs(novel_id: str):
    """获取知识图谱抽取日志列表（最新优先，最多 100 条）"""
    async with get_db_session() as session:
        result = await session.execute(
            select(KnowledgeExtractionLog)
            .where(KnowledgeExtractionLog.novel_id == novel_id)
            .order_by(KnowledgeExtractionLog.created_at.desc())
            .limit(100)
        )
        logs = result.scalars().all()
        return [
            {
                "chapter_number": log.chapter_number,
                "status": log.status,
                "entities_count": log.entities_count,
                "triples_count": log.triples_count,
                "duration_ms": log.duration_ms,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]


@router.get("/conflicts")
async def list_kg_conflicts(novel_id: str):
    """获取一致性检查冲突记录（从 ChapterVersion.kg_conflicts 字段查询）"""
    from src.api.models.db_models import ChapterVersion

    async with get_db_session() as session:
        result = await session.execute(
            select(ChapterVersion)
            .where(and_(
                ChapterVersion.novel_id == novel_id,
                ChapterVersion.kg_conflicts.isnot(None),
            ))
            .order_by(ChapterVersion.created_at.desc())
            .limit(100)
        )
        versions = result.scalars().all()
        return [
            {
                "chapter_number": v.chapter_number,
                "version_number": v.version_number,
                "conflicts": v.kg_conflicts,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]


@router.get("/visualization", response_model=VisualizationResponse)
async def get_visualization(novel_id: str):
    """获取可视化数据（nodes + edges 格式）"""
    async with get_db_session() as session:
        # Nodes
        ent_result = await session.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.novel_id == novel_id)
        )
        entities = list(ent_result.scalars().all())
        nodes = [
            {
                "id": e.id, "name": e.name,
                "type": e.entity_type,
                "attributes": e.attributes or {},
                "first_chapter": e.first_chapter,
                "last_chapter": e.last_chapter,
            }
            for e in entities
        ]

        # Edges
        triple_result = await session.execute(
            select(KnowledgeTriple).where(and_(
                KnowledgeTriple.novel_id == novel_id,
                KnowledgeTriple.status == "active",
            ))
        )
        triples = list(triple_result.scalars().all())
        edges = [
            {
                "id": t.id,
                "source": t.subject_id,
                "target": t.object_id,
                "predicate": t.predicate,
                "chapter": t.chapter_number,
                "confidence": t.confidence,
            }
            for t in triples
        ]

    return VisualizationResponse(nodes=nodes, edges=edges)


@router.post("/consistency-check/{chapter_number}", response_model=ConsistencyResult)
async def run_consistency_check(novel_id: str, chapter_number: int):
    """手动触发一致性检查"""
    from datetime import datetime

    from src.api.models.db_models import Chapter

    async with get_db_session() as session:
        result = await session.execute(
            select(Chapter).where(and_(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number,
            ))
        )
        chapter = result.scalar_one_or_none()
        if not chapter or not chapter.content:
            raise HTTPException(status_code=404, detail="Chapter not found or empty")
        chapter_text = chapter.content

    service = get_knowledge_graph_service()
    conflicts = await service.check_consistency(novel_id, chapter_number, chapter_text)
    return ConsistencyResult(
        conflicts=conflicts,
        checked_at=datetime.now(UTC).isoformat(),
    )


@router.get("/three-layer")
async def get_three_layer_graph(novel_id: str, min_frequency: int = Query(default=2, ge=1)):
    """获取三层关系图谱数据"""
    service = get_knowledge_graph_service()
    data = await service.get_three_layer_graph(novel_id, min_frequency=min_frequency)
    return data

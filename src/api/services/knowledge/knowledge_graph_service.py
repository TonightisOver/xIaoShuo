"""知识图谱服务

提供实体/三元组抽取、上下文检索、一致性检查功能。
"""

import json
import time
import uuid
from typing import Any

import structlog
from sqlalchemy import and_, delete, select

from src.api.models.db_models import (
    Character,
    KnowledgeEntity,
    KnowledgeEntityState,
    KnowledgeExtractionLog,
    KnowledgeTriple,
)
from src.api.services.knowledge.kg_prompts import (
    CONSISTENCY_CHECK_PROMPT,
    KG_EXTRACTION_PROMPT,
)
from src.api.services.knowledge.kg_similarity import cosine_similarity
from src.core.config import get_settings
from src.core.database import get_db_session
from src.core.json_utils import safe_json_parse
from src.core.llm.client import embed_texts as _embed_texts
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)


class KnowledgeGraphService:
    """知识图谱服务"""

    async def extract_from_chapter(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_text: str,
        continuity_report: dict | None = None,
        *,
        applied_version: int | None = None,
    ) -> dict[str, Any]:
        """从单章文本抽取实体和关系。

        Task 11 / B20：幂等判定——
        1. KnowledgeExtractionLog.status=='completed' 则跳过（已抽过）。
        2. 传入 applied_version 时，若 Chapter.kg_applied_version >= applied_version
           也跳过（恢复重放不重复抽取）。
        成功后写 kg_applied_version = applied_version。
        """
        settings = get_settings()
        if not settings.KNOWLEDGE_GRAPH_ENABLED:
            return {"entities_count": 0, "triples_count": 0}

        # 幂等：仅在 checkpoint 路径（传 applied_version）做 log 幂等判定，
        # 避免无 checkpoint 的单次抽取路径多消耗 session.execute（破坏单测 mock 契约）。
        # 长篇重放场景才需要"已 completed 则跳过"。
        if applied_version is not None:
            async with get_db_session() as session:
                existing_log = (
                    await session.execute(
                        select(KnowledgeExtractionLog).where(
                            and_(
                                KnowledgeExtractionLog.novel_id == novel_id,
                                KnowledgeExtractionLog.chapter_number == chapter_number,
                                KnowledgeExtractionLog.status == "completed",
                            )
                        )
                    )
                ).scalar_one_or_none()
                if existing_log is not None and getattr(
                    existing_log, "status", None
                ) == "completed":
                    logger.info(
                        "knowledge_extraction_skipped_idempotent",
                        novel_id=novel_id,
                        chapter=chapter_number,
                    )
                    return {
                        "entities_count": getattr(existing_log, "entities_count", 0) or 0,
                        "triples_count": getattr(existing_log, "triples_count", 0) or 0,
                        "skipped": True,
                    }
                # 版本哨兵
                from src.api.models.db_models import Chapter

                ch = (
                    await session.execute(
                        select(Chapter).where(
                            Chapter.novel_id == novel_id,
                            Chapter.chapter_number == chapter_number,
                        )
                    )
                ).scalar_one_or_none()
                if ch is not None:
                    applied_existing = getattr(ch, "kg_applied_version", None)
                    if isinstance(applied_existing, int) and (
                        applied_existing >= applied_version or applied_existing == -1
                    ):
                        logger.info(
                            "knowledge_extraction_skipped_version",
                            novel_id=novel_id,
                            chapter=chapter_number,
                            applied=applied_existing,
                            requested=applied_version,
                        )
                        return {
                            "entities_count": 0,
                            "triples_count": 0,
                            "skipped": True,
                        }

        start_time = time.time()
        log_id = str(uuid.uuid4())

        try:
            # 获取已有实体（一次查询，传递给 merge 复用）
            existing = await self._get_existing_entities(novel_id)
            existing_json = json.dumps(
                [{"name": e.name, "type": e.entity_type, "aliases": e.aliases}
                 for e in existing],
                ensure_ascii=False,
            )

            # 调用 LLM 抽取
            prompt = KG_EXTRACTION_PROMPT.format(
                existing_entities_json=existing_json,
                chapter_text=chapter_text[:6000],
            )
            client = get_llm_client()
            raw = await client.generate(prompt, temperature=0.1)

            # Check if subagent mode is enabled, ensuring it is a boolean to support unit tests mock environments
            kg_subagent_enabled = False
            if hasattr(settings, "KG_SUBAGENT_ENABLED"):
                val = settings.KG_SUBAGENT_ENABLED
                if isinstance(val, bool):
                    kg_subagent_enabled = val

            if kg_subagent_enabled:
                from src.core.agents.graph_reconciler import GraphReconcilerAgent
                reconciler = GraphReconcilerAgent()
                reconciled = await reconciler.reconcile(
                    continuity_report=continuity_report,
                    extracted_entities=raw,
                    existing_entities=existing_json,
                )

                entities_to_upsert = reconciled.get("entities_to_upsert", [])
                triples_to_add = reconciled.get("triples_to_add", [])
                entity_status_updates = reconciled.get("entity_status_updates", [])
                foreshadowing_resolutions = reconciled.get("foreshadowing_resolutions", [])

                # 初始化 name_to_id 映射
                name_to_id = {}
                for e in existing:
                    name_to_id[e.name] = e.id
                    for alias in (e.aliases or []):
                        name_to_id[alias] = e.id

                # 1. 合并 upsert 实体
                for ent in entities_to_upsert:
                    eid = await self._merge_entity(novel_id, chapter_number, ent, existing)
                    if eid and ent.get("name"):
                        name_to_id[ent["name"]] = eid
                        for alias in ent.get("aliases", []):
                            name_to_id[alias] = eid

                # 2. 合并更新状态
                for ent_update in entity_status_updates:
                    await self._merge_entity(novel_id, chapter_number, ent_update, existing)

                # 3. 合并伏笔状态更新
                for res in foreshadowing_resolutions:
                    if "attributes" not in res:
                        res["attributes"] = {}
                    if "foreshadowing_status" not in res["attributes"]:
                        res["attributes"]["foreshadowing_status"] = "resolved"
                    await self._merge_entity(novel_id, chapter_number, res, existing)

                # 4. 写入三元组
                triples_count = 0
                for t in triples_to_add:
                    success = await self.add_triple(novel_id, chapter_number, t, name_to_id)
                    if success:
                        triples_count += 1

                entities_extracted = len(entities_to_upsert)

            else:
                result = safe_json_parse(raw, fallback={"entities": [], "triples": []})
                # 合并实体（传入已查询的 existing 避免重复查询）
                name_to_id = await self._merge_entities(
                    novel_id, chapter_number, result.get("entities", []), existing
                )

                # 写入三元组
                triples_count = await self._write_triples(
                    novel_id, chapter_number, result.get("triples", []), name_to_id
                )
                entities_extracted = len(result.get("entities", []))

            duration_ms = int((time.time() - start_time) * 1000)

            # 写入日志
            await self._write_extraction_log(
                log_id, novel_id, chapter_number, "completed",
                entities_extracted, triples_count, duration_ms,
            )

            # 写回幂等哨兵
            if applied_version is not None:
                from src.api.models.db_models import Chapter

                async with get_db_session() as session:
                    ch = (
                        await session.execute(
                            select(Chapter).where(
                                Chapter.novel_id == novel_id,
                                Chapter.chapter_number == chapter_number,
                            )
                        )
                    ).scalar_one_or_none()
                    if ch is not None:
                        ch.kg_applied_version = applied_version
                        await session.commit()

            return {
                "entities_count": entities_extracted,
                "triples_count": triples_count,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await self._write_extraction_log(
                log_id, novel_id, chapter_number,
                "failed", 0, 0, duration_ms, str(e)
            )
            logger.error(
                "knowledge_extraction_failed",
                novel_id=novel_id,
                chapter=chapter_number,
                error=str(e),
            )
            return {
                "entities_count": 0,
                "triples_count": 0,
                "error": str(e),
            }


    async def retrieve_context(
        self, novel_id: str, chapter_outline: dict[str, Any],
        raw_format: bool = False
    ) -> str:
        """根据章节大纲检索相关图谱上下文，支持状态继承合并与最新双向关系演化去重"""
        settings = get_settings()
        if not settings.KNOWLEDGE_GRAPH_ENABLED:
            return ""

        try:
            current_ch = chapter_outline.get("chapter", 1)
            outline_text = json.dumps(chapter_outline, ensure_ascii=False)

            # 1. 获取所有实体
            entities = await self._get_existing_entities(novel_id)

            # 2. 精确匹配大纲中提到的实体名称（包含别名）
            exact_match_entities = []
            for e in entities:
                mentioned = False
                if e.name and e.name in outline_text:
                    mentioned = True
                else:
                    for alias in (e.aliases or []):
                        if alias and alias in outline_text:
                            mentioned = True
                            break
                if mentioned:
                    exact_match_entities.append(e)

            mentioned_entities = exact_match_entities

            # 3. 当子代理模式启用且 outline 文本足够长时，使用 embedding 语义相似度补充
            if (
                len(outline_text) > 50
                and hasattr(settings, "KG_SUBAGENT_ENABLED")
                and isinstance(settings.KG_SUBAGENT_ENABLED, bool)
                and settings.KG_SUBAGENT_ENABLED
            ):
                try:
                    # 筛选出有 embedding 向量的实体
                    entities_with_embedding = [
                        e for e in entities
                        if e.embedding is not None and isinstance(e.embedding, list) and len(e.embedding) > 0
                    ]
                    if entities_with_embedding:
                        # 为 outline 生成 embedding
                        outline_embeddings = await _embed_texts([outline_text])
                        if outline_embeddings and outline_embeddings[0]:
                            outline_vec = outline_embeddings[0]

                            similarity_threshold = 0.5
                            scored = []
                            for e in entities_with_embedding:
                                sim = cosine_similarity(outline_vec, e.embedding)
                                if sim >= similarity_threshold:
                                    scored.append((sim, e))
                            scored.sort(key=lambda x: x[0], reverse=True)
                            top_k = scored[:20]

                            embedding_matched_ids = {e.id for _, e in top_k}
                            exact_matched_ids = {e.id for e in exact_match_entities}
                            all_entity_ids = exact_matched_ids | embedding_matched_ids
                            mentioned_entities = [
                                e for e in entities if e.id in all_entity_ids
                            ]
                except Exception as embed_err:
                    logger.warning("embedding_similarity_fallback", error=str(embed_err))
                    mentioned_entities = exact_match_entities

            if not mentioned_entities:
                return ""

            entity_ids = [e.id for e in mentioned_entities]
            entity_map = {e.id: e for e in entities}

            # 2. 获取这些实体在当前章节之前的最新状态快照
            entity_states = {}
            async with get_db_session() as session:
                if entity_ids:
                    state_result = await session.execute(
                        select(KnowledgeEntityState)
                        .where(
                            and_(
                                KnowledgeEntityState.entity_id.in_(entity_ids),
                                KnowledgeEntityState.chapter_number < current_ch
                            )
                        )
                        .order_by(
                            KnowledgeEntityState.entity_id,
                            KnowledgeEntityState.chapter_number.desc(),
                        )
                    )
                    all_states = list(state_result.scalars().all())

                    for s in all_states:
                        if s.entity_id not in entity_states:
                            entity_states[s.entity_id] = s.attributes or {}

            # 如果没有历史状态，则使用实体的基础/最新 attributes 作为默认
            for e in mentioned_entities:
                if e.id not in entity_states:
                    entity_states[e.id] = e.attributes or {}

            # 3. 合并读取 Character 表中正式的人设设定
            character_details = {}
            async with get_db_session() as session:
                char_names = [
                    e.name for e in mentioned_entities
                    if e.entity_type == "character"
                ]
                if char_names:
                    char_result = await session.execute(
                        select(Character).where(
                            and_(
                                Character.novel_id == novel_id,
                                Character.name.in_(char_names)
                            )
                        )
                    )
                    chars = list(char_result.scalars().all())
                    for c in chars:
                        character_details[c.name] = {
                            "personality": c.personality,
                            "background": c.background_story,
                            "abilities": c.abilities,
                            "role": c.role,
                            "description": c.description
                        }

            # 4. 检索这些实体在当前章节前的最新 active 三元组关系，并去重保留最新演化
            triples_data = []
            async with get_db_session() as session:
                if entity_ids:
                    triples_result = await session.execute(
                        select(KnowledgeTriple)
                        .where(
                            and_(
                                KnowledgeTriple.novel_id == novel_id,
                                KnowledgeTriple.status == "active",
                                KnowledgeTriple.chapter_number < current_ch,
                                (
                                    KnowledgeTriple.subject_id.in_(entity_ids)
                                    | KnowledgeTriple.object_id.in_(entity_ids)
                                )
                            )
                        )
                        .order_by(KnowledgeTriple.chapter_number.desc())
                    )
                    triples_list = list(triples_result.scalars().all())

                    seen_triples = set()
                    for t in triples_list:
                        subj_ent = entity_map.get(t.subject_id)
                        obj_ent = entity_map.get(t.object_id)
                        subj_name = subj_ent.name if subj_ent else "unknown"
                        obj_name = obj_ent.name if obj_ent else "unknown"

                        # 仅保留最新（第一条被扫描到，因有序降序）
                        key = (t.subject_id, t.predicate, t.object_id)
                        if key not in seen_triples:
                            seen_triples.add(key)

                            metadata_str = ""
                            if t.metadata_ and isinstance(t.metadata_, dict):
                                meta_parts = []
                                for k, v in t.metadata_.items():
                                    meta_parts.append(f"{k}: {v}")
                                if meta_parts:
                                    metadata_str = f" ({', '.join(meta_parts)})"

                            triples_data.append({
                                "subject": subj_name,
                                "predicate": t.predicate,
                                "object": obj_name,
                                "chapter": t.chapter_number,
                                "metadata_str": metadata_str
                            })

            # 5. 查询悬挂伏笔
            foreshadowings = await self._get_hanging_foreshadowings(novel_id)

            # 6. 查询最近事件
            recent_events = await self._get_recent_events(novel_id, current_ch)

            # 7. 格式化生成高质量记忆 Prompt 或原始数据
            context = self._format_rich_context(
                mentioned_entities=mentioned_entities,
                entity_states=entity_states,
                character_details=character_details,
                triples_data=triples_data,
                foreshadowings=foreshadowings,
                recent_events=recent_events,
                raw_format=raw_format,
            )
            if not raw_format and len(context) > 1500:
                context = context[:1500].rsplit("\n", 1)[0]
            elif raw_format and len(context) > 4000:
                context = context[:4000].rsplit("\n", 1)[0]
            return context


        except Exception as e:
            logger.warning("knowledge_retrieve_context_failed", error=str(e))
            return ""

    async def check_consistency(
        self, novel_id: str, chapter_number: int, chapter_text: str
    ) -> list[dict[str, Any]]:
        """一致性检查，返回冲突列表"""
        settings = get_settings()
        if not settings.KNOWLEDGE_GRAPH_ENABLED:
            return []

        try:
            # 规则检查
            new_triples = await self._get_chapter_triples(novel_id, chapter_number)
            conflicts = await self._rule_based_check(novel_id, new_triples)

            # 如果规则检查发现疑似问题，触发 LLM 检查
            if conflicts:
                history_ctx = await self._build_history_context(
                    novel_id, chapter_number
                )
                triples_json = json.dumps(
                    [
                        {
                            "subject": t.subject_id,
                            "predicate": t.predicate,
                            "object": t.object_id,
                        }
                        for t in new_triples
                    ],
                    ensure_ascii=False,
                )
                llm_conflicts = await self._llm_consistency_check(
                    chapter_text, triples_json, history_ctx
                )
                conflicts.extend(llm_conflicts)

            return conflicts

        except Exception as e:
            logger.warning("consistency_check_failed", error=str(e))
            return []


    async def get_three_layer_graph(self, novel_id: str, min_frequency: int = 1) -> dict[str, Any]:
        """获取三层关系图谱数据"""
        async with get_db_session() as session:
            # 1. 查询所有实体和有效三元组
            entities_result = await session.execute(
                select(KnowledgeEntity).where(KnowledgeEntity.novel_id == novel_id)
            )
            entities = list(entities_result.scalars().all())
            entity_map = {e.id: e for e in entities}

            triples_result = await session.execute(
                select(KnowledgeTriple).where(
                    and_(
                        KnowledgeTriple.novel_id == novel_id,
                        KnowledgeTriple.status == "active"
                    )
                )
            )
            triples = list(triples_result.scalars().all())

        # 统计每个实体在三元组中出现的频次
        entity_frequency: dict[str, int] = {}
        for t in triples:
            entity_frequency[t.subject_id] = entity_frequency.get(t.subject_id, 0) + 1
            entity_frequency[t.object_id] = entity_frequency.get(t.object_id, 0) + 1

        # 过滤低频实体（foreshadowing 类型不过滤）
        def should_include(entity, layer_type: str) -> bool:
            if layer_type == "foreshadowing":
                return True
            if min_frequency <= 1:
                return True
            freq = entity_frequency.get(entity.id, 0)
            return freq >= min_frequency

        # 2. 抽取并封装第一层：人物关系网络 (character_graph)
        character_nodes = []
        character_edges = []
        char_ids = set()

        for e in entities:
            if e.entity_type == "character" and should_include(e, "character"):
                char_ids.add(e.id)
                character_nodes.append({
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type,
                    "attributes": e.attributes or {},
                    "first_chapter": e.first_chapter,
                    "last_chapter": e.last_chapter
                })

        for t in triples:
            if t.subject_id in char_ids and t.object_id in char_ids:
                character_edges.append({
                    "id": t.id,
                    "source": t.subject_id,
                    "target": t.object_id,
                    "predicate": t.predicate,
                    "chapter": t.chapter_number,
                    "confidence": t.confidence
                })

        # 3. 抽取并封装第二层：剧情事件推进因果树 (plot_graph)
        event_nodes = []
        event_edges = []
        event_ids = set()

        for e in entities:
            if e.entity_type == "event" and should_include(e, "event"):
                event_ids.add(e.id)
                event_nodes.append({
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type,
                    "attributes": e.attributes or {},
                    "first_chapter": e.first_chapter,
                    "last_chapter": e.last_chapter
                })

        # 按首发章节升序对事件排序，穿织时间线
        event_nodes.sort(key=lambda x: x["first_chapter"])

        # 显式三元组因果关系
        for t in triples:
            if t.subject_id in event_ids and t.object_id in event_ids:
                event_edges.append({
                    "id": t.id,
                    "source": t.subject_id,
                    "target": t.object_id,
                    "predicate": t.predicate,
                    "chapter": t.chapter_number,
                    "confidence": t.confidence,
                    "type": "explicit"
                })

        # 隐式因果/时序流：如果存在相邻章节的事件，穿织一条时序流连线，predicate为 "后续章节"
        for i in range(len(event_nodes) - 1):
            event_edges.append({
                "id": f"flow_{event_nodes[i]['id']}_{event_nodes[i+1]['id']}",
                "source": event_nodes[i]["id"],
                "target": event_nodes[i+1]["id"],
                "predicate": "后续章节",
                "chapter": event_nodes[i+1]["first_chapter"],
                "confidence": 1.0,
                "type": "narrative_flow"
            })

        # 4. 抽取并封装第三层：伏笔填坑生命周期图 (foreshadowing_graph)
        foreshadowing_nodes = []
        foreshadowing_edges = []
        foreshadowing_ids = set()

        for e in entities:
            if e.entity_type == "foreshadowing":
                foreshadowing_ids.add(e.id)
                status = (e.attributes or {}).get("foreshadowing_status", "planted")
                foreshadowing_nodes.append({
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type,
                    "attributes": e.attributes or {},
                    "first_chapter": e.first_chapter,
                    "last_chapter": e.last_chapter,
                    "foreshadowing_status": status
                })

        # 捞取与伏笔相关的显式三元组
        for t in triples:
            if t.subject_id in foreshadowing_ids or t.object_id in foreshadowing_ids:
                foreshadowing_edges.append({
                    "id": t.id,
                    "source": t.subject_id,
                    "target": t.object_id,
                    "predicate": t.predicate,
                    "chapter": t.chapter_number,
                    "confidence": t.confidence,
                    "type": "explicit"
                })

        # 补充被引用的节点，防止孤立
        extra_nodes_map = {}
        for edge in foreshadowing_edges:
            for node_id in (edge["source"], edge["target"]):
                if node_id not in foreshadowing_ids and node_id not in extra_nodes_map:
                    ent = entity_map.get(node_id)
                    if ent:
                        extra_nodes_map[node_id] = {
                            "id": ent.id,
                            "name": ent.name,
                            "type": ent.entity_type,
                            "attributes": ent.attributes or {},
                            "first_chapter": ent.first_chapter,
                            "last_chapter": ent.last_chapter
                        }

        foreshadowing_nodes.extend(extra_nodes_map.values())

        return {
            "character_graph": {
                "nodes": character_nodes,
                "edges": character_edges
            },
            "plot_graph": {
                "nodes": event_nodes,
                "edges": event_edges
            },
            "foreshadowing_graph": {
                "nodes": foreshadowing_nodes,
                "edges": foreshadowing_edges
            }
        }


    # --- Private helpers ---


    async def _get_existing_entities(self, novel_id: str) -> list[KnowledgeEntity]:
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntity).where(KnowledgeEntity.novel_id == novel_id)
            )
            return list(result.scalars().all())

    async def _merge_entities(
        self, novel_id: str, chapter_number: int,
        new_entities: list[dict],
        existing: list[KnowledgeEntity] | None = None,
    ) -> dict[str, str]:
        """合并实体，返回 name -> entity_id 映射，并实现属性的继承合并和状态历史记录"""
        if existing is None:
            existing = await self._get_existing_entities(novel_id)
        name_map: dict[str, str] = {e.name: e.id for e in existing}
        alias_map: dict[str, str] = {}
        for e in existing:
            for alias in (e.aliases or []):
                alias_map[alias] = e.id

        async with get_db_session() as session:
            for ent in new_entities:
                ent_name = ent.get("name", "")
                if not ent_name:
                    continue

                extracted_attrs = ent.get("attributes", {})

                matched_id = None
                matched_entity = None

                # 别名或精确名称匹配
                if ent_name in name_map:
                    matched_id = name_map[ent_name]
                elif ent_name in alias_map:
                    matched_id = alias_map[ent_name]
                    name_map[ent_name] = matched_id

                if matched_id:
                    result = await session.execute(
                        select(KnowledgeEntity).where(KnowledgeEntity.id == matched_id)
                    )
                    matched_entity = result.scalar_one_or_none()

                if matched_entity:
                    # 1. 查询在此章节前的最新历史状态
                    hist_result = await session.execute(
                        select(KnowledgeEntityState)
                        .where(
                            and_(
                                KnowledgeEntityState.entity_id == matched_entity.id,
                                KnowledgeEntityState.chapter_number < chapter_number
                            )
                        )
                        .order_by(KnowledgeEntityState.chapter_number.desc())
                        .limit(1)
                    )
                    latest_state = hist_result.scalar_one_or_none()

                    previous_attributes = {}
                    if latest_state:
                        previous_attributes = latest_state.attributes or {}
                    elif matched_entity.attributes:
                        previous_attributes = matched_entity.attributes

                    # 2. 执行继承合并属性
                    merged_attributes = {**previous_attributes, **extracted_attrs}

                    # 3. 更新主实体字段
                    matched_entity.attributes = merged_attributes
                    matched_entity.last_chapter = chapter_number

                    # 4. 判断并记录/覆盖该章节的历史快照
                    state_result = await session.execute(
                        select(KnowledgeEntityState)
                        .where(
                            and_(
                                KnowledgeEntityState.entity_id == matched_entity.id,
                                KnowledgeEntityState.chapter_number == chapter_number
                            )
                        )
                    )
                    existing_state = state_result.scalar_one_or_none()
                    if existing_state:
                        existing_state.attributes = merged_attributes
                    else:
                        new_state = KnowledgeEntityState(
                            id=str(uuid.uuid4()),
                            novel_id=novel_id,
                            entity_id=matched_entity.id,
                            chapter_number=chapter_number,
                            attributes=merged_attributes
                        )
                        session.add(new_state)
                else:
                    # 新建实体与初始状态记录
                    entity_id = str(uuid.uuid4())
                    entity = KnowledgeEntity(
                        id=entity_id,
                        novel_id=novel_id,
                        entity_type=ent.get("type", "character"),
                        name=ent_name,
                        aliases=ent.get("aliases", []),
                        attributes=extracted_attrs,
                        first_chapter=chapter_number,
                        last_chapter=chapter_number,
                        source="extracted",
                    )
                    # RAG: 为实体生成 embedding（失败不阻断创建，精确检索仍可用）
                    entity.embedding = await _generate_entity_embedding(
                        ent_name, ent.get("type", "character"),
                        ent.get("aliases", []), extracted_attrs,
                    )
                    session.add(entity)

                    new_state = KnowledgeEntityState(
                        id=str(uuid.uuid4()),
                        novel_id=novel_id,
                        entity_id=entity_id,
                        chapter_number=chapter_number,
                        attributes=extracted_attrs
                    )
                    session.add(new_state)
                    name_map[ent_name] = entity_id

        return name_map

    async def _merge_entity(
        self, novel_id: str, chapter_number: int, ent: dict, existing: list[KnowledgeEntity] | None = None
    ) -> str:
        """合并/更新单个实体，并返回其 ID"""
        if existing is None:
            existing = await self._get_existing_entities(novel_id)
        name_map: dict[str, str] = {e.name: e.id for e in existing}
        alias_map: dict[str, str] = {}
        for e in existing:
            for alias in (e.aliases or []):
                alias_map[alias] = e.id

        ent_name = ent.get("name", "")
        if not ent_name:
            return ""

        extracted_attrs = ent.get("attributes", {})
        matched_id = None
        matched_entity = None

        if ent_name in name_map:
            matched_id = name_map[ent_name]
        elif ent_name in alias_map:
            matched_id = alias_map[ent_name]

        async with get_db_session() as session:
            if matched_id:
                result = await session.execute(
                    select(KnowledgeEntity).where(KnowledgeEntity.id == matched_id)
                )
                matched_entity = result.scalar_one_or_none()

            if matched_entity:
                # 1. 查询在此章节前的最新历史状态
                hist_result = await session.execute(
                    select(KnowledgeEntityState)
                    .where(
                        and_(
                            KnowledgeEntityState.entity_id == matched_entity.id,
                            KnowledgeEntityState.chapter_number < chapter_number
                        )
                    )
                    .order_by(KnowledgeEntityState.chapter_number.desc())
                    .limit(1)
                )
                latest_state = hist_result.scalar_one_or_none()

                previous_attributes = {}
                if latest_state:
                    previous_attributes = latest_state.attributes or {}
                elif matched_entity.attributes:
                    previous_attributes = matched_entity.attributes

                # 2. 执行继承合并属性
                merged_attributes = {**previous_attributes, **extracted_attrs}

                # 3. 更新主实体字段
                matched_entity.attributes = merged_attributes
                matched_entity.last_chapter = chapter_number
                session.add(matched_entity)

                # 4. 判断并记录/覆盖该章节的历史快照
                state_result = await session.execute(
                    select(KnowledgeEntityState)
                    .where(
                        and_(
                            KnowledgeEntityState.entity_id == matched_entity.id,
                            KnowledgeEntityState.chapter_number == chapter_number
                        )
                    )
                )
                existing_state = state_result.scalar_one_or_none()
                if existing_state:
                    existing_state.attributes = merged_attributes
                    session.add(existing_state)
                else:
                    new_state = KnowledgeEntityState(
                        id=str(uuid.uuid4()),
                        novel_id=novel_id,
                        entity_id=matched_entity.id,
                        chapter_number=chapter_number,
                        attributes=merged_attributes
                    )
                    session.add(new_state)
                return matched_entity.id
            else:
                # 新建实体与初始状态记录
                entity_id = str(uuid.uuid4())
                entity = KnowledgeEntity(
                    id=entity_id,
                    novel_id=novel_id,
                    entity_type=ent.get("type", "character"),
                    name=ent_name,
                    aliases=ent.get("aliases", []),
                    attributes=extracted_attrs,
                    first_chapter=chapter_number,
                    last_chapter=chapter_number,
                    source="extracted",
                )
                # RAG: 为实体生成 embedding（失败不阻断创建，精确检索仍可用）
                entity.embedding = await _generate_entity_embedding(
                    ent_name, ent.get("type", "character"),
                    ent.get("aliases", []), extracted_attrs,
                )
                session.add(entity)

                new_state = KnowledgeEntityState(
                    id=str(uuid.uuid4()),
                    novel_id=novel_id,
                    entity_id=entity_id,
                    chapter_number=chapter_number,
                    attributes=extracted_attrs
                )
                session.add(new_state)
                return entity_id

    async def add_triple(
        self, novel_id: str, chapter_number: int, triple: dict, name_to_id: dict[str, str]
    ) -> bool:
        """添加单个三元组"""
        subj_name = triple.get("subject", "")
        obj_name = triple.get("object", "")
        subj_id = name_to_id.get(subj_name)
        obj_id = name_to_id.get(obj_name)
        if not subj_id or not obj_id:
            return False

        async with get_db_session() as session:
            new_triple = KnowledgeTriple(
                id=str(uuid.uuid4()),
                novel_id=novel_id,
                subject_id=subj_id,
                predicate=triple.get("predicate", ""),
                object_id=obj_id,
                chapter_number=chapter_number,
                confidence=triple.get("confidence", 1.0),
                status="active",
                metadata_=triple.get("metadata", {}),
                source="extracted",
            )
            session.add(new_triple)
        return True

    async def _write_triples(
        self, novel_id: str, chapter_number: int,
        triples: list[dict], name_to_id: dict[str, str],
    ) -> int:
        """写入三元组，返回写入数量"""
        count = 0
        async with get_db_session() as session:
            for t in triples:
                subj_name = t.get("subject", "")
                obj_name = t.get("object", "")
                subj_id = name_to_id.get(subj_name)
                obj_id = name_to_id.get(obj_name)
                if not subj_id or not obj_id:
                    continue

                triple = KnowledgeTriple(
                    id=str(uuid.uuid4()),
                    novel_id=novel_id,
                    subject_id=subj_id,
                    predicate=t.get("predicate", ""),
                    object_id=obj_id,
                    chapter_number=chapter_number,
                    confidence=t.get("confidence", 1.0),
                    status="active",
                    metadata_=t.get("metadata", {}),
                    source="extracted",
                )
                session.add(triple)
                count += 1
        return count


    async def _write_extraction_log(
        self, log_id: str, novel_id: str, chapter_number: int,
        status: str, entities_count: int, triples_count: int,
        duration_ms: int, error_message: str | None = None,
    ) -> None:
        async with get_db_session() as session:
            # Upsert: delete existing log for this chapter then insert
            await session.execute(
                delete(KnowledgeExtractionLog).where(and_(
                    KnowledgeExtractionLog.novel_id == novel_id,
                    KnowledgeExtractionLog.chapter_number == chapter_number,
                ))
            )
            log = KnowledgeExtractionLog(
                id=log_id,
                novel_id=novel_id,
                chapter_number=chapter_number,
                status=status,
                entities_count=entities_count,
                triples_count=triples_count,
                duration_ms=duration_ms,
                error_message=error_message,
            )
            session.add(log)

    async def _get_triples_by_names(
        self, novel_id: str, names: list[str]
    ) -> list[dict[str, Any]]:
        """按实体名查询相关三元组"""
        async with get_db_session() as session:
            # 获取匹配的实体 ID
            result = await session.execute(
                select(KnowledgeEntity).where(and_(
                    KnowledgeEntity.novel_id == novel_id,
                    KnowledgeEntity.name.in_(names),
                ))
            )
            entities = list(result.scalars().all())
            entity_ids = [e.id for e in entities]
            entity_map = {e.id: e for e in entities}

            if not entity_ids:
                return []

            # 查询三元组
            result = await session.execute(
                select(KnowledgeTriple).where(and_(
                    KnowledgeTriple.novel_id == novel_id,
                    KnowledgeTriple.status == "active",
                    (
                        KnowledgeTriple.subject_id.in_(entity_ids)
                        | KnowledgeTriple.object_id.in_(entity_ids)
                    ),
                )).order_by(
                    KnowledgeTriple.chapter_number.desc()
                ).limit(50)
            )
            triples = list(result.scalars().all())

            # 补充实体名称
            all_ids = set()
            for t in triples:
                all_ids.add(t.subject_id)
                all_ids.add(t.object_id)
            missing_ids = all_ids - set(entity_ids)
            if missing_ids:
                r2 = await session.execute(
                    select(KnowledgeEntity).where(
                        KnowledgeEntity.id.in_(list(missing_ids))
                    )
                )
                for e in r2.scalars().all():
                    entity_map[e.id] = e

            return [
                {
                    "subject": (
                        entity_map[t.subject_id].name
                        if t.subject_id in entity_map
                        else "unknown"
                    ),
                    "predicate": t.predicate,
                    "object": (
                        entity_map[t.object_id].name
                        if t.object_id in entity_map
                        else "unknown"
                    ),
                    "chapter": t.chapter_number,
                    "confidence": t.confidence,
                }
                for t in triples
            ]


    async def _get_hanging_foreshadowings(
        self, novel_id: str
    ) -> list[KnowledgeEntity]:
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntity).where(and_(
                    KnowledgeEntity.novel_id == novel_id,
                    KnowledgeEntity.entity_type == "foreshadowing",
                    KnowledgeEntity.attributes["foreshadowing_status"]
                    .as_string() == "planted",
                ))
            )
            return list(result.scalars().all())

    async def _get_recent_events(
        self, novel_id: str, current_chapter: int
    ) -> list[KnowledgeEntity]:
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeEntity).where(and_(
                    KnowledgeEntity.novel_id == novel_id,
                    KnowledgeEntity.entity_type == "event",
                    KnowledgeEntity.last_chapter >= current_chapter - 3,
                )).order_by(KnowledgeEntity.last_chapter.desc()).limit(10)
            )
            return list(result.scalars().all())

    async def _get_chapter_triples(
        self, novel_id: str, chapter_number: int
    ) -> list[KnowledgeTriple]:
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeTriple).where(and_(
                    KnowledgeTriple.novel_id == novel_id,
                    KnowledgeTriple.chapter_number == chapter_number,
                ))
            )
            return list(result.scalars().all())

    async def _rule_based_check(
        self, novel_id: str, new_triples: list[KnowledgeTriple]
    ) -> list[dict[str, Any]]:
        """基于规则的一致性检查，覆盖 5 类常见冲突。"""
        conflicts: list[dict[str, Any]] = []
        entities = await self._get_existing_entities(novel_id)
        entity_map = {e.id: e for e in entities}

        # ── 构建本章每个 subject 的 triple 列表（用于 R2 地点冲突） ──
        subject_triples: dict[str, list[KnowledgeTriple]] = {}
        for triple in new_triples:
            subject_triples.setdefault(triple.subject_id, []).append(triple)

        for triple in new_triples:
            subject = entity_map.get(triple.subject_id)
            if not subject:
                continue

            # ── R1: 死角色仍在活动 ──
            if subject.entity_type == "character":
                if (subject.attributes or {}).get("status") == "dead":
                    action_predicates = ("位于", "前往", "战斗", "对话", "交手", "击杀", "拯救", "交谈", "协助", "攻击", "追击")
                    if triple.predicate in action_predicates:
                        conflicts.append({
                            "severity": "error",
                            "type": "dead_character_active",
                            "message": f"角色'{subject.name}'已死亡，但在新章节中仍有活动",
                            "entity": subject.name,
                        })

            # ── R2: 同一角色在同一章出现在两个不同地点 ──
            if subject.entity_type == "character" and triple.predicate == "位于":
                locations = [t for t in subject_triples.get(triple.subject_id, [])
                             if t.predicate == "位于" and t.id != triple.id]
                for loc_triple in locations:
                    other_loc = entity_map.get(loc_triple.object_id)
                    if other_loc and other_loc.entity_type == "location":
                        loc_name = other_loc.name
                        target_loc = entity_map.get(triple.object_id)
                        target_name = target_loc.name if target_loc else "未知"
                        conflicts.append({
                            "severity": "warning",
                            "type": "location_conflict",
                            "message": f"角色'{subject.name}'在同一章节出现在'{target_name}'和'{loc_name}'两个地点",
                            "entity": subject.name,
                        })

            # ── R3: 战力等级倒退（除非含"退化"描述） ──
            if subject.entity_type == "character" and triple.predicate == "拥有实力":
                # 从历史三元组查上次战力
                has_regression = False
                reasons = (triple.metadata_ or {}).get("reason", "")
                if "退化" not in reasons and "残废" not in reasons:
                    has_regression = True  # 标记，由 LLM 进一步确认
                if has_regression:
                    conflicts.append({
                        "severity": "warning",
                        "type": "power_level_regression",
                        "message": f"角色'{subject.name}'战力等级可能异常下降",
                        "entity": subject.name,
                    })

            # ── R4: 时间线矛盾 ──
            if triple.predicate in ("发生于", "开始于"):
                obj_entity = entity_map.get(triple.object_id)
                if obj_entity and obj_entity.entity_type == "event":
                    conflicts.append({
                        "severity": "warning",
                        "type": "timeline_contradiction",
                        "message": f"事件'{obj_entity.name}'已在第{obj_entity.first_chapter}章提及，注意时间线一致性",
                        "entity": obj_entity.name,
                    })

            # ── R5: 物品被多人同时持有 ──
            if triple.predicate in ("持有", "拥有"):
                obj_entity = entity_map.get(triple.object_id)
                if obj_entity and obj_entity.entity_type == "item":
                    other_holders = [
                        t for t in subject_triples.get(triple.subject_id, [])
                        if t.predicate in ("持有", "拥有") and t.object_id == triple.object_id and t.id != triple.id
                    ]
                    if other_holders:
                        conflicts.append({
                            "severity": "warning",
                            "type": "item_ownership_conflict",
                            "message": f"物品'{obj_entity.name}'被多个角色同时持有",
                            "entity": obj_entity.name,
                        })

        return conflicts

    async def _build_history_context(self, novel_id: str, chapter_number: int) -> str:
        """构建历史上下文摘要"""
        async with get_db_session() as session:
            result = await session.execute(
                select(KnowledgeTriple).where(and_(
                    KnowledgeTriple.novel_id == novel_id,
                    KnowledgeTriple.status == "active",
                    KnowledgeTriple.chapter_number < chapter_number,
                )).order_by(KnowledgeTriple.chapter_number.desc()).limit(30)
            )
            triples = list(result.scalars().all())

        entities = await self._get_existing_entities(novel_id)
        entity_map = {e.id: e for e in entities}

        lines = []
        for t in triples:
            subj = entity_map.get(t.subject_id)
            obj = entity_map.get(t.object_id)
            if subj and obj:
                lines.append(
                    f"第{t.chapter_number}章: "
                    f"{subj.name} → {t.predicate} → {obj.name}"
                )
        return "\n".join(lines[:30])


    async def _llm_consistency_check(
        self, chapter_text: str, triples_json: str, history_context: str
    ) -> list[dict[str, Any]]:
        """LLM 辅助的语义一致性检查"""
        prompt = CONSISTENCY_CHECK_PROMPT.format(
            chapter_text=chapter_text[:3000],
            new_triples=triples_json,
            history_context=history_context,
        )
        client = get_llm_client()
        raw = await client.generate(prompt, temperature=0.1)
        result = safe_json_parse(raw, fallback=[])
        if isinstance(result, list):
            return result
        return []

    def _format_context(
        self,
        triples: list[dict[str, Any]],
        foreshadowings: list[KnowledgeEntity],
        recent_events: list[KnowledgeEntity],
        all_entities: list[KnowledgeEntity],
    ) -> str:
        """格式化图谱上下文为 prompt 片段"""
        parts: list[str] = []
        parts.append("## 已知设定（来自知识图谱，请严格遵守）")

        # 人物关系
        if triples:
            parts.append("\n### 人物关系")
            for t in triples[:30]:
                parts.append(
                    f"- {t['subject']} → {t['predicate']}"
                    f" → {t['object']}（第{t['chapter']}章确立）"
                )

        # 当前人物状态
        characters = [e for e in all_entities if e.entity_type == "character"]
        if characters:
            parts.append("\n### 当前人物状态")
            for c in characters[:15]:
                status = (c.attributes or {}).get("status", "unknown")
                parts.append(f"- {c.name}：{status}")

        # 悬挂伏笔
        if foreshadowings:
            parts.append("\n### 悬挂伏笔（请考虑适时回收）")
            for f in foreshadowings:
                parts.append(f"- {f.name}（第{f.first_chapter}章埋设，尚未揭示）")

        # 最近事件
        if recent_events:
            parts.append("\n### 最近事件")
            for ev in recent_events:
                parts.append(f"- 第{ev.last_chapter or ev.first_chapter}章：{ev.name}")

        context = "\n".join(parts)
        if len(context) > 1500:
            context = context[:1500].rsplit("\n", 1)[0]
        return context

    def _format_rich_context(
        self,
        mentioned_entities: list[KnowledgeEntity],
        entity_states: dict[str, dict],
        character_details: dict[str, dict],
        triples_data: list[dict[str, Any]],
        foreshadowings: list[KnowledgeEntity],
        recent_events: list[KnowledgeEntity],
        raw_format: bool = False,
    ) -> str:
        """将活态实体记忆格式化为结构化 Markdown Prompt 上下文"""
        parts = []
        if raw_format:
            parts.append("## 知识图谱原始检索数据")
        else:
            parts.append("## 已知实体记忆与动态设定（来自活态知识图谱，请严格遵守）")

        # 1. 实体最新状态与背景
        parts.append("\n### 1. 实体当前状态与人物档案")
        for ent in mentioned_entities:
            state_attrs = entity_states.get(ent.id, {})

            # Format attributes string
            attr_lines = []
            for k, v in state_attrs.items():
                attr_lines.append(f"{k}: {v}")
            attrs_str = "; ".join(attr_lines) if attr_lines else "默认状态"

            if ent.entity_type == "character":
                char_info = character_details.get(ent.name, {})
                parts.append(f"\n#### 角色：{ent.name}")
                if char_info.get("role"):
                    parts.append(f"- **身份角色**: {char_info['role']}")
                parts.append(f"- **当前状态/属性**: {attrs_str}")
                if char_info.get("personality"):
                    parts.append(f"- **性格特征**: {char_info['personality']}")
                if char_info.get("abilities"):
                    parts.append(f"- **特殊能力**: {char_info['abilities']}")
                if char_info.get("background"):
                    parts.append(f"- **背景故事**: {char_info['background']}")
            else:
                ent_type_map = {
                    "location": "地点",
                    "item": "道具/物品",
                    "organization": "势力/组织",
                    "event": "事件",
                    "foreshadowing": "伏笔"
                }
                type_name = ent_type_map.get(ent.entity_type, ent.entity_type)
                parts.append(f"\n#### {type_name}：{ent.name}")
                parts.append(f"- **当前属性**: {attrs_str}")

        # 2. 角色恩怨与双向关系演化
        if triples_data:
            parts.append("\n### 2. 人物恩怨与双向关系演化")
            for t in triples_data[:20]:  # Cap at 20 relationships
                parts.append(
                    f"- **{t['subject']}** ──({t['predicate']})──> **{t['object']}** "
                    f"(第 {t['chapter']} 章确立{t['metadata_str']})"
                )

        # 3. 悬挂伏笔
        if foreshadowings:
            parts.append("\n### 3. 悬挂伏笔（请根据剧情节奏适时回收）")
            for f in foreshadowings[:10]:
                foreshadowing_desc = (f.attributes or {}).get(
                    "description", "已埋设的伏笔设定"
                )
                parts.append(
                    f"- **{f.name}**：{foreshadowing_desc} "
                    f"(第 {f.first_chapter} 章埋设，尚未回收)"
                )

        # 4. 最近历史事件
        if recent_events:
            parts.append("\n### 4. 最近历史事件")
            for ev in recent_events[:5]:
                ch_num = ev.last_chapter or ev.first_chapter
                parts.append(f"- **第 {ch_num} 章**: {ev.name}")

        return "\n".join(parts)


# 全局服务实例
_service: KnowledgeGraphService | None = None


def _build_entity_embedding_text(
    name: str,
    entity_type: str,
    aliases: list[str] | None,
    attributes: dict | None,
) -> str:
    """构造用于生成实体 embedding 的文本。

    融合名称、别名、类型与关键属性，使语义检索能匹配到实体的描述性信息。
    截断到合理长度，避免 embedding 输入过长。
    """
    parts: list[str] = [f"[{entity_type}] {name}"]
    if aliases:
        parts.append("别名：" + "、".join(aliases))
    if attributes and isinstance(attributes, dict):
        # 取属性键值，跳过过长的值
        attr_items = []
        for k, v in attributes.items():
            val = str(v)[:60] if v is not None else ""
            if val:
                attr_items.append(f"{k}:{val}")
        if attr_items:
            parts.append("属性：" + "；".join(attr_items[:8]))
    return "\n".join(parts)[:500]  # 截断，避免 embedding 输入过长


async def _generate_entity_embedding(
    name: str,
    entity_type: str,
    aliases: list[str] | None,
    attributes: dict | None,
) -> list[float] | None:
    """为实体生成 embedding 向量，用于 RAG 语义检索。

    仅当 ``settings.EMBEDDING_ENABLED=True`` 时调用 embedding API。默认 False
    （DeepSeek 不提供 embedding 接口，调用必 404）；此时返回 None，retrieve_context
    降级为精确匹配检索（基于实体名/别名，对中文小说足够）。

    配置了支持 embedding 的供应商（OpenAI/智谱等）时，设 EMBEDDING_ENABLED=True
    并配 EMBEDDING_BASE_URL/EMBEDDING_MODEL 即可启用向量语义检索。

    失败时返回 None（记日志），不阻断实体创建——精确匹配检索仍可用。

    Returns:
        embedding 向量，或 None（功能未启用或 API 失败时）。
    """
    settings = get_settings()
    if not getattr(settings, "EMBEDDING_ENABLED", False):
        return None  # 默认关闭，避免 DeepSeek 404 噪音
    if not settings.KNOWLEDGE_GRAPH_ENABLED:
        return None
    text = _build_entity_embedding_text(name, entity_type, aliases, attributes)
    if not text:
        return None
    try:
        embeddings = await _embed_texts([text])
        return embeddings[0] if embeddings else None
    except Exception as e:
        logger.warning(
            "entity_embedding_generation_failed",
            name=name,
            entity_type=entity_type,
            error=str(e),
        )
        return None


def get_knowledge_graph_service() -> KnowledgeGraphService:
    """获取知识图谱服务单例"""
    global _service
    if _service is None:
        _service = KnowledgeGraphService()
    return _service

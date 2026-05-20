"""SQLAlchemy database models"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base


class Novel(Base):
    """小说项目"""

    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(200))
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    novel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_words: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    writing_style: Mapped[str] = mapped_column(
        String(50), nullable=False, default="现代白话"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    custom_style_description: Mapped[str | None] = mapped_column(Text)
    writing_style_prompt: Mapped[str | None] = mapped_column(Text)

    # Relationships
    world_setting: Mapped["WorldSetting | None"] = relationship(
        back_populates="novel", uselist=False, cascade="all, delete-orphan"
    )
    power_systems: Mapped[list["PowerSystem"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan",
        order_by="Chapter.chapter_number"
    )
    volumes: Mapped[list["Volume"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan",
        order_by="Volume.volume_number"
    )


class WorldSetting(Base):
    """世界观设定"""

    __tablename__ = "world_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    background: Mapped[str | None] = mapped_column(Text)
    geography: Mapped[str | None] = mapped_column(Text)
    culture: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    novel: Mapped["Novel"] = relationship(back_populates="world_setting")


class PowerSystem(Base):
    """等级/力量体系"""

    __tablename__ = "power_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    levels: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    novel: Mapped["Novel"] = relationship(back_populates="power_systems")


class Character(Base):
    """人物"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[str | None] = mapped_column(Text)
    abilities: Mapped[str | None] = mapped_column(Text)
    background_story: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    novel: Mapped["Novel"] = relationship(back_populates="characters")


class Volume(Base):
    """卷"""

    __tablename__ = "volumes"
    __table_args__ = (
        UniqueConstraint("novel_id", "volume_number", name="uq_volume_novel_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    outline: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    chapter_start: Mapped[int | None] = mapped_column(Integer)
    chapter_end: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    novel: Mapped["Novel"] = relationship(back_populates="volumes")


class Chapter(Base):
    """章节"""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("novel_id", "chapter_number", name="uq_chapter_novel_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    volume_number: Mapped[int | None] = mapped_column(Integer)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    novel: Mapped["Novel"] = relationship(back_populates="chapters")


class Task(Base):
    """生成任务（保留兼容）"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    novel_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    novel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_words: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    errors: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "novel_id": self.novel_id,
            "status": self.status,
            "idea": self.idea,
            "novel_type": self.novel_type,
            "target_words": self.target_words,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "estimated_completion": self.estimated_completion,
            "progress": self.progress,
            "result": self.result,
            "errors": self.errors or [],
        }


class Conversation(Base):
    """创作对话"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


class Message(Base):
    """对话消息"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_as: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Outline(Base):
    """三级大纲（总纲/卷纲/章纲）"""

    __tablename__ = "outlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    volume_number: Mapped[int | None] = mapped_column(Integer)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class Storyline(Base):
    """故事线"""

    __tablename__ = "storylines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="main")
    description: Mapped[str | None] = mapped_column(Text)
    key_events: Mapped[list[dict] | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class CharacterArc(Base):
    """人物弧光"""

    __tablename__ = "character_arcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    arc_type: Mapped[str] = mapped_column(String(30), nullable=False, default="growth")
    description: Mapped[str | None] = mapped_column(Text)
    stages: Mapped[list[dict] | None] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class Scene(Base):
    """场景"""

    __tablename__ = "scenes_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    appearances: Mapped[list[dict] | None] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class StorylineCharacter(Base):
    """故事线-人物关联"""

    __tablename__ = "storyline_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    storyline_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("storylines.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    role_in_line: Mapped[str | None] = mapped_column(String(50))


class KnowledgeEntity(Base):
    """知识图谱实体"""

    __tablename__ = "knowledge_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    first_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    last_chapter: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20), default="extracted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class KnowledgeTriple(Base):
    """知识图谱三元组"""

    __tablename__ = "knowledge_triples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="extracted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )


class KnowledgeExtractionLog(Base):
    """知识抽取日志"""

    __tablename__ = "knowledge_extraction_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    entities_count: Mapped[int] = mapped_column(Integer, default=0)
    triples_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeEntityState(Base):
    """知识图谱实体状态历史（时空与状态追踪）"""

    __tablename__ = "knowledge_entity_states"
    __table_args__ = (
        UniqueConstraint("entity_id", "chapter_number", name="uq_kes_entity_chapter"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    novel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("novels.novel_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


"""API 请求模型"""

from pydantic import BaseModel, Field


class CreateNovelRequest(BaseModel):
    """创建小说请求"""

    idea: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="小说创意",
        examples=["一个现代程序员穿越到修仙世界，用编程思维修炼"],
    )
    novel_type: str = Field(
        ...,
        description="小说类型",
        examples=["玄幻"],
    )
    target_words: int = Field(
        default=100000,
        ge=10000,
        le=10000000,
        description="目标字数",
    )
    writing_style: str = Field(
        default="现代白话",
        description="文风风格",
    )
    writing_style_prompt: str = Field(
        default="",
        description="自定义文风指令（writing_style=自定义时使用）",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "idea": "一个现代程序员穿越到修仙世界，用编程思维修炼",
                    "novel_type": "玄幻",
                    "target_words": 100000,
                }
            ]
        }
    }


class LongFormNovelRequest(BaseModel):
    """百万字长篇生成请求"""

    idea: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="核心创意/故事梗概",
    )
    novel_type: str = Field(
        ...,
        description="小说类型（玄幻、都市等）",
    )
    target_words: int = Field(
        default=1_000_000,
        ge=100_000,
        le=5_000_000,
        description="目标总字数",
    )
    volumes: int = Field(
        default=10,
        ge=3,
        le=20,
        description="卷数",
    )
    chapters_per_volume: int = Field(
        default=40,
        ge=20,
        le=60,
        description="每卷章数（约）",
    )
    words_per_chapter: int = Field(
        default=3000,
        ge=2000,
        le=4000,
        description="每章目标字数",
    )
    writing_style: str = Field(
        default="现代白话",
        description="写作风格",
    )
    writing_style_prompt: str = Field(
        default="",
        description="自定义风格提示",
    )
    auto_quality_check: bool = Field(
        default=True,
        description="是否自动质量检查",
    )
    auto_filler_detection: bool = Field(
        default=True,
        description="是否自动注水检测",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "idea": "一个现代程序员穿越到修仙世界，用编程思维修炼",
                    "novel_type": "玄幻",
                    "target_words": 1000000,
                    "volumes": 10,
                    "chapters_per_volume": 40,
                    "words_per_chapter": 3000,
                }
            ]
        }
    }


class VolumeGenerateRequest(BaseModel):
    """按卷生成请求"""

    start_chapter: int = Field(
        default=1,
        ge=1,
        description="卷内起始章节（用于断点恢复）",
    )
    overwrite_existing: bool = Field(
        default=False,
        description="是否覆盖已生成章节",
    )

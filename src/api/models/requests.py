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

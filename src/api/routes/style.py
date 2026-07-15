"""文风生成 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.auth_models import User
from src.core.llm.client import get_llm_client
from src.core.security.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/style", tags=["style"])

STYLE_GENERATION_PROMPT = """你是一位文学风格分析专家。用户描述了他们想要的写作风格，请将其转化为一段具体的写作指令（100-200字），用于指导 AI 生成小说内容。

用户描述：{description}

请输出一段具体的风格指令，包含：
- 句式特点（长短句、节奏）
- 用词风格（文雅/通俗/专业）
- 叙事视角和语气
- 特殊技巧（比喻手法、对话风格等）

只输出风格指令，不要其他说明。"""


class GenerateStyleRequest(BaseModel):
    description: str = Field(..., min_length=2, max_length=500)


@router.post("/generate")
async def generate_style(request: GenerateStyleRequest, current_user: User = Depends(get_current_user)):
    try:
        client = get_llm_client()
        prompt = STYLE_GENERATION_PROMPT.format(description=request.description)
        style_prompt = await client.generate(prompt, max_tokens=500)
        return {"style_prompt": style_prompt.strip()}
    except Exception as e:
        logger.error(f"Style generation failed: {e}")
        raise HTTPException(status_code=500, detail="风格生成失败，请重试")

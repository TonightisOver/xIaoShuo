"""向后兼容 re-export — 实现已迁移到 src/api/services/novel_context_service。"""
from src.api.services.novel_context_service import (  # noqa: F401
    BlueprintContext,
    GenerationContext,
    NovelContextBuilder,
    RewriteContext,
)

__all__ = ["BlueprintContext", "GenerationContext", "NovelContextBuilder", "RewriteContext"]

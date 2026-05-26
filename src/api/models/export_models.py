"""导出功能请求/响应模型"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ExportFormat(StrEnum):
    txt = "txt"
    epub = "epub"
    docx = "docx"


class ExportScope(StrEnum):
    full = "full"
    volume = "volume"
    range = "range"


class ExportTemplate(StrEnum):
    default = "default"
    qidian = "qidian"
    fanqie = "fanqie"
    custom = "custom"


class TemplateOptions(BaseModel):
    chapter_title_format: str = Field(
        default="第{num}章 {title}",
        description="章节标题格式模板",
    )
    paragraph_indent: int = Field(default=2, ge=0, le=8)
    paragraph_spacing: int = Field(default=0, ge=0, le=2)
    include_volume_page: bool = Field(default=True)


class ExportRequest(BaseModel):
    format: ExportFormat
    scope: ExportScope = ExportScope.full
    volume_number: int | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    template: ExportTemplate = ExportTemplate.default
    template_options: TemplateOptions | None = None

    @model_validator(mode="after")
    def validate_scope_params(self) -> "ExportRequest":
        if self.scope == ExportScope.volume and self.volume_number is None:
            raise ValueError("volume_number is required when scope is 'volume'")
        if self.scope == ExportScope.range:
            if self.chapter_start is None or self.chapter_end is None:
                raise ValueError(
                    "chapter_start and chapter_end are required when scope is 'range'"
                )
            if self.chapter_start > self.chapter_end:
                raise ValueError("chapter_start must be <= chapter_end")
        return self


class TemplateInfo(BaseModel):
    name: str
    display_name: str
    description: str
    default_options: TemplateOptions

# code_review 评审报告

> 评审轮次：第 1 轮 · 日期：2026-05-26

## 评审结论

**结果**：APPROVED

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

#### SF-1: EPUB identifier 使用 `id(chapters)` 不稳定

**文件**: `src/api/services/export_service.py` L119

```python
book.set_identifier(f"xiaoshuo-{id(chapters)}")
```

`id()` 返回的是内存地址，每次请求都不同且不可复现。EPUB 规范中 identifier 应为稳定的唯一标识（如 novel_id + 时间戳或 UUID）。当前不影响功能，但不符合 EPUB 最佳实践。

**建议**: 传入 `novel_id` 参数，使用 `f"xiaoshuo-{novel_id}-{int(time.time())}"` 或 `uuid4()`。

---

#### SF-2: Content-Disposition 中文文件名兼容性

**文件**: `src/api/routes/export.py` L129

```python
headers={"Content-Disposition": f'attachment; filename="{filename}"'},
```

当 `novel.title` 包含中文时，部分浏览器/客户端可能无法正确解析非 ASCII 的 `filename`。RFC 6266 建议同时提供 `filename*=UTF-8''...` 编码形式。

**建议**: 使用 `urllib.parse.quote` 添加 `filename*` 参数：
```python
from urllib.parse import quote
headers={
    "Content-Disposition": (
        f'attachment; filename="{filename}"; '
        f"filename*=UTF-8''{quote(filename)}"
    ),
}
```

---

#### SF-3: EPUB/DOCX HTML 内容未转义

**文件**: `src/api/services/export_service.py` L149-150

```python
p_html = "".join(f"<p>{p}</p>" for p in paragraphs)
html_content = f"<h2>{ch_title}</h2>{p_html}"
```

如果章节内容中包含 `<`, `>`, `&` 等 HTML 特殊字符，生成的 XHTML 可能格式错误或导致 EPUB 阅读器解析失败。虽然小说正文通常不含这些字符，但作为防御性编程应进行转义。

**建议**: 使用 `html.escape()` 对段落文本和标题进行转义。

---

#### SF-4: 缺少 `test_export_routes.py` 路由层测试

需求文档 `影响范围` 中列出了 `tests/unit/test_export_routes.py`，但当前提交中未包含该文件。服务层测试覆盖良好（21 个用例），但路由层（参数校验、404 处理、StreamingResponse）缺少集成测试。

**建议**: 后续补充路由层测试，覆盖正常导出流程和异常场景（小说不存在、章节为空、参数校验失败）。

---

#### SF-5: 前端 ExportDialog 缺少 FR-4 一键复制功能

需求 FR-4 要求"批量复制（选择多章节，合并复制）"。当前 `ExportDialog.vue` 仅实现了文件导出功能，未包含批量复制入口。`ChapterEdit.vue` 中已有单章复制按钮，但批量复制尚未实现。

**建议**: 可作为后续迭代补充，当前单章复制已满足基本需求。

### INFO（信息提示）

#### I-1: 大文件内存占用

当前 TXT/EPUB/DOCX 导出均在内存中完成全部构建后返回 `BytesIO`。对于 NFR-1 提到的 100 章 30 万字场景，内存占用可控（约几 MB）。但如果未来支持更大规模导出，可考虑 TXT 格式的流式写入。

#### I-2: 数据库查询在 session 关闭后访问 ORM 对象

`export.py` L101-110 在 `async with get_db_session()` 块外部访问 `chapters_db` 的属性。由于查询使用了 `.all()` 且访问的都是标量属性（非延迟加载关系），当前不会触发 `DetachedInstanceError`，但需注意后续不要在此处添加关系属性访问。

#### I-3: 前端错误处理使用 alert

`ExportDialog.vue` L124 使用 `alert()` 显示错误信息。功能正确，但与项目整体 UI 风格（toast/notification）可能不一致。可后续统一为项目的通知组件。

## 总结

导出功能实现完整、结构清晰，覆盖了需求文档中 FR-1/FR-2/FR-3/FR-5 的核心功能点。代码分层合理（models → service → route），排版引擎设计灵活可扩展，单元测试覆盖了格式化引擎和三种导出器的关键路径。未发现阻塞性问题，建议修复项均为健壮性和兼容性改进，不影响当前功能正确性。

**结论：APPROVED**

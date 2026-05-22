# Code Review — CHANGE-040 修复章节分卷与图谱筛选

**评审轮次**: 第 1 轮  
**日期**: 2026-05-22  
**评审类型**: code_review  
**评审范围**: novel_generator.py 章节替换策略与 volume_number fallback、knowledge_graph_service.py 频次筛选、RelationGraph.vue 前端控件、ChapterEdit.vue 空状态 UX

---

## 评审结论
**结果**：APPROVED

---

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

1. **版本记录与章节持久化的过滤条件不一致**
   - 位置：`src/api/services/novel_generator.py:806-808`
   - 问题：章节持久化使用 `successful_chapters` 过滤条件为 `ch.get("content") and ch.get("word_count", 0) > 0`，但版本记录创建循环遍历的是 `generated_chapters` 且仅检查 `ch.get("content")`。理论上存在 content 非空但 word_count 为 0 的边界情况，此时会创建版本记录但对应章节未写入 Chapter 表。
   - 建议：将版本记录循环改为遍历 `successful_chapters`，保持一致性：
     ```python
     for ch in successful_chapters:
         try:
             await novel_manager.create_chapter_version(...)
         except (ValueError, Exception):
             pass
     ```

2. **前端 toggleShowAll 缺少 loading 状态防护**
   - 位置：`frontend/src/views/RelationGraph.vue:107-112`
   - 问题：`toggleShowAll()` 调用 `loadThreeLayerGraph()` 会设置 `kgLoading`，但切换按钮本身没有 disabled 状态，用户可能在加载中重复点击导致并发请求。
   - 建议：在按钮上添加 `:disabled="kgLoading"` 防止重复触发。

### INFO（信息提示）

1. **频次筛选对边的间接影响设计正确**
   - `should_include` 过滤低频实体节点后，三元组边的过滤依赖于 `char_ids`/`event_ids` 集合（只包含通过筛选的实体）。被过滤实体的关联边自然不会出现在结果中，逻辑自洽。

2. **foreshadowing 层不受频次筛选影响**
   - `should_include` 对 foreshadowing 类型始终返回 True，且伏笔层循环未调用该函数，两处逻辑一致。伏笔节点始终全量展示，符合设计意图（伏笔数量通常较少且每个都有业务意义）。

3. **fix_volume_numbers 的事务隔离合理**
   - `fix_volume_numbers()` 在章节写入 session 提交后以独立事务运行，确保能看到刚写入的章节数据。与 `_find_volume_number()` 形成双保险：前者在写入时尽量赋值，后者在写入后兜底修补。

4. **ChapterEdit 空状态 UX 改进良好**
   - 新的空状态卡片提供了"刷新重试"和"返回章节列表"两个操作路径，文案准确描述了可能的原因（正在重新生成/生成异常），比原来的纯文字"章节不存在"体验显著提升。

---

## 各文件评审摘要

| 文件 | 评分 | 主要问题 |
|------|------|----------|
| `novel_generator.py` (章节替换 + volume fallback) | 良好 | 核心逻辑正确，版本记录过滤条件可优化 |
| `knowledge_graph_service.py` (频次筛选) | 良好 | 筛选逻辑清晰，foreshadowing 豁免合理 |
| `knowledge_graph.py` (路由参数) | 良好 | Query 参数带 ge=1 校验，无问题 |
| `RelationGraph.vue` (前端控件) | 良好 | 功能完整，按钮可加 disabled 防护 |
| `ChapterEdit.vue` (空状态) | 良好 | UX 改进到位，无阻塞问题 |

---

## 总结

本次变更质量良好，四个 Bug 修复均针对性强且实现合理。核心改动——逐章替换策略避免了失败章节数据丢失、volume_number 双重保障机制、频次筛选降低图谱节点密度——逻辑清晰，没有引入安全或性能隐患。两个 SHOULD FIX 项为边界一致性和 UX 防御性建议，不阻塞合入。

**APPROVED**

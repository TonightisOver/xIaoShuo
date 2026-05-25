# plan_review 评审报告

**评审轮次**: 第 1 轮
**评审对象**: CHANGE-044-百万字长篇生成验证 需求分析 + 技术设计
**日期**: 2026-05-25

## 评审结论
**结果**：APPROVED（附带建议项）

## 评审发现

### MUST FIX（必须修复）

无

### SHOULD FIX（建议修复）

1. **大纲生成的 token 上限矛盾**
   - 位置：技术设计 D1 章节 + outline_generation.py:39
   - 问题：技术设计指出 DeepSeek API 单次输出 token 上限约 4000，不够输出完整百万字大纲，但当前 outline_generation.py 中 max_tokens=4000。设计文档中未明确说明三级大纲各阶段的具体 token 分配策略（总纲需要多少 token、卷纲需要多少 token），且未评估 DeepSeek 对输出 35~50 章章纲（每章需含 chapter_type、摘要、冲突设定等字段）的单次调用是否可行。若卷纲一次仍无法输出 40 章的完整章纲，需要进一步细化为卷纲 + 逐章补全两步。
   - 建议：补充各阶段 token 预算估算，并明确当卷纲输出超过 token 上限时的降级策略（如分批次输出章纲）。

2. **断点恢复的并发安全未说明**
   - 位置：API 设计 pause/resume 端点 + LongFormProgress 模型
   - 问题：LongFormProgress 记录了 current_chapter 和 status，但设计中未提及暂停/恢复操作的并发安全机制。若用户在生成过程中调用 pause，当前 LLM 调用可能仍在进行中，resume 时如何确定是从当前 chapter 还是下一 chapter 恢复？是否有锁机制防止重复触发同一卷的生成？
   - 建议：在技术设计中补充 pause/resume 的状态机转换图，明确暂停中已完成的章和暂停中未完成的章的处理方式。

3. **伏笔追踪阈值调整缺乏具体参数**
   - 位置：需求分析 F6 + 风险表
   - 问题：风险表提到 10章阈值在300+章中过于宽松，但未给出调整后的具体参数。验收标准中注水检测能识别连续3章低 advancement 是固定阈值，与动态调整阈值的描述不一致。
   - 建议：明确注水检测阈值是固定（连续3章）还是动态（基于卷长度的百分比），二选一并在验收标准中统一。

4. **新增 4 个 service 文件的职责边界模糊**
   - 位置：影响评估涉及文件表
   - 问题：quality_report_service.py、filler_detection_service.py、foreshadow_tracker_service.py、long_form_progress_service.py 四个新服务。其中 filler_detection 和 foreshadow_tracker 的功能在需求分析 F6 和 F5 中描述为监控仪表盘的子功能，是否有必要拆为独立服务？如果它们都读取 ChapterVersion 的质量评分数据，是否存在重复的查询逻辑？
   - 建议：考虑将 filler_detection 和 foreshadow_tracker 合并为一个 long_form_monitoring_service.py，减少服务间的职责碎片化。此为架构偏好，不阻塞流程。

5. **LongFormProgress 表与现有 Volume 表字段重叠**
   - 位置：数据模型 LongFormProgress vs Volume
   - 问题：Volume 表新增了 generated_chapters、avg_quality_score、quality_report 字段，LongFormProgress 表也记录了 chapters_completed、quality_report、filler_report。两表存在数据冗余，更新时需要同步，容易导致不一致。
   - 建议：明确哪张表为权威数据源。建议 LongFormProgress 只记录生成进度（status、current_chapter、errors），将质量报告数据统一归到 Volume 表。

### INFO（信息提示）

1. **数据库迁移脚本路径未指定**：影响评估中提到需要 Alembic 迁移，但未指定迁移脚本的命名（如 versions/xxx_add_long_form_fields.py），实现时需注意。

2. **性能估算基本合理**：1500+ 次 LLM 调用、2~4 小时生成时间、50MB 内存峰值的估算与百万字规模匹配，无明显夸大或遗漏。

3. **需求分析与技术设计的一致性良好**：F1~F6 六个功能点在技术设计中均有对应的设计决策（D1~D6），覆盖完整。

4. **不需要改动的部分判断合理**：LLM 客户端、DB 基础模型、API 路由框架、事件总线确实无需改动，变更范围控制得当。

## 总结

需求分析和技术设计整体质量较高，功能覆盖完整，技术方案与现有架构兼容性好。核心目标百万字规模下的工程健壮性和一致性维护能力定义清晰，避免了生成质量这一难以量化的目标干扰工程验证。

主要关注点集中在三个方面：(1) 三级大纲各阶段的 token 可行性需要更精确的评估，特别是卷纲阶段单次输出 35~50 章章纲是否超出 DeepSeek 输出上限；(2) pause/resume 的并发安全和状态机转换需要补充说明；(3) LongFormProgress 与 Volume 表的数据冗余需要明确归属。

以上建议项均不阻塞流程，可在实现阶段逐步解决。

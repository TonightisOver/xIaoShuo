# Spec：funnel-quality-gate 上线 + 低内聚高耦合重构

## 已完成（2026-07-16 ~ 2026-07-18）

### 首页 & 全站风格
- [x] 水墨书法首页（`/`）：毛笔逐笔书写「落笔生花」+ 鼠标墨迹 + 五屏内容滚动
- [x] 全站米白纸墨统一：清理 slate/gray/neutral 深色异类，Inspiration 整页米白化
- [x] 首页置于根路径 `/`，书房移至 `/shelf`

### Dev 体验
- [x] 取消登录守卫，dev 免登录（DEV_AUTO_LOGIN）
- [x] 路由守卫取消 + App 根底改纸白

### Bug 修复
- [x] 人物对话句尾 `------`（后处理 + prompt 禁半角连字符）
- [x] 长篇质量门禁 state_delta/quality_status 未落库（persist 顺序 + 门禁字段双保险）
- [x] long-form 鉴权 + owner_id + 进度路由
- [x] 大纲生成 499/504（nginx 超时 300s→600s + 前端进度提示）
- [x] 进度逐章实时落库 LFP 表（进行中卷不再卡 0）
- [x] persist upsert（重试不撞唯一约束）
- [x] 失败章节不写垃圾行
- [x] chapters.state_delta/quality_status 迁移 + compose DEV_AUTO_LOGIN 注入

### 低内聚高耦合重构（三步）
- [x] Step 1：提取 `compute_chapter_numbering` 纯函数（TDD，4 测试）
- [x] Step 2：GVC 用纯函数 + 支持无卷退化
- [x] Step 2.5：提取 `record_chapter_artifacts` 版本+StoryBible 语义统一（TDD，3 测试）
- [x] Step 3：删 `_generate_chapters_batch`（-120 行），全路径接入 GVC

### 工程化
- [x] Matt Pocock engineering skills 配置（issue-tracker=本地 markdown，domain=单上下文）
- [x] CONTEXT.md 领域术语表

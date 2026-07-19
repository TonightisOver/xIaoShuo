# 项目历史归档

本目录保存已完成的工程变更、设计、计划、报告和临时记录。活动开发资料仍放在原有工作目录中。

## 查阅入口

- [`index.md`](index.md)：按类别浏览归档资料
- [`manifest.csv`](manifest.csv)：查询文件的新旧路径
- [`organization-report.md`](organization-report.md)：查看本次整理结果

## 规则

1. 归档原文保持不变。
2. 每个 Harness 变更目录增加一份 `archive-record.md` 综合记录。
3. 新任务继续使用 `.harness/changes/` 和 `.scratch/`；完成后再迁入本目录。
4. 归档区不存放源码、依赖、日志或运行数据；自动生成的索引和摘要会对 API Key 脱敏。

## 安全说明

部分原始历史文档曾记录旧 API Key。为满足“原文不改”的归档要求，这些原始文件保持不变；它们不应被公开分发。归档索引和 `archive-record.md` 不复制明文密钥。旧密钥应视为已泄露并完成轮换，后续可单独进行 Git 历史清理。

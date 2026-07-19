# CHANGE-043 归档记录

- 原名称：API压力测试扩展
- 状态：completed
- 时间范围：2026-05-25
- 原路径：`.harness/changes/CHANGE-043-API压力测试扩展`
- 归档路径：`archive/changes/CHANGE-043-API压力测试扩展`
- 关联提交：
  - e5bebc2 2026-05-25 feat: expand Locust load tests to 21 API scenarios and fix regenerate bug (CHANGE-043)

## 目标

| 指标 | 目标值 |
|------|--------|
| 读接口 P95 延迟 | < 200ms |
| 写接口 P95 延迟 | < 500ms |
| AI 接口 P95 延迟 | < 60s（LLM 限制） |
| 错误率 | < 1% |
| 并发用户 | 50-200 |
| 持续时间 | 5-15 分钟 |

## 主要设计决定

### 方案 A：扩展 Locust（推荐）
- 优势：已有基础、Python 生态一致、Web UI 实时监控
- 新增场景模块 + 用户画像 + HTML 报告

### 方案 B：新增 k6 脚本
- 优势：更精确的性能指标、原生 CI 集成、阈值断言
- 输出 JSON summary + 可选 Grafana 集成

### 最终方案：A + B 并行
- Locust 用于交互式压测和探索
- k6 用于 CI 自动化回归和阈值守护

## 涉及模块

- 未在原始文档中识别出明确模块路径

## 实施结果

项目已有基础 Locust 压测框架（CHANGE-042），覆盖 4 个场景：
- 章节读取 (chapter_read)
- 章节列表 (chapter_list)
- 章节生成 (chapter_generate)
- AI 改写 (ai_rewrite)
用户已完成 20 章 30 万字小说的数据准备，现需扩展压测覆盖面，同时支持 k6 作为备选工具。
1. **扩展 Locust 压测场景**：覆盖项目全部核心 API 接口
2. **新增 k6 压测脚本**：提供 k6 版本的压测方案，支持 CI 集成和更精确的性能指标
3. **压测报告输出**：支持 HTML/JSON 报告生成
| 场景 | 接口 | 方法 |
|------|------|------|
| 章节读取 | /api/v1/projects/{id}/chapters/{num} | GET |

## 测试与验证

项目已有基础 Locust 压测框架（CHANGE-042），覆盖 4 个场景：
- 章节读取 (chapter_read)
- 章节列表 (chapter_list)
- 章节生成 (chapter_generate)
- AI 改写 (ai_rewrite)
用户已完成 20 章 30 万字小说的数据准备，现需扩展压测覆盖面，同时支持 k6 作为备选工具。
1. **扩展 Locust 压测场景**：覆盖项目全部核心 API 接口
2. **新增 k6 压测脚本**：提供 k6 版本的压测方案，支持 CI 集成和更精确的性能指标
3. **压测报告输出**：支持 HTML/JSON 报告生成
| 场景 | 接口 | 方法 |
|------|------|------|
| 章节读取 | /api/v1/projects/{id}/chapters/{num} | GET |

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `01-需求分析.md`

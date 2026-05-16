# xIaoShuo Harness 体系使用指南

**版本**: v1.0  
**项目**: AI 中文网络小说生成平台  
**创建日期**: 2026-05-16

---

## 什么是 Harness 体系？

Harness 体系是为 AI Coding Agent 设计的工作环境，包含：
- **Agent 定义**: Application Owner Agent 的角色和职责
- **Rules**: 工程结构、开发流程、编码规范等规则
- **Skills**: 10 阶段开发流程对应的技能
- **变更管理**: 完整的 Audit Trail
- **Wiki**: 项目知识库

---

## 快速开始

### 1. 启动新需求

当你有新需求时，告诉 Application Owner Agent：

```
我需要实现 {需求描述}
```

Agent 会自动：
1. 创建变更目录（CHANGE-XXX-描述/）
2. 启动 10 阶段开发流程
3. 生成所有必需的文档和代码

### 2. 查看进度

```bash
# 查看所有变更
ls .harness/changes/

# 查看特定变更的 summary
cat .harness/changes/CHANGE-XXX-描述/summary.md
```

### 3. 人工审核

在以下阶段，Agent 会等待你的确认：
- **阶段 2（技术设计）**: 确认架构方案
- **阶段 6（专家评审）**: 如有严重问题，确认修复方案
- **阶段 10（部署验证）**: 确认交付

你可以回复：
- **"通过"** 或 **"继续"**: 进入下一阶段
- **"修改 XXX"**: Agent 会根据反馈修改
- **"拒绝"**: 回退到上一阶段

---

## 目录结构

```
.harness/
├── README.md                      # 本文件
├── agents/
│   └── application-owner.md       # Application Owner Agent 定义
├── rules/                         # 规则体系
│   ├── 工程结构.md
│   ├── 开发流程规范.md
│   ├── Python编码规范.md
│   ├── LangGraph最佳实践.md
│   ├── FastAPI开发规范.md
│   └── 数据库设计规范.md
├── skills/                        # 10 阶段 Skills
│   ├── 01-request-analysis/
│   ├── 02-technical-design/
│   ├── 03-coding-plan/
│   ├── 04-coding-impl/
│   ├── 05-code-review/
│   ├── 06-expert-review/
│   ├── 07-unit-test/
│   ├── 08-integration-test/
│   ├── 09-ci-verify/
│   └── 10-deploy-verify/
├── changes/                       # 变更管理
│   ├── README.md
│   ├── _template/
│   └── CHANGE-XXX-描述/
├── wiki/                          # 知识库
│   ├── README.md
│   ├── quick-start/
│   ├── architecture/
│   ├── business/
│   └── tech-stack/
└── prompts/                       # AI Prompt 模板
    ├── world-building.md
    ├── character-design.md
    ├── outline-generation.md
    └── chapter-generation.md
```

---

## 10 阶段开发流程

| 阶段 | 名称 | 产出物 | 人工审核 |
|------|------|--------|---------|
| 1 | 需求分析 | `01-需求分析.md` | 否 |
| 2 | 技术设计 | `02-技术设计.md` | **是** |
| 3 | 编码计划 | `03-编码计划.md` | 否 |
| 4 | 编码实现 | 代码 + `04-编码报告-v1.md` | 否 |
| 5 | 代码检查 | `05-代码检查报告-v1.md` | 否 |
| 6 | 专家评审 | `06-专家评审报告-v1.md` | 可选 |
| 7 | 单元测试 | 测试 + `07-单元测试报告-v1.md` | 否 |
| 8 | 集成测试 | 测试 + `08-集成测试报告-v1.md` | 否 |
| 9 | CI 验证 | `09-CI验证报告-v1.md` | 否 |
| 10 | 部署验证 | `10-部署验证报告-v1.md` | **是** |

---

## 常用命令

### 查看变更历史
```bash
ls .harness/changes/
```

### 查看特定变更
```bash
cd .harness/changes/CHANGE-001-langgraph-基础框架/
ls -la
```

### 运行代码检查
```bash
ruff check src/
mypy src/
```

### 运行测试
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### 查看测试覆盖率（HTML）
```bash
pytest tests/ --cov=src --cov-report=html
# 打开 htmlcov/index.html
```

---

## 质量标准

每个阶段都有明确的质量门禁：

- **阶段 4（编码实现）**: ruff + mypy 通过，代码可运行
- **阶段 5（代码检查）**: 0 errors
- **阶段 6（专家评审）**: 无严重问题
- **阶段 7（单元测试）**: 覆盖率 > 80%
- **阶段 8（集成测试）**: 核心流程通过
- **阶段 9（CI 验证）**: 所有检查通过
- **阶段 10（部署验证）**: 功能可用

---

## 最佳实践

### 1. 明确需求
- 提供清晰的需求描述
- 说明业务背景和使用场景
- 提供参考示例（如有）

### 2. 及时反馈
- 在人工审核节点及时给出反馈
- 明确说明"通过"或"修改 XXX"

### 3. 查看文档
- 定期查看变更目录中的文档
- 了解 Agent 的设计思路和实现细节

### 4. 保持沟通
- 遇到问题及时与 Agent 沟通
- 不要让 Agent 猜测你的意图

---

## 常见问题

### Q1: 如何跳过某个阶段？
**A**: 不建议跳过阶段。如果确实需要（如紧急修复），可以使用 Hotfix 流程。

### Q2: 如何修改已完成的阶段？
**A**: 告诉 Agent "我需要修改阶段 X"，Agent 会回退到该阶段并重新执行。

### Q3: 如何查看某个变更的完整历史？
**A**: 进入变更目录，查看所有文档：
```bash
cd .harness/changes/CHANGE-XXX-描述/
ls -la
```

### Q4: 版本号是什么意思？
**A**: 当某个阶段需要重做时，版本号递增（v1 → v2 → v3）。旧版本不会被删除，便于追溯。

### Q5: 如何添加新的 Rule 或 Skill？
**A**: 
- 新增 Rule: 在 `.harness/rules/` 下创建新的 `.md` 文件
- 新增 Skill: 在 `.harness/skills/` 下创建新的目录和 `skill.md`

---

## 项目特定信息

### 技术栈
- Python 3.11+
- FastAPI
- LangGraph
- DeepSeek API
- PostgreSQL + SQLAlchemy
- Redis
- Celery
- pytest

### 核心业务
- 小说创作流程：创意 → 世界观 → 人物 → 大纲 → 章节
- LangGraph 状态管理
- Human-in-the-Loop 审核

### 关键文档
- **需求分析**: `需求分析.md`（项目根目录）
- **架构设计**: `Harness架构设计.md`（项目根目录）
- **Agent 定义**: `.harness/agents/application-owner.md`

---

## 下一步

### 1. 熟悉 Agent
阅读 `.harness/agents/application-owner.md`，了解 Agent 的工作方式。

### 2. 查看 Rules
浏览 `.harness/rules/` 下的规范文件，了解项目的约束。

### 3. 启动第一个需求
告诉 Agent 你的第一个需求，体验完整的 10 阶段流程。

### 4. 完善 Wiki
随着项目推进，逐步完善 `.harness/wiki/` 下的知识库。

---

## 维护指南

### 定期更新
- Rules 和 Skills 应随项目演进而更新
- 发现新的最佳实践时，及时补充到 Rules

### 清理旧变更
- 已完成的变更可以归档（移动到 `changes/archived/`）
- 但不要删除，保持完整的历史记录

### 知识沉淀
- 将常见问题和解决方案记录到 Wiki
- 将优秀的设计模式记录到 Wiki

---

## 联系和反馈

如有问题或建议，请：
1. 查看 `.harness/wiki/` 知识库
2. 查看 `.harness/changes/` 历史变更
3. 与 Application Owner Agent 沟通

---

**Harness 状态**: ✅ 已激活，准备接收需求

**下一步**: 告诉 Agent 你的第一个需求，开始你的 AI 小说生成平台之旅！
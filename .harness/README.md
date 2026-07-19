# xIaoShuo Harness 体系

**版本**: v2.0
**架构**: 多 Agent 协作 + 2 Gate 人工门禁

---

## 架构概览

```
用户需求 → Orchestrator → Analyst → Gate 1 → Implementer → Tester → Deployer → Gate 2 → 完成
```

### Agent 清单

| Agent | 文件 | 职责 |
|-------|------|------|
| Orchestrator | `agents/orchestrator.md` | 主编排，调用子 Agent，管理门禁，注入上下文 |
| Analyst | `agents/analyst.md` | 阶段 1-2: 需求分析 + 技术设计 |
| Implementer | `agents/implementer.md` | 阶段 3-5: 编码计划 + 实现 + 代码检查 |
| Tester | `agents/tester.md` | 阶段 6-8: 专家评审 + 单元测试 + 集成测试 |
| Deployer | `agents/deployer.md` | 阶段 9-10: CI 验证 + 部署验证 |

### 门禁

- **Gate 1** — 技术设计完成后，人工审批架构方案
- **Gate 2** — 所有阶段完成后，人工审批交付

---

## 快速开始

在 Claude Code 中输入 `/harness` + 你的需求：

```
/harness 我需要实现 {需求描述}
```

Orchestrator 将自动创建变更目录并启动流程，在关键节点暂停等待审批。

---

## 目录结构

```
.harness/
├── README.md
├── agents/                       # Agent 指令模板
│   ├── orchestrator.md
│   ├── analyst.md
│   ├── implementer.md
│   ├── tester.md
│   └── deployer.md
├── rules/                        # 规范约束
│   ├── 开发流程规范.md
│   ├── 工程结构.md
│   ├── Python编码规范.md
│   ├── LangGraph最佳实践.md
│   ├── FastAPI开发规范.md
│   └── 数据库设计规范.md
├── changes/                      # 变更记录
│   └── CHANGE-XXX-xxx/
├── wiki/                         # 知识库
└── prompts/                      # LLM Prompt 模板
```

---

## 上下文传递

1. **文件系统**: Agent 产出写入 `changes/CHANGE-XXX/`，下游 Agent 读取上游产出
2. **Prompt 注入**: Orchestrator 将需求摘要、设计摘要写入子 Agent prompt
3. **指令模板**: Orchestrator 读取 `agents/*.md` 并拼接到子 Agent prompt

---

## 常用命令

```bash
# 查看变更历史
Get-ChildItem .harness/changes/ -Directory | Sort-Object Name -Descending

# 代码检查
ruff check src/
mypy src/

# 测试
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 历史归档

`.harness/changes/` 只保留当前变更和模板。已完成变更集中保存在项目根目录 [`archive/changes/`](../archive/changes/)，统一索引见 [`archive/index.md`](../archive/index.md)。

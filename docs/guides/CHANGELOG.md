# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-16

### Added

- **DeepSeek API 集成**: 完整集成 DeepSeek v4-pro 模型，替换所有 mock 数据
  - 配置管理系统 (`src/core/config.py`)
  - LLM 客户端 (`src/core/llm/client.py`) 支持重试和超时控制
  - 5 个节点的 Prompt 模板 (`src/core/llm/prompts.py`)
  
- **安全和验证**:
  - 输入验证系统 (`src/core/validation.py`) 防止 prompt 注入攻击
  - 智能 JSON 解析 (`src/core/json_utils.py`) 支持容错和部分提取
  - 13 种小说类型白名单验证
  - 字数范围验证 (10,000 - 10,000,000)

- **日志系统**:
  - 集中式日志配置 (`src/core/logging_config.py`)
  - 文件和控制台双输出
  - 可配置日志级别和路径
  - 完整的 API 调用和错误堆栈记录

- **错误处理**:
  - 完善的降级机制：API 失败时使用 mock 数据
  - 重试机制：指数退避，最多 3 次重试
  - 超时控制：默认 120 秒，可配置
  - 错误状态记录到 `state["errors"]`

- **测试覆盖**:
  - 27 个新增单元测试
  - LLM 客户端测试 (5 个)
  - 输入验证测试 (13 个)
  - JSON 解析测试 (9 个)
  - 总测试数量: 43 个 (100% 通过率)

- **部署工具**:
  - 部署验证脚本 (`verify_deployment.py`)
  - 环境变量配置模板 (`.env.example`)
  - 完整的部署文档

### Changed

- **依赖升级**:
  - `langgraph`: 0.2.76 → 1.2.0
  - `langchain-core`: 0.3.86 → 1.4.0
  - 新增: `langchain` 1.3.1, `langchain-openai` 1.2.1, `pydantic-settings` 2.14.1, `tenacity` 9.1.4

- **节点异步化**:
  - 所有 5 个节点从同步转换为异步执行
  - 使用 `async/await` 提升性能
  - 支持并发 API 调用

- **配置更新**:
  - 模型: `deepseek-chat` → `deepseek-v4-pro`
  - 超时: 30 秒 → 120 秒
  - 最大 Token: 2000 (可配置)
  - 温度: 0.7 (可配置)

### Fixed

- **依赖冲突**: 解决 langchain-core 版本冲突 (< 0.4 vs >= 1.3.2)
- **API 认证**: 修复环境变量覆盖 .env 文件的问题
- **API 超时**: 增加超时时间以处理复杂 prompt
- **导入错误**: 修复 `langchain.prompts` 模块路径
- **编码错误**: 修复 Windows 控制台 Unicode 显示问题
- **代码质量**: 修复所有 ruff 和 mypy 检查问题

### Quality Metrics

- **测试覆盖率**: ~85%
- **代码质量**: Ruff 0 错误, Mypy 0 错误
- **测试通过率**: 100% (43/43)
- **总体评分**: 9.4/10

### Documentation

- 完整的 Harness 变更记录 (10 个阶段文档)
- 需求分析、技术设计、编码计划
- 专家评审、问题修复、集成测试报告
- CI 验证、部署验证报告
- API 配置指南和故障排除文档

## [0.1.0] - 2026-05-15

### Added

- 初始项目框架
- LangGraph 基础工作流
- 7 个核心节点 (使用 mock 数据)
- 基础测试套件 (16 个测试)
- Poetry 依赖管理
- Harness 工程体系

---

**变更编号**: CHANGE-002  
**负责人**: Development Team  
**审核人**: Expert Reviewer, QA Team, CI/CD Team, DevOps Team

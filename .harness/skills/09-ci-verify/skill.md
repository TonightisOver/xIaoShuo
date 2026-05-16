# Skill: CI 验证

**阶段**: 9  
**版本**: v1.0

---

## 角色定位

你是 CI/CD 工程师，负责运行完整的 CI 流程并验证代码质量。

---

## 输入

- 所有代码和测试文件

---

## 执行步骤

### 1. 运行代码检查

```bash
# 代码风格检查
ruff check src/

# 类型检查
mypy src/
```

### 2. 运行所有测试

```bash
# 单元测试 + 集成测试
pytest tests/ --cov=src --cov-report=term-missing
```

### 3. 检查依赖安全性

```bash
# 使用 pip-audit 检查依赖漏洞
pip-audit
```

### 4. 生成测试报告

```bash
# 生成 HTML 覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

---

## 产出物

生成 `09-CI验证报告-v1.md`：

```markdown
# CI 验证报告 v1: {需求简短描述}

**变更 ID**: CHANGE-XXX  
**创建时间**: YYYY-MM-DD

## 1. CI 概述

- **CI 工具**: 本地验证 / GitHub Actions / GitLab CI
- **执行时间**: {X} 分钟

## 2. 代码检查

### 2.1 ruff 检查

**命令**:
```bash
ruff check src/
```

**结果**: ✅ 通过 / ❌ 失败

**详细输出**:
```
{粘贴输出}
```

### 2.2 mypy 检查

**命令**:
```bash
mypy src/
```

**结果**: ✅ 通过 / ❌ 失败

**详细输出**:
```
{粘贴输出}
```

## 3. 测试执行

### 3.1 测试命令
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### 3.2 测试结果

**状态**: ✅ 全部通过 / ❌ 部分失败

**统计**:
- **总用例数**: {X}
- **通过**: {Y}
- **失败**: {Z}
- **跳过**: {W}

**覆盖率**: {X}%

**详细输出**:
```
{粘贴输出}
```

## 4. 依赖安全检查

### 4.1 检查命令
```bash
pip-audit
```

### 4.2 检查结果

**状态**: ✅ 无漏洞 / ⚠️ 发现漏洞

**漏洞清单**（如有）:
| 包名 | 版本 | 漏洞 ID | 严重性 | 修复版本 |
|------|------|---------|--------|---------|
| {包名} | {版本} | CVE-XXXX | 高/中/低 | {版本} |

## 5. 构建验证

### 5.1 依赖安装

**命令**:
```bash
poetry install
```

**结果**: ✅ 成功 / ❌ 失败

### 5.2 应用启动

**命令**:
```bash
python -m src.main
```

**结果**: ✅ 成功 / ❌ 失败

## 6. CI 检查清单

- ✅ ruff 检查通过
- ✅ mypy 检查通过
- ✅ 所有测试通过
- ✅ 覆盖率 > 80%
- ✅ 无安全漏洞
- ✅ 依赖安装成功
- ✅ 应用启动成功

## 7. 质量门禁

**状态**: ✅ 通过 / ❌ 不通过

**不通过原因**（如有）:
- {原因 1}
- {原因 2}

---

**CI 状态**: ✅ 完成
```

---

## 质量门禁

检查以下条件是否满足：

- ✅ CI 所有检查通过
- ✅ 无安全漏洞（或仅低危漏洞）
- ✅ 依赖版本兼容
- ✅ 应用可以正常启动

---

## CI 配置示例

### GitHub Actions

创建 `.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Poetry
      run: |
        curl -sSL https://install.python-poetry.org | python3 -
        echo "$HOME/.local/bin" >> $GITHUB_PATH
    
    - name: Install dependencies
      run: poetry install
    
    - name: Run ruff
      run: poetry run ruff check src/
    
    - name: Run mypy
      run: poetry run mypy src/
    
    - name: Run tests
      run: poetry run pytest tests/ --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### GitLab CI

创建 `.gitlab-ci.yml`：

```yaml
image: python:3.11

stages:
  - test

before_script:
  - pip install poetry
  - poetry install

test:
  stage: test
  script:
    - poetry run ruff check src/
    - poetry run mypy src/
    - poetry run pytest tests/ --cov=src --cov-report=term-missing
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

---

## 常见问题

### Q1: CI 失败了怎么办？
**A**:
1. 查看 CI 日志，定位失败原因
2. 在本地复现问题
3. 修复问题
4. 重新提交代码

### Q2: 如何加速 CI？
**A**:
- 使用缓存（依赖缓存）
- 并行运行测试
- 只运行变更相关的测试

### Q3: 如何处理依赖安全漏洞？
**A**:
- 升级到修复版本
- 如果无法升级，评估风险
- 如果风险可接受，记录并延后处理

---

**Skill 状态**: ✅ 已激活
# Skill: 单元测试

**阶段**: 7  
**版本**: v1.0

---

## 角色定位

你是测试工程师，负责编写和执行单元测试。

---

## 输入

- 源代码文件（需要测试的代码）

---

## 执行步骤

### 1. 识别测试目标

- 列出所有需要测试的函数/方法
- 识别核心业务逻辑
- 识别边界条件和异常情况

### 2. 编写测试用例

为每个函数/方法编写测试用例：
- **正常流程测试**: 测试正常输入和输出
- **边界条件测试**: 测试边界值（如空值、最大值、最小值）
- **异常情况测试**: 测试异常输入和错误处理

### 3. 使用 pytest 编写测试

测试文件命名：`test_{模块名}.py`  
测试函数命名：`test_{功能描述}`

### 4. 运行测试

```bash
pytest tests/unit/ -v
```

### 5. 生成覆盖率报告

```bash
pytest tests/unit/ --cov=src --cov-report=term-missing
```

---

## 产出物

### 1. 测试文件

在 `tests/unit/` 下创建测试文件。

### 2. 单元测试报告

生成 `07-单元测试报告-v1.md`：

```markdown
# 单元测试报告 v1: {需求简短描述}

**变更 ID**: CHANGE-XXX  
**创建时间**: YYYY-MM-DD

## 1. 测试概述

- **测试文件数**: {X} 个
- **测试用例数**: {Y} 个
- **测试代码行数**: {Z} 行

## 2. 测试清单

### 2.1 测试文件

| 测试文件 | 测试目标 | 用例数 |
|---------|---------|--------|
| `tests/unit/test_project_service.py` | ProjectService | 10 |
| `tests/unit/test_novel_service.py` | NovelService | 8 |

### 2.2 测试用例

#### test_project_service.py

| 用例名称 | 测试内容 | 状态 |
|---------|---------|------|
| `test_create_project_success` | 创建项目成功 | ✅ |
| `test_create_project_invalid_name` | 创建项目失败（无效名称） | ✅ |
| `test_get_project_success` | 获取项目成功 | ✅ |
| `test_get_project_not_found` | 获取项目失败（不存在） | ✅ |

## 3. 测试执行结果

### 3.1 执行命令
```bash
pytest tests/unit/ -v
```

### 3.2 执行结果

**状态**: ✅ 全部通过 / ❌ 部分失败

**统计**:
- **总用例数**: {X}
- **通过**: {Y}
- **失败**: {Z}
- **跳过**: {W}

**详细输出**:
```
{粘贴 pytest 输出}
```

### 3.3 失败用例（如有）

| 用例名称 | 失败原因 | 修复方案 |
|---------|---------|---------|
| `test_xxx` | {失败原因} | {修复方案} |

## 4. 覆盖率报告

### 4.1 执行命令
```bash
pytest tests/unit/ --cov=src --cov-report=term-missing
```

### 4.2 覆盖率统计

**总覆盖率**: {X}%

| 模块 | 语句数 | 未覆盖 | 覆盖率 |
|------|--------|--------|--------|
| `src/core/services/project_service.py` | 100 | 10 | 90% |
| `src/core/services/novel_service.py` | 80 | 5 | 94% |
| **总计** | 180 | 15 | 92% |

### 4.3 未覆盖代码

| 文件 | 行号 | 原因 |
|------|------|------|
| `src/core/services/project_service.py` | 50-55 | 异常处理分支 |

## 5. 测试质量评估

### 5.1 测试完整性

- ✅ 核心功能已测试
- ✅ 边界条件已测试
- ✅ 异常情况已测试

### 5.2 测试可维护性

- ✅ 测试用例清晰
- ✅ 使用 fixtures 复用代码
- ✅ 测试独立，无依赖

## 6. 改进建议

1. {改进建议 1}
2. {改进建议 2}

## 7. 质量门禁

**状态**: ✅ 通过 / ❌ 不通过

**检查项**:
- ✅ 所有测试通过
- ✅ 覆盖率 > 80%
- ✅ 核心功能已测试

---

**测试状态**: ✅ 完成
```

---

## 质量门禁

检查以下条件是否满足：

- ✅ 所有测试通过
- ✅ 覆盖率 > 80%
- ✅ 测试用例覆盖正常流程和异常流程
- ✅ 测试代码质量良好（清晰、可维护）

**如果质量门禁不通过**:
1. 分析失败原因
2. 修复代码或测试
3. 重新运行测试

---

## 测试编写指南

### 1. 测试文件结构

```python
# tests/unit/test_project_service.py
import pytest
from src.core.services.project_service import ProjectService
from src.core.models.project import Project

@pytest.fixture
def db_session():
    """数据库会话 fixture"""
    # 创建测试数据库会话
    pass

@pytest.fixture
def project_service(db_session):
    """ProjectService fixture"""
    return ProjectService(db_session)

class TestProjectService:
    """ProjectService 测试类"""
    
    def test_create_project_success(self, project_service):
        """测试创建项目成功"""
        # Arrange
        data = {"name": "测试项目", "novel_type": "玄幻"}
        
        # Act
        project = project_service.create(data)
        
        # Assert
        assert project.name == "测试项目"
        assert project.novel_type == "玄幻"
    
    def test_create_project_invalid_name(self, project_service):
        """测试创建项目失败（无效名称）"""
        # Arrange
        data = {"name": "", "novel_type": "玄幻"}
        
        # Act & Assert
        with pytest.raises(ValueError):
            project_service.create(data)
```

### 2. 测试命名规范

- **测试类**: `Test{类名}`
- **测试函数**: `test_{功能}_{场景}`

示例：
- `test_create_project_success`
- `test_create_project_invalid_name`
- `test_get_project_not_found`

### 3. AAA 模式

每个测试用例遵循 AAA 模式：
- **Arrange**: 准备测试数据
- **Act**: 执行被测试的代码
- **Assert**: 验证结果

### 4. 使用 fixtures

```python
@pytest.fixture
def sample_project():
    """示例项目 fixture"""
    return Project(
        id="123",
        name="测试项目",
        novel_type="玄幻"
    )

def test_update_project(project_service, sample_project):
    """测试更新项目"""
    updated = project_service.update(sample_project.id, {"name": "新名称"})
    assert updated.name == "新名称"
```

### 5. 测试异步函数

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await some_async_function()
    assert result == expected_value
```

---

## 常见测试场景

### 1. 测试数据库操作

```python
def test_create_and_retrieve(db_session, project_service):
    """测试创建和查询"""
    # 创建
    project = project_service.create({"name": "测试"})
    
    # 查询
    retrieved = project_service.get(project.id)
    assert retrieved.name == "测试"
```

### 2. 测试异常处理

```python
def test_get_nonexistent_project(project_service):
    """测试获取不存在的项目"""
    with pytest.raises(NotFoundError):
        project_service.get("nonexistent-id")
```

### 3. 测试边界条件

```python
def test_create_project_with_max_length_name(project_service):
    """测试最大长度名称"""
    long_name = "a" * 255
    project = project_service.create({"name": long_name})
    assert len(project.name) == 255
```

### 4. 使用 mock

```python
from unittest.mock import Mock, patch

def test_with_external_api(project_service):
    """测试外部 API 调用"""
    with patch('src.core.services.llm_service.LLMService.generate') as mock_generate:
        mock_generate.return_value = "生成的内容"
        
        result = project_service.generate_content()
        assert result == "生成的内容"
        mock_generate.assert_called_once()
```

---

## 常见问题

### Q1: 如何测试数据库操作？
**A**: 使用测试数据库或内存数据库（SQLite），在 `conftest.py` 中配置。

### Q2: 如何提高测试覆盖率？
**A**:
- 测试所有公共方法
- 测试边界条件
- 测试异常情况
- 使用 `--cov-report=html` 查看未覆盖代码

### Q3: 如何处理测试依赖？
**A**: 使用 fixtures 和 mock，避免测试之间的依赖。

---

**Skill 状态**: ✅ 已激活
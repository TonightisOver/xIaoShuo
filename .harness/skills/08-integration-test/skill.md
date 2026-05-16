# Skill: 集成测试

**阶段**: 8  
**版本**: v1.0

---

## 角色定位

你是集成测试工程师，负责测试多个模块协作和端到端流程。

---

## 输入

- 源代码文件
- 单元测试通过的代码

---

## 执行步骤

### 1. 识别集成测试场景

- API 接口测试
- LangGraph 流程端到端测试
- 数据库事务测试
- 多模块协作测试

### 2. 编写集成测试用例

- 测试完整的业务流程
- 测试模块间的交互
- 测试外部依赖（数据库、Redis、API）

### 3. 运行集成测试

```bash
pytest tests/integration/ -v
```

---

## 产出物

### 1. 测试文件

在 `tests/integration/` 下创建测试文件。

### 2. 集成测试报告

生成 `08-集成测试报告-v1.md`：

```markdown
# 集成测试报告 v1: {需求简短描述}

**变更 ID**: CHANGE-XXX  
**创建时间**: YYYY-MM-DD

## 1. 测试概述

- **测试场景数**: {X} 个
- **测试用例数**: {Y} 个

## 2. 测试场景

### 场景 1: API 接口测试

**测试目标**: 测试项目管理 API 接口

**测试用例**:
| 用例名称 | 测试内容 | 状态 |
|---------|---------|------|
| `test_create_project_api` | POST /api/projects | ✅ |
| `test_get_project_api` | GET /api/projects/{id} | ✅ |
| `test_update_project_api` | PUT /api/projects/{id} | ✅ |

### 场景 2: LangGraph 流程测试

**测试目标**: 测试小说创作流程端到端

**测试用例**:
| 用例名称 | 测试内容 | 状态 |
|---------|---------|------|
| `test_novel_creation_flow` | 完整创作流程 | ✅ |
| `test_flow_with_human_review` | 带人工审核的流程 | ✅ |

### 场景 3: 数据库事务测试

**测试目标**: 测试数据库事务和回滚

**测试用例**:
| 用例名称 | 测试内容 | 状态 |
|---------|---------|------|
| `test_transaction_commit` | 事务提交 | ✅ |
| `test_transaction_rollback` | 事务回滚 | ✅ |

## 3. 测试执行结果

### 3.1 执行命令
```bash
pytest tests/integration/ -v
```

### 3.2 执行结果

**状态**: ✅ 全部通过 / ❌ 部分失败

**统计**:
- **总用例数**: {X}
- **通过**: {Y}
- **失败**: {Z}

**详细输出**:
```
{粘贴 pytest 输出}
```

### 3.3 失败用例（如有）

| 用例名称 | 失败原因 | 修复方案 |
|---------|---------|---------|
| `test_xxx` | {失败原因} | {修复方案} |

## 4. 性能测试

### 4.1 API 响应时间

| 接口 | 平均响应时间 | P95 响应时间 | 目标 | 状态 |
|------|-------------|-------------|------|------|
| POST /api/projects | 50ms | 80ms | < 200ms | ✅ |
| GET /api/projects/{id} | 30ms | 50ms | < 200ms | ✅ |

### 4.2 LangGraph 流程执行时间

| 流程 | 执行时间 | 目标 | 状态 |
|------|---------|------|------|
| 小说创作流程 | 25s | < 30s | ✅ |

## 5. 质量门禁

**状态**: ✅ 通过 / ❌ 不通过

**检查项**:
- ✅ 核心流程测试通过
- ✅ API 接口测试通过
- ✅ 数据库事务测试通过
- ✅ 性能指标达标

---

**测试状态**: ✅ 完成
```

---

## 质量门禁

检查以下条件是否满足：

- ✅ 核心流程测试通过
- ✅ API 接口测试通过
- ✅ 数据库事务测试通过
- ✅ 性能指标达标

---

## 集成测试示例

### 1. API 接口测试

```python
# tests/integration/test_api/test_projects.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)

def test_create_project_api(client):
    """测试创建项目 API"""
    # Arrange
    data = {
        "name": "测试项目",
        "novel_type": "玄幻",
        "target_words": 100000
    }
    
    # Act
    response = client.post("/api/projects", json=data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "测试项目"

def test_get_project_api(client):
    """测试获取项目 API"""
    # 先创建项目
    create_response = client.post("/api/projects", json={"name": "测试"})
    project_id = create_response.json()["id"]
    
    # 获取项目
    response = client.get(f"/api/projects/{project_id}")
    
    assert response.status_code == 200
    assert response.json()["id"] == project_id
```

### 2. LangGraph 流程测试

```python
# tests/integration/test_langgraph/test_graph.py
import pytest
from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState

@pytest.mark.asyncio
async def test_novel_creation_flow():
    """测试小说创作流程"""
    # Arrange
    graph = create_novel_graph()
    initial_state: NovelState = {
        "project_id": "test-123",
        "novel_type": "玄幻",
        "idea": "一个修仙者的故事",
        # ... 其他字段
    }
    
    # Act
    final_state = await graph.ainvoke(initial_state)
    
    # Assert
    assert final_state["current_stage"] == "completed"
    assert len(final_state["chapters"]) > 0
```

### 3. 数据库事务测试

```python
# tests/integration/test_db/test_transactions.py
import pytest
from sqlalchemy.exc import IntegrityError
from src.core.services.project_service import ProjectService

def test_transaction_rollback(db_session):
    """测试事务回滚"""
    service = ProjectService(db_session)
    
    try:
        # 创建项目
        service.create({"name": "测试"})
        
        # 触发错误（如违反唯一约束）
        service.create({"name": "测试"})  # 假设名称唯一
    except IntegrityError:
        db_session.rollback()
    
    # 验证回滚后数据库状态
    projects = service.list()
    assert len(projects) == 0
```

---

## 常见问题

### Q1: 集成测试和单元测试的区别？
**A**:
- **单元测试**: 测试单个函数/方法，使用 mock 隔离依赖
- **集成测试**: 测试多个模块协作，使用真实依赖（数据库、API）

### Q2: 如何加速集成测试？
**A**:
- 使用测试数据库（内存数据库或独立测试库）
- 并行运行测试（`pytest -n auto`）
- 复用测试数据（使用 fixtures）

### Q3: 如何测试外部 API？
**A**:
- 开发环境：使用 mock
- 集成测试：使用测试环境的真实 API
- 或使用 VCR 录制和回放 HTTP 请求

---

**Skill 状态**: ✅ 已激活
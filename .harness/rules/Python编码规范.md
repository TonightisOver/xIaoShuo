# Python 编码规范

**版本**: v1.0  
**适用项目**: xIaoShuo - AI 中文网络小说生成平台  
**基于**: PEP 8, PEP 257, Python 最佳实践

---

## 1. 代码风格

### 1.1 缩进和空格

- **使用 4 个空格缩进**（不使用 Tab）
- **行长度限制**: 88 字符（black 默认）
- **续行缩进**: 使用 4 个空格

```python
# ✅ 正确
def long_function_name(
    var_one: str,
    var_two: int,
    var_three: dict
) -> bool:
    return True

# ❌ 错误
def long_function_name(var_one: str, var_two: int,
    var_three: dict) -> bool:
    return True
```

### 1.2 空行

- **顶层函数和类之间**: 2 个空行
- **类中的方法之间**: 1 个空行
- **函数内逻辑块之间**: 1 个空行（可选）

```python
# ✅ 正确
class MyClass:
    def method_one(self):
        pass
    
    def method_two(self):
        pass


def top_level_function():
    pass
```

### 1.3 导入

**导入顺序**:
1. 标准库
2. 第三方库
3. 本地模块

**每组之间空一行**:

```python
# ✅ 正确
import os
import sys
from typing import List, Dict

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from src.core.models.project import Project
from src.core.services.project_service import ProjectService
```

**禁止使用通配符导入**:

```python
# ❌ 错误
from module import *

# ✅ 正确
from module import specific_function, SpecificClass
```

---

## 2. 命名规范

### 2.1 命名风格

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块 | snake_case | `project_service.py` |
| 类 | PascalCase | `ProjectService` |
| 函数 | snake_case | `create_project()` |
| 变量 | snake_case | `project_id` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| 私有成员 | _前缀 | `_internal_method()` |
| 特殊方法 | __前后缀__ | `__init__()` |

### 2.2 命名原则

**使用有意义的名称**:

```python
# ❌ 错误
def f(x, y):
    return x + y

# ✅ 正确
def calculate_total_price(base_price: float, tax_rate: float) -> float:
    return base_price * (1 + tax_rate)
```

**避免单字母变量**（除了循环计数器）:

```python
# ✅ 可接受
for i in range(10):
    print(i)

# ❌ 错误
p = get_project()  # p 是什么？

# ✅ 正确
project = get_project()
```

**布尔变量使用 is/has/can 前缀**:

```python
# ✅ 正确
is_active = True
has_permission = False
can_edit = True
```

---

## 3. 类型注解

### 3.1 必须使用类型注解

**所有函数参数和返回值必须有类型注解**:

```python
# ✅ 正确
def create_project(name: str, novel_type: str) -> Project:
    return Project(name=name, novel_type=novel_type)

# ❌ 错误
def create_project(name, novel_type):
    return Project(name=name, novel_type=novel_type)
```

### 3.2 常用类型

```python
from typing import List, Dict, Optional, Union, Any, Tuple

# 基础类型
name: str = "test"
age: int = 25
price: float = 99.99
is_active: bool = True

# 容器类型
names: List[str] = ["Alice", "Bob"]
config: Dict[str, Any] = {"key": "value"}
coordinates: Tuple[float, float] = (1.0, 2.0)

# 可选类型
description: Optional[str] = None  # 等同于 str | None

# 联合类型
result: Union[int, str] = 42  # 等同于 int | str

# 函数类型
from typing import Callable
callback: Callable[[int, str], bool] = some_function
```

### 3.3 复杂类型

```python
from typing import TypedDict, Protocol

# TypedDict（用于字典结构）
class ProjectData(TypedDict):
    name: str
    novel_type: str
    target_words: int

def create_project(data: ProjectData) -> Project:
    pass

# Protocol（用于鸭子类型）
class Drawable(Protocol):
    def draw(self) -> None:
        ...

def render(obj: Drawable) -> None:
    obj.draw()
```

---

## 4. 函数和方法

### 4.1 函数长度

- **单个函数不超过 50 行**
- 如果超过，拆分为多个小函数

### 4.2 函数参数

- **参数数量不超过 5 个**
- 如果超过，使用数据类或字典

```python
# ❌ 错误（参数过多）
def create_project(name, type, words, style, background, setting):
    pass

# ✅ 正确（使用数据类）
from dataclasses import dataclass

@dataclass
class ProjectConfig:
    name: str
    novel_type: str
    target_words: int
    style: str
    background: str
    setting: str

def create_project(config: ProjectConfig) -> Project:
    pass
```

### 4.3 返回值

- **单一返回类型**（避免返回不同类型）
- **使用 Optional 表示可能为 None**

```python
# ❌ 错误（返回类型不一致）
def get_project(id: str):
    if exists(id):
        return Project(...)
    return None  # 类型不明确

# ✅ 正确
def get_project(id: str) -> Optional[Project]:
    if exists(id):
        return Project(...)
    return None
```

---

## 5. 类和对象

### 5.1 类设计原则

- **单一职责原则**: 一个类只负责一件事
- **开闭原则**: 对扩展开放，对修改关闭
- **依赖注入**: 通过构造函数注入依赖

```python
# ✅ 正确
class ProjectService:
    def __init__(self, db: Session, llm_service: LLMService):
        self.db = db
        self.llm_service = llm_service
    
    def create(self, data: dict) -> Project:
        # 使用注入的依赖
        pass
```

### 5.2 数据类

使用 `dataclass` 或 `pydantic` 定义数据类:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Project:
    id: str
    name: str
    created_at: datetime
    
    def is_recent(self) -> bool:
        return (datetime.now() - self.created_at).days < 7
```

### 5.3 属性访问

使用 `@property` 装饰器:

```python
class Project:
    def __init__(self, name: str):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, value: str) -> None:
        if not value:
            raise ValueError("Name cannot be empty")
        self._name = value
```

---

## 6. 异步编程

### 6.1 使用 async/await

```python
# ✅ 正确
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

async def process_data():
    data = await fetch_data("https://api.example.com")
    return data
```

### 6.2 异步上下文管理器

```python
class AsyncDatabaseConnection:
    async def __aenter__(self):
        self.conn = await create_connection()
        return self.conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.conn.close()

# 使用
async with AsyncDatabaseConnection() as conn:
    await conn.execute("SELECT * FROM projects")
```

---

## 7. 错误处理

### 7.1 异常处理

```python
# ✅ 正确
def get_project(id: str) -> Project:
    try:
        project = db.query(Project).filter(Project.id == id).first()
        if not project:
            raise NotFoundError(f"Project {id} not found")
        return project
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        raise DatabaseError("Failed to retrieve project") from e
```

### 7.2 自定义异常

```python
class ApplicationError(Exception):
    """应用基础异常"""
    pass

class NotFoundError(ApplicationError):
    """资源不存在异常"""
    pass

class ValidationError(ApplicationError):
    """验证错误异常"""
    pass
```

### 7.3 不要捕获所有异常

```python
# ❌ 错误
try:
    do_something()
except:  # 捕获所有异常，包括 KeyboardInterrupt
    pass

# ✅ 正确
try:
    do_something()
except (ValueError, TypeError) as e:  # 只捕获特定异常
    logger.error(f"Error: {e}")
    raise
```

---

## 8. 注释和文档

### 8.1 注释原则

**默认不写注释**（代码应该自解释）

**仅在以下情况添加注释**:
- 复杂的算法逻辑
- 非显而易见的业务规则
- 临时的 Workaround
- 性能优化的原因

```python
# ✅ 好的注释
def calculate_discount(price: float, user_level: int) -> float:
    # VIP 用户（level >= 5）享受额外 10% 折扣
    # 这是市场部 2026-05 的临时促销策略
    if user_level >= 5:
        return price * 0.9
    return price

# ❌ 不必要的注释
def get_project(id: str) -> Project:
    # 获取项目  # 函数名已经说明了
    return db.query(Project).filter(Project.id == id).first()
```

### 8.2 文档字符串（Docstring）

**仅为公共 API 编写 docstring**:

```python
def create_project(name: str, novel_type: str) -> Project:
    """创建新项目
    
    Args:
        name: 项目名称
        novel_type: 小说类型（玄幻、都市、科幻等）
    
    Returns:
        创建的项目对象
    
    Raises:
        ValidationError: 参数验证失败
    """
    pass
```

---

## 9. 测试

### 9.1 测试命名

```python
def test_create_project_success():
    """测试创建项目成功"""
    pass

def test_create_project_invalid_name():
    """测试创建项目失败（无效名称）"""
    pass
```

### 9.2 使用 fixtures

```python
import pytest

@pytest.fixture
def db_session():
    """数据库会话 fixture"""
    session = create_test_session()
    yield session
    session.close()

def test_create_project(db_session):
    service = ProjectService(db_session)
    project = service.create({"name": "test"})
    assert project.name == "test"
```

---

## 10. 日志

### 10.1 日志级别

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: 详细的调试信息
logger.debug(f"Processing project {project_id}")

# INFO: 一般信息
logger.info(f"Project {project_id} created successfully")

# WARNING: 警告信息
logger.warning(f"Project {project_id} has no chapters")

# ERROR: 错误信息
logger.error(f"Failed to create project: {error}")

# CRITICAL: 严重错误
logger.critical(f"Database connection lost")
```

### 10.2 日志格式

```python
# 使用 f-string 格式化
logger.info(f"User {user_id} created project {project_id}")

# 包含上下文信息
logger.error(f"Failed to generate chapter", extra={
    "project_id": project_id,
    "chapter_number": chapter_number,
    "error": str(e)
})
```

---

## 11. 性能优化

### 11.1 避免 N+1 查询

```python
# ❌ 错误（N+1 查询）
projects = db.query(Project).all()
for project in projects:
    chapters = project.chapters  # 每次都查询数据库

# ✅ 正确（使用 joinedload）
from sqlalchemy.orm import joinedload

projects = db.query(Project).options(joinedload(Project.chapters)).all()
for project in projects:
    chapters = project.chapters  # 已经加载
```

### 11.2 使用生成器

```python
# ❌ 错误（一次性加载所有数据）
def get_all_projects():
    return db.query(Project).all()

# ✅ 正确（使用生成器）
def get_all_projects():
    for project in db.query(Project).yield_per(100):
        yield project
```

---

## 12. 安全性

### 12.1 输入验证

```python
from pydantic import BaseModel, validator

class ProjectCreate(BaseModel):
    name: str
    novel_type: str
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
```

### 12.2 SQL 注入防护

```python
# ❌ 错误（SQL 注入风险）
query = f"SELECT * FROM projects WHERE name = '{name}'"
db.execute(query)

# ✅ 正确（使用参数化查询）
db.query(Project).filter(Project.name == name).all()
```

### 12.3 敏感信息

```python
# ❌ 错误（硬编码密钥）
API_KEY = "sk-1234567890abcdef"

# ✅ 正确（从环境变量读取）
import os
API_KEY = os.getenv("DEEPSEEK_API_KEY")
```

---

## 13. 代码检查工具

### 13.1 ruff 配置

在 `pyproject.toml` 中配置:

```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/*" = ["S101"]  # 允许测试中使用 assert
```

### 13.2 mypy 配置

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

---

## 14. 违规示例

### ❌ 错误示例 1: 缺少类型注解

```python
def create_project(name, novel_type):
    return Project(name=name, novel_type=novel_type)
```

### ❌ 错误示例 2: 函数过长

```python
def process_project(project):
    # 100+ 行代码
    # 应该拆分为多个小函数
    pass
```

### ❌ 错误示例 3: 不一致的命名

```python
class projectService:  # 应该是 ProjectService
    def CreateProject(self):  # 应该是 create_project
        MAX_retries = 3  # 应该是 MAX_RETRIES
```

---

## 15. 正确示例

### ✅ 正确示例 1: 完整的类型注解

```python
from typing import Optional

def create_project(name: str, novel_type: str) -> Project:
    """创建新项目"""
    return Project(name=name, novel_type=novel_type)

def get_project(id: str) -> Optional[Project]:
    """获取项目"""
    return db.query(Project).filter(Project.id == id).first()
```

### ✅ 正确示例 2: 清晰的代码结构

```python
class ProjectService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, data: dict) -> Project:
        """创建项目"""
        self._validate_data(data)
        project = self._build_project(data)
        return self._save_project(project)
    
    def _validate_data(self, data: dict) -> None:
        """验证数据"""
        if not data.get("name"):
            raise ValidationError("Name is required")
    
    def _build_project(self, data: dict) -> Project:
        """构建项目对象"""
        return Project(**data)
    
    def _save_project(self, project: Project) -> Project:
        """保存项目"""
        self.db.add(project)
        self.db.commit()
        return project
```

---

**规范状态**: ✅ 已生效
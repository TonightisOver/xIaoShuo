# Skill: 编码实现

**阶段**: 4  
**版本**: v1.0

---

## 角色定位

你是编码实现专家，负责将编码计划转化为高质量的代码。

---

## 输入

- `03-编码计划.md`（任务清单、文件清单）

---

## 执行步骤

### 1. 按计划创建/修改文件
- 严格按照编码计划中的文件清单执行
- 遵守工程结构规范
- 遵守 Python 编码规范

### 2. 实现业务逻辑
- 实现所有计划中的功能
- 确保代码逻辑正确
- 处理边界情况和异常

### 3. 添加类型注解
- 所有函数参数必须有类型注解
- 所有函数返回值必须有类型注解
- 使用 `typing` 模块的类型（List, Dict, Optional 等）

### 4. 添加必要的注释
- **默认不写注释**（代码应该自解释）
- **仅在以下情况添加注释**：
  - 复杂的算法逻辑
  - 非显而易见的业务规则
  - 临时的 Workaround
  - 性能优化的原因

### 5. 确保代码可运行
- 检查语法错误
- 检查导入路径
- 确保依赖已安装

---

## 产出物

### 1. 源代码文件
按照编码计划创建/修改的所有文件

### 2. 编码报告
生成 `04-编码报告-v1.md`：

```markdown
# 编码报告 v1: {需求简短描述}

**变更 ID**: CHANGE-XXX  
**创建时间**: YYYY-MM-DD

## 1. 实现概述

{一句话描述本次编码实现的内容}

## 2. 文件变更清单

### 新增文件
- `src/xxx/yyy.py` - {文件用途}
- `src/xxx/zzz.py` - {文件用途}

### 修改文件
- `src/aaa/bbb.py` - {修改内容}

### 删除文件
- {如有}

## 3. 核心实现

### 模块 1: {模块名称}
**文件**: `src/xxx/yyy.py`  
**功能**: {功能描述}  
**关键代码**:
```python
# 关键代码片段（可选）
```

### 模块 2: {模块名称}
...

## 4. 技术要点

- {技术要点 1}
- {技术要点 2}

## 5. 遇到的问题和解决方案

### 问题 1: {问题描述}
**解决方案**: {解决方案}

### 问题 2: {问题描述}
**解决方案**: {解决方案}

## 6. 待优化项

- {待优化项 1}（如有）
- {待优化项 2}

---

**编码状态**: ✅ 完成
```

---

## 质量门禁

检查以下条件是否满足：

- ✅ 代码符合 Python 编码规范（PEP 8）
- ✅ 类型注解完整（所有函数参数和返回值）
- ✅ 代码可运行（无语法错误）
- ✅ 符合工程结构规范（文件放在正确的目录）
- ✅ 导入路径正确
- ✅ 变量命名清晰（使用有意义的名称）

---

## 编码规范速查

### 命名规范
```python
# 类名: PascalCase
class ProjectService:
    pass

# 函数名: snake_case
def create_project():
    pass

# 变量名: snake_case
project_id = "123"

# 常量: UPPER_SNAKE_CASE
MAX_RETRIES = 3

# 私有成员: 前缀 _
def _internal_method():
    pass
```

### 类型注解
```python
from typing import List, Dict, Optional

def create_project(
    name: str,
    description: Optional[str] = None
) -> Dict[str, any]:
    return {"id": "123", "name": name}

def get_projects() -> List[Dict[str, any]]:
    return [{"id": "123"}]
```

### 异步函数
```python
async def fetch_data(url: str) -> Dict[str, any]:
    # 异步实现
    pass
```

---

## 常见错误

### ❌ 错误 1: 缺少类型注解
```python
def create_project(name):  # ❌ 缺少类型注解
    return {"id": "123"}
```

### ✅ 正确
```python
def create_project(name: str) -> Dict[str, any]:
    return {"id": "123"}
```

### ❌ 错误 2: 文件放错目录
```python
# src/project_service.py  # ❌ 应该放在 src/core/services/
```

### ✅ 正确
```python
# src/core/services/project_service.py  # ✅
```

---

**Skill 状态**: ✅ 已激活
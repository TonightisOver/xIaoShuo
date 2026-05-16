# FastAPI 开发规范

**版本**: v1.0  
**适用项目**: xIaoShuo - AI 中文网络小说生成平台  
**FastAPI 版本**: 0.110+

---

## 1. 项目结构

```
src/api/
├── __init__.py
├── deps.py                # 依赖注入
├── routes/                # 路由模块
│   ├── __init__.py
│   ├── projects.py
│   ├── novels.py
│   └── characters.py
└── schemas/               # Pydantic 模型
    ├── __init__.py
    ├── project.py
    ├── novel.py
    └── character.py
```

---

## 2. 路由设计

### 2.1 路由组织

```python
# src/api/routes/projects.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas.project import ProjectCreate, ProjectResponse
from src.core.services.project_service import ProjectService

router = APIRouter(
    prefix="/projects",
    tags=["projects"]
)

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db)
) -> ProjectResponse:
    """创建新项目"""
    service = ProjectService(db)
    project = service.create(data.model_dump())
    return ProjectResponse.model_validate(project)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db)
) -> ProjectResponse:
    """获取项目详情"""
    service = ProjectService(db)
    project = service.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    return ProjectResponse.model_validate(project)
```

### 2.2 路由命名规范

| 操作 | HTTP 方法 | 路径 | 函数名 |
|------|----------|------|--------|
| 列表 | GET | `/projects` | `list_projects` |
| 创建 | POST | `/projects` | `create_project` |
| 详情 | GET | `/projects/{id}` | `get_project` |
| 更新 | PUT | `/projects/{id}` | `update_project` |
| 部分更新 | PATCH | `/projects/{id}` | `patch_project` |
| 删除 | DELETE | `/projects/{id}` | `delete_project` |

---

## 3. Pydantic 模型

### 3.1 请求模型

```python
# src/api/schemas/project.py
from pydantic import BaseModel, Field, validator
from typing import Optional

class ProjectCreate(BaseModel):
    """创建项目请求模型"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    novel_type: str = Field(..., description="小说类型")
    target_words: int = Field(..., gt=0, description="目标字数")
    description: Optional[str] = Field(None, max_length=1000, description="项目描述")
    
    @validator('name')
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "我的玄幻小说",
                "novel_type": "玄幻",
                "target_words": 100000,
                "description": "一个修仙者的故事"
            }
        }
```

### 3.2 响应模型

```python
from datetime import datetime
from pydantic import ConfigDict

class ProjectResponse(BaseModel):
    """项目响应模型"""
    id: str
    name: str
    novel_type: str
    target_words: int
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

### 3.3 更新模型

```python
class ProjectUpdate(BaseModel):
    """更新项目请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    novel_type: Optional[str] = None
    target_words: Optional[int] = Field(None, gt=0)
    description: Optional[str] = Field(None, max_length=1000)
```

---

## 4. 依赖注入

### 4.1 数据库会话

```python
# src/api/deps.py
from typing import Generator
from sqlalchemy.orm import Session

from src.db.session import SessionLocal

def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 4.2 当前用户

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户"""
    token = credentials.credentials
    # 验证 token
    user = verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return user
```

### 4.3 分页参数

```python
from fastapi import Query

class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页数量")
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

# 使用
@router.get("/projects")
async def list_projects(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    projects = service.list(
        offset=pagination.offset,
        limit=pagination.page_size
    )
    return projects
```

---

## 5. 错误处理

### 5.1 自定义异常

```python
# src/core/exceptions.py
class ApplicationError(Exception):
    """应用基础异常"""
    pass

class NotFoundError(ApplicationError):
    """资源不存在"""
    pass

class ValidationError(ApplicationError):
    """验证错误"""
    pass

class UnauthorizedError(ApplicationError):
    """未授权"""
    pass
```

### 5.2 异常处理器

```python
# src/main.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.core.exceptions import NotFoundError, ValidationError

app = FastAPI()

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "not_found", "message": str(exc)}
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "validation_error", "message": str(exc)}
    )
```

### 5.3 在路由中使用

```python
from src.core.exceptions import NotFoundError

@router.get("/{project_id}")
async def get_project(project_id: str, db: Session = Depends(get_db)):
    service = ProjectService(db)
    project = service.get(project_id)
    if not project:
        raise NotFoundError(f"Project {project_id} not found")
    return project
```

---

## 6. 响应格式

### 6.1 统一响应格式

```python
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """统一响应格式"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None

# 使用
@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> ApiResponse[ProjectResponse]:
    project = service.get(project_id)
    return ApiResponse(
        success=True,
        data=ProjectResponse.model_validate(project)
    )
```

### 6.2 分页响应

```python
class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.get("/projects")
async def list_projects(
    pagination: PaginationParams = Depends()
) -> PaginatedResponse[ProjectResponse]:
    projects, total = service.list_with_count(
        offset=pagination.offset,
        limit=pagination.page_size
    )
    return PaginatedResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )
```

---

## 7. 中间件

### 7.1 CORS 中间件

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 7.2 请求日志中间件

```python
import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 记录请求
    logger.info(f"Request: {request.method} {request.url}")
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} "
        f"(took {process_time:.3f}s)"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

---

## 8. 后台任务

### 8.1 使用 BackgroundTasks

```python
from fastapi import BackgroundTasks

def send_notification(project_id: str, message: str):
    """发送通知（后台任务）"""
    # 发送通知逻辑
    logger.info(f"Sending notification for project {project_id}")

@router.post("/projects")
async def create_project(
    data: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    project = service.create(data.model_dump())
    
    # 添加后台任务
    background_tasks.add_task(
        send_notification,
        project.id,
        "Project created successfully"
    )
    
    return project
```

### 8.2 使用 Celery

```python
from src.core.tasks import generate_chapter_task

@router.post("/projects/{project_id}/chapters")
async def generate_chapter(
    project_id: str,
    chapter_number: int,
    db: Session = Depends(get_db)
):
    # 提交 Celery 任务
    task = generate_chapter_task.delay(project_id, chapter_number)
    
    return {
        "task_id": task.id,
        "status": "processing"
    }

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = generate_chapter_task.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.ready() else None
    }
```

---

## 9. 文件上传

### 9.1 单文件上传

```python
from fastapi import File, UploadFile

@router.post("/projects/{project_id}/cover")
async def upload_cover(
    project_id: str,
    file: UploadFile = File(...)
):
    # 验证文件类型
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are allowed"
        )
    
    # 保存文件
    file_path = f"uploads/{project_id}/cover.{file.filename.split('.')[-1]}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"file_path": file_path}
```

### 9.2 多文件上传

```python
from typing import List

@router.post("/projects/{project_id}/images")
async def upload_images(
    project_id: str,
    files: List[UploadFile] = File(...)
):
    file_paths = []
    for file in files:
        file_path = f"uploads/{project_id}/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        file_paths.append(file_path)
    
    return {"file_paths": file_paths}
```

---

## 10. WebSocket

### 10.1 WebSocket 端点

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            # 处理消息
            response = process_message(data)
            
            # 发送响应
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from project {project_id}")
```

### 10.2 WebSocket 管理器

```python
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
    
    def disconnect(self, project_id: str, websocket: WebSocket):
        self.active_connections[project_id].remove(websocket)
    
    async def broadcast(self, project_id: str, message: str):
        for connection in self.active_connections.get(project_id, []):
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await manager.connect(project_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(project_id, f"Message: {data}")
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
```

---

## 11. 测试

### 11.1 测试客户端

```python
# tests/integration/test_api/test_projects.py
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_project():
    """测试创建项目"""
    response = client.post(
        "/api/projects",
        json={
            "name": "测试项目",
            "novel_type": "玄幻",
            "target_words": 100000
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试项目"

def test_get_project():
    """测试获取项目"""
    # 先创建项目
    create_response = client.post("/api/projects", json={"name": "测试"})
    project_id = create_response.json()["id"]
    
    # 获取项目
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id
```

### 11.2 异步测试

```python
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_create_project_async():
    """异步测试创建项目"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/projects",
            json={"name": "测试项目"}
        )
    assert response.status_code == 201
```

---

## 12. 最佳实践

### ✅ 推荐做法

1. **使用 Pydantic 模型验证输入**
2. **使用依赖注入管理资源**
3. **使用异步函数提高性能**
4. **统一错误处理**
5. **添加 API 文档示例**
6. **使用类型注解**
7. **实现分页**
8. **添加请求日志**
9. **使用后台任务处理耗时操作**
10. **编写集成测试**

### ❌ 避免做法

1. **不要在路由中写业务逻辑**
2. **不要忽略输入验证**
3. **不要返回敏感信息**
4. **不要使用同步数据库操作（如果可以异步）**
5. **不要忽略错误处理**
6. **不要硬编码配置**
7. **不要忘记关闭资源**
8. **不要在生产环境暴露调试信息**

---

**规范状态**: ✅ 已生效
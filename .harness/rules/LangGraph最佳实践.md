# LangGraph 最佳实践

**版本**: v1.0  
**适用项目**: xIaoShuo - AI 中文网络小说生成平台  
**LangGraph 版本**: 0.2+

---

## 1. StateGraph 设计

### 1.1 State 定义

使用 `TypedDict` 定义状态:

```python
from typing import TypedDict, List, Dict, Optional

class NovelState(TypedDict):
    # 项目元信息
    project_id: str
    novel_type: str
    target_words: int
    
    # 创作内容
    idea: str
    world_setting: Optional[Dict]
    characters: List[Dict]
    relationships: Dict
    outline: Optional[Dict]
    chapter_outlines: List[Dict]
    chapters: List[Dict]
    
    # 流程控制
    current_stage: str
    approval_status: str  # pending/approved/rejected
    revision_requests: List[str]
    
    # 质量指标
    quality_scores: Dict[str, float]
    
    # 错误信息
    errors: List[str]
```

### 1.2 State 设计原则

**最小化状态**:
- 只保存必要的信息
- 避免冗余数据
- 可以从其他字段计算的数据不要保存

**不可变性**:
- 不要直接修改 state
- 总是返回新的 state

```python
# ❌ 错误（直接修改）
def node_function(state: NovelState) -> NovelState:
    state["chapters"].append(new_chapter)  # 直接修改
    return state

# ✅ 正确（返回新 state）
def node_function(state: NovelState) -> NovelState:
    return {
        **state,
        "chapters": [*state["chapters"], new_chapter]
    }
```

---

## 2. 节点（Node）设计

### 2.1 节点函数签名

```python
from langgraph.graph import StateGraph

def node_function(state: NovelState) -> NovelState:
    """节点函数
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    # 处理逻辑
    result = process(state)
    
    # 返回更新后的状态
    return {
        **state,
        "field": result
    }
```

### 2.2 异步节点

```python
async def async_node_function(state: NovelState) -> NovelState:
    """异步节点函数"""
    # 异步处理
    result = await async_process(state)
    
    return {
        **state,
        "field": result
    }
```

### 2.3 节点职责

**单一职责**:
- 每个节点只做一件事
- 避免"上帝节点"

```python
# ❌ 错误（节点做太多事）
def process_everything(state: NovelState) -> NovelState:
    world = build_world(state)
    characters = design_characters(state)
    outline = generate_outline(state)
    # ... 太多逻辑
    return state

# ✅ 正确（拆分为多个节点）
def build_world_node(state: NovelState) -> NovelState:
    world = build_world(state)
    return {**state, "world_setting": world}

def design_characters_node(state: NovelState) -> NovelState:
    characters = design_characters(state)
    return {**state, "characters": characters}
```

### 2.4 错误处理

```python
def node_with_error_handling(state: NovelState) -> NovelState:
    """带错误处理的节点"""
    try:
        result = risky_operation(state)
        return {
            **state,
            "field": result,
            "errors": []  # 清空错误
        }
    except Exception as e:
        logger.error(f"Node error: {e}")
        return {
            **state,
            "errors": [*state.get("errors", []), str(e)],
            "current_stage": "error"
        }
```

---

## 3. 边（Edge）和路由

### 3.1 条件路由

```python
def should_regenerate(state: NovelState) -> str:
    """条件路由函数
    
    Returns:
        下一个节点的名称
    """
    quality_score = state.get("quality_scores", {}).get("overall", 0)
    
    if quality_score >= 0.8:
        return "next_node"
    elif quality_score >= 0.6:
        return "review_node"
    else:
        return "regenerate_node"

# 在图中使用
graph.add_conditional_edges(
    "quality_check",
    should_regenerate,
    {
        "next_node": "outline_generation",
        "review_node": "human_review",
        "regenerate_node": "world_building"
    }
)
```

### 3.2 路由设计原则

**明确的路由逻辑**:
- 路由条件清晰
- 避免复杂的嵌套条件

```python
# ❌ 错误（复杂的嵌套条件）
def complex_router(state: NovelState) -> str:
    if state["approval_status"] == "pending":
        if state["quality_scores"]["overall"] > 0.8:
            if len(state["chapters"]) > 0:
                return "next"
            else:
                return "generate"
        else:
            return "review"
    else:
        return "end"

# ✅ 正确（清晰的路由逻辑）
def clear_router(state: NovelState) -> str:
    # 先检查审批状态
    if state["approval_status"] != "pending":
        return "end"
    
    # 再检查质量分数
    if state["quality_scores"]["overall"] < 0.8:
        return "review"
    
    # 最后检查章节
    if len(state["chapters"]) == 0:
        return "generate"
    
    return "next"
```

---

## 4. Checkpointer（检查点）

### 4.1 使用 MemorySaver

```python
from langgraph.checkpoint.memory import MemorySaver

# 创建 checkpointer
checkpointer = MemorySaver()

# 创建图时传入
graph = StateGraph(NovelState)
# ... 添加节点和边
compiled_graph = graph.compile(checkpointer=checkpointer)
```

### 4.2 使用持久化 Checkpointer

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# 使用 SQLite 持久化
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

compiled_graph = graph.compile(checkpointer=checkpointer)
```

### 4.3 Checkpoint 配置

```python
# 配置 checkpoint
config = {
    "configurable": {
        "thread_id": f"project-{project_id}",
        "checkpoint_ns": "novel_creation"
    }
}

# 使用 checkpoint
result = await compiled_graph.ainvoke(initial_state, config=config)
```

### 4.4 恢复执行

```python
# 从 checkpoint 恢复
async def resume_from_checkpoint(project_id: str):
    config = {
        "configurable": {
            "thread_id": f"project-{project_id}"
        }
    }
    
    # 获取最新状态
    state = await compiled_graph.aget_state(config)
    
    # 继续执行
    result = await compiled_graph.ainvoke(state.values, config=config)
    return result
```

---

## 5. Human-in-the-Loop

### 5.1 中断节点

```python
from langgraph.graph import END

def human_review_node(state: NovelState) -> NovelState:
    """人工审核节点"""
    # 标记需要人工审核
    return {
        **state,
        "approval_status": "pending",
        "current_stage": "human_review"
    }

# 添加中断
graph.add_node("human_review", human_review_node)
graph.add_edge("human_review", END)  # 中断执行
```

### 5.2 恢复执行

```python
async def approve_and_continue(project_id: str, feedback: str):
    """用户审核通过，继续执行"""
    config = {
        "configurable": {
            "thread_id": f"project-{project_id}"
        }
    }
    
    # 获取当前状态
    state = await compiled_graph.aget_state(config)
    
    # 更新状态
    updated_state = {
        **state.values,
        "approval_status": "approved",
        "revision_requests": [feedback] if feedback else []
    }
    
    # 继续执行
    result = await compiled_graph.ainvoke(updated_state, config=config)
    return result
```

---

## 6. 流式输出

### 6.1 使用 astream

```python
async def stream_novel_creation(initial_state: NovelState):
    """流式执行小说创作"""
    config = {
        "configurable": {
            "thread_id": f"project-{initial_state['project_id']}"
        }
    }
    
    async for event in compiled_graph.astream(initial_state, config=config):
        # 处理每个节点的输出
        node_name = list(event.keys())[0]
        node_output = event[node_name]
        
        print(f"Node {node_name} completed")
        print(f"Current stage: {node_output.get('current_stage')}")
        
        # 可以在这里更新 UI 或发送通知
        yield node_output
```

### 6.2 流式事件

```python
async def stream_with_events(initial_state: NovelState):
    """流式输出带事件信息"""
    async for event in compiled_graph.astream_events(
        initial_state,
        version="v1"
    ):
        kind = event["event"]
        
        if kind == "on_chain_start":
            print(f"Starting node: {event['name']}")
        elif kind == "on_chain_end":
            print(f"Finished node: {event['name']}")
        elif kind == "on_chain_error":
            print(f"Error in node: {event['name']}")
            print(f"Error: {event['data']['error']}")
```

---

## 7. 子图（Subgraph）

### 7.1 创建子图

```python
def create_character_design_subgraph() -> StateGraph:
    """创建人物设计子图"""
    subgraph = StateGraph(NovelState)
    
    subgraph.add_node("generate_protagonist", generate_protagonist_node)
    subgraph.add_node("generate_supporting", generate_supporting_node)
    subgraph.add_node("build_relationships", build_relationships_node)
    
    subgraph.set_entry_point("generate_protagonist")
    subgraph.add_edge("generate_protagonist", "generate_supporting")
    subgraph.add_edge("generate_supporting", "build_relationships")
    subgraph.add_edge("build_relationships", END)
    
    return subgraph.compile()
```

### 7.2 在主图中使用子图

```python
# 创建主图
main_graph = StateGraph(NovelState)

# 添加子图作为节点
character_subgraph = create_character_design_subgraph()
main_graph.add_node("character_design", character_subgraph)

# 连接子图
main_graph.add_edge("world_building", "character_design")
main_graph.add_edge("character_design", "outline_generation")
```

---

## 8. 性能优化

### 8.1 并行执行

```python
from langgraph.graph import StateGraph

# 使用 Send 实现并行
from langgraph.types import Send

def fan_out_node(state: NovelState) -> List[Send]:
    """扇出节点，并行处理多个章节"""
    return [
        Send("generate_chapter", {"chapter_number": i, **state})
        for i in range(1, 11)  # 并行生成 10 章
    ]

def fan_in_node(state: NovelState) -> NovelState:
    """扇入节点，收集结果"""
    return state

graph.add_node("fan_out", fan_out_node)
graph.add_node("generate_chapter", generate_chapter_node)
graph.add_node("fan_in", fan_in_node)
```

### 8.2 缓存

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_prompt_template(template_name: str) -> str:
    """缓存 prompt 模板"""
    with open(f"prompts/{template_name}.md") as f:
        return f.read()

def node_with_cache(state: NovelState) -> NovelState:
    """使用缓存的节点"""
    template = get_prompt_template("world_building")
    # 使用模板
    pass
```

---

## 9. 测试

### 9.1 单元测试节点

```python
import pytest

def test_world_building_node():
    """测试世界观构建节点"""
    # Arrange
    initial_state: NovelState = {
        "project_id": "test-123",
        "novel_type": "玄幻",
        "idea": "修仙世界",
        # ... 其他字段
    }
    
    # Act
    result = build_world_node(initial_state)
    
    # Assert
    assert "world_setting" in result
    assert result["world_setting"] is not None
    assert "background" in result["world_setting"]
```

### 9.2 集成测试图

```python
@pytest.mark.asyncio
async def test_novel_creation_flow():
    """测试完整的小说创作流程"""
    # Arrange
    graph = create_novel_graph()
    initial_state: NovelState = {
        "project_id": "test-123",
        "novel_type": "玄幻",
        "idea": "修仙者的故事",
        # ... 其他字段
    }
    
    # Act
    final_state = await graph.ainvoke(initial_state)
    
    # Assert
    assert final_state["current_stage"] == "completed"
    assert len(final_state["chapters"]) > 0
```

---

## 10. 常见模式

### 10.1 重试模式

```python
def node_with_retry(state: NovelState, max_retries: int = 3) -> NovelState:
    """带重试的节点"""
    retries = state.get("retries", 0)
    
    try:
        result = risky_operation(state)
        return {
            **state,
            "field": result,
            "retries": 0  # 重置重试次数
        }
    except Exception as e:
        if retries < max_retries:
            logger.warning(f"Retry {retries + 1}/{max_retries}")
            return {
                **state,
                "retries": retries + 1,
                "current_stage": "retry"
            }
        else:
            logger.error(f"Max retries reached: {e}")
            return {
                **state,
                "errors": [*state.get("errors", []), str(e)],
                "current_stage": "error"
            }
```

### 10.2 验证模式

```python
def validation_node(state: NovelState) -> NovelState:
    """验证节点"""
    errors = []
    
    # 验证必填字段
    if not state.get("idea"):
        errors.append("Idea is required")
    
    if not state.get("novel_type"):
        errors.append("Novel type is required")
    
    # 验证数据格式
    if state.get("target_words", 0) < 1000:
        errors.append("Target words must be at least 1000")
    
    if errors:
        return {
            **state,
            "errors": errors,
            "current_stage": "validation_failed"
        }
    
    return {
        **state,
        "errors": [],
        "current_stage": "validated"
    }
```

---

## 11. 调试和监控

### 11.1 日志

```python
import logging

logger = logging.getLogger(__name__)

def node_with_logging(state: NovelState) -> NovelState:
    """带日志的节点"""
    logger.info(f"Processing project {state['project_id']}")
    logger.debug(f"Current stage: {state['current_stage']}")
    
    try:
        result = process(state)
        logger.info(f"Node completed successfully")
        return {**state, "field": result}
    except Exception as e:
        logger.error(f"Node failed: {e}", exc_info=True)
        raise
```

### 11.2 可视化

```python
from langgraph.graph import StateGraph

# 创建图
graph = StateGraph(NovelState)
# ... 添加节点和边

# 生成 Mermaid 图
mermaid_code = graph.get_graph().draw_mermaid()
print(mermaid_code)

# 或生成 PNG（需要安装 graphviz）
graph.get_graph().draw_png("graph.png")
```

---

## 12. 最佳实践总结

### ✅ 推荐做法

1. **使用 TypedDict 定义 State**
2. **节点函数保持单一职责**
3. **使用 Checkpointer 支持中断恢复**
4. **实现 Human-in-the-Loop**
5. **使用条件路由处理不同场景**
6. **添加错误处理和重试机制**
7. **使用流式输出提供实时反馈**
8. **编写单元测试和集成测试**
9. **添加日志和监控**
10. **使用子图组织复杂流程**

### ❌ 避免做法

1. **不要直接修改 state**
2. **不要在节点中做太多事情**
3. **不要忽略错误处理**
4. **不要在生产环境使用 MemorySaver**
5. **不要在节点中阻塞太久**
6. **不要忽略类型注解**
7. **不要在路由函数中做复杂计算**
8. **不要忘记测试边界情况**

---

**规范状态**: ✅ 已生效
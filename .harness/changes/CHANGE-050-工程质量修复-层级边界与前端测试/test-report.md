# CHANGE-050 测试报告

## 测试文件

`tests/unit/test_change050_layer_boundary.py`

## 执行结果

```
15 passed in 1.05s
```

全部通过，无失败、无跳过。

## 测试覆盖

### 1. Re-export 链路测试（6 项）

| 测试 | 结果 |
|------|------|
| `from src.core.context import NovelContextBuilder` 导入成功 | PASSED |
| `from src.core.context import GenerationContext, RewriteContext, BlueprintContext` 导入成功 | PASSED |
| `from src.api.services.novel_context_service import NovelContextBuilder` 导入成功 | PASSED |
| 两条路径导入的 `NovelContextBuilder` 是同一个类（`is` 检查） | PASSED |
| `src.core.context.novel_context.__all__` 包含全部四个符号 | PASSED |
| `src.core.context.__init__.__all__` 包含全部四个符号 | PASSED |

### 2. 层级边界静态检查（3 项）

使用 `ast` 模块解析源文件，静态检查导入关系，无需运行时依赖。

| 测试 | 结果 |
|------|------|
| `src/core/context/novel_context.py` 不直接导入 `src.api.models.db_models` | PASSED |
| `src/core/llm/` 下所有文件不导入 `src.api.models` | PASSED |
| `src/core/langgraph/nodes/` 下所有文件不导入 `src.api.services` | PASSED |

### 3. NovelContextBuilder 基本功能测试（6 项，mock AsyncSession）

| 测试 | 结果 |
|------|------|
| 无参数实例化成功 | PASSED |
| `build_generation_context` 方法存在且可调用 | PASSED |
| `build_rewrite_context` 方法存在且可调用 | PASSED |
| `build_blueprint_context` 方法存在且可调用 | PASSED |
| `build_generation_context` 返回 `GenerationContext` 实例 | PASSED |
| 无数据时 `GenerationContext` 使用默认值（`暂无世界观` / `暂无人物` / `""` / `""`） | PASSED |

## 修复说明

初次运行时 2 个异步测试失败，原因：`_build_world_str` 在 WorldSetting 非 None 时会调用 `json.dumps`，而 MagicMock 属性不可序列化。修复方式：将 world-setting 查询的 mock 结果也设为 `scalar_one_or_none() → None`，与实际"无数据"场景一致，触发 `return "暂无世界观"` 分支。

## 层级边界确认

- `src/core/context/novel_context.py` 仅做 re-export，不含 `db_models` 直接导入 ✓
- `src/core/llm/`（6 个文件）均未导入 `src.api.models` ✓
- `src/core/langgraph/nodes/`（8 个文件）均未导入 `src.api.services` ✓

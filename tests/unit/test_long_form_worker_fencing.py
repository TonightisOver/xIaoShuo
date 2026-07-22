"""长篇后台入口的任务状态写必须携带 worker lease 身份。"""

import ast
import inspect

from src.api.services.generation import long_form_generation_helpers as helpers


def test_long_form_background_task_writes_pass_worker_id() -> None:
    tree = ast.parse(inspect.getsource(helpers))
    background_functions = {
        "generate_volume_background",
        "generate_chapters_background",
        "generate_long_form_background",
    }
    missing: list[str] = []

    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if node.name not in background_functions:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute):
                continue
            if child.func.attr not in {"update_status", "complete_task", "fail_task"}:
                continue
            if not any(keyword.arg == "worker_id" for keyword in child.keywords):
                missing.append(f"{node.name}:{child.lineno}:{child.func.attr}")

    assert missing == []


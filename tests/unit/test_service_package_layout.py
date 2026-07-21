import ast
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[2] / "src" / "api" / "services"

EXPECTED_PACKAGES = {
    "knowledge": (
        "knowledge_graph_service",
        "kg_prompts",
        "kg_similarity",
    ),
    "tasks": (
        "task_manager",
        "task_dispatcher",
        "task_worker",
        "checkpoint_store",
    ),
    "quality": (
        "quality_action_service",
        "quality_report_service",
        "filler_detection_service",
        "foreshadow_tracker_service",
        "novel_context_service",
        "rewrite_loop_service",
    ),
    "content": (
        "novel_manager",
        "chapter_service",
        "character_service",
        "world_service",
        "volume_service",
        "outline_service",
        "outline_sync_service",
        "storyline_service",
        "story_bible_service",
        "blueprint_service",
        "conversation_service",
        "career_service",
        "inspiration_service",
        "chapter_analysis_service",
    ),
    "generation": (
        "novel_generator",
        "novel_generator_planning",
        "long_form_generation_helpers",
        "long_form_progress_service",
        "chapter_generation_utils",
        "chapter_persistence_service",
        "ai_generation_service",
        "pause_state_store",
        "progress_event_bus",
    ),
}

ROOT_MODULES = {
    "agent_journal_service.py",
    "book_import_service.py",
    "export_service.py",
    "reader_simulation_service.py",
}


@pytest.mark.parametrize(
    ("package", "modules"),
    EXPECTED_PACKAGES.items(),
    ids=list(EXPECTED_PACKAGES),
)
def test_service_modules_are_grouped(package: str, modules: tuple[str, ...]) -> None:
    package_dir = SERVICES_DIR / package
    init_file = package_dir / "__init__.py"

    assert init_file.is_file()
    assert ast.get_docstring(ast.parse(init_file.read_text(encoding="utf-8")))

    actual_python_files = {path.name for path in package_dir.glob("*.py")}
    expected_python_files = {f"{module}.py" for module in modules} | {"__init__.py"}
    assert actual_python_files == expected_python_files

    actual_nested_dirs = {
        path.name
        for path in package_dir.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert actual_nested_dirs == set()

    for module in modules:
        assert (package_dir / f"{module}.py").is_file()
        assert not (SERVICES_DIR / f"{module}.py").exists()


def test_service_root_is_structurally_closed() -> None:
    actual_python_files = {path.name for path in SERVICES_DIR.glob("*.py")}
    actual_package_dirs = {
        path.name
        for path in SERVICES_DIR.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert actual_python_files == ROOT_MODULES | {"__init__.py"}
    assert actual_package_dirs == set(EXPECTED_PACKAGES)
    assert (SERVICES_DIR / "README.md").is_file()


def test_service_public_exports_are_stable() -> None:
    tree = ast.parse((SERVICES_DIR / "__init__.py").read_text(encoding="utf-8"))
    all_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    )

    assert set(ast.literal_eval(all_assignment.value)) == {
        "TaskManager",
        "get_task_manager",
        "generate_novel_background",
    }

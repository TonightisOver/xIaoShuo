"""服务目录结构约束：断言关键目录/分包存在，且 archive/ 不被 src/ 引用。"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"


def test_routes_split_by_resource():
    """routes 按资源拆分，不再是单文件。"""
    routes_dir = SRC / "api" / "routes"
    assert routes_dir.is_dir(), "src/api/routes/ 应为目录"
    py_files = [p.name for p in routes_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(py_files) >= 3, f"routes 下应至少有 3 个资源模块，实际 {py_files}"


def test_core_subpackages_exist():
    """core 已有合理分包。"""
    for sub in ["database.py", "config.py", "security", "langgraph", "llm", "quality", "agents"]:
        assert (SRC / "core" / sub).exists(), f"src/core/{sub} 应存在"


def test_services_subpackages_exist():
    """api/services 已按职责分包。"""
    for sub in ["content", "generation", "knowledge", "quality", "tasks"]:
        assert (SRC / "api" / "services" / sub).is_dir(), f"src/api/services/{sub}/ 应为目录"


def test_archive_not_imported_by_src():
    """archive/ 仅供归档，src/ 内不应 import 它。"""
    if not (REPO_ROOT / "archive").is_dir():
        return  # 无 archive 目录则跳过
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "from archive" not in text and "import archive" not in text, (
            f"{py.relative_to(REPO_ROOT)} 不应 import archive/"
        )

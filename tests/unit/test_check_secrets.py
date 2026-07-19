from pathlib import Path

from scripts.check_secrets import find_secret_candidates


def test_detects_provider_key(tmp_path: Path) -> None:
    sample = tmp_path / "leak.md"
    sample.write_text("DEEPSEEK_API_KEY=sk-" + "a" * 32, encoding="utf-8")

    assert find_secret_candidates(tmp_path) == [sample]


def test_allows_documented_placeholders(tmp_path: Path) -> None:
    sample = tmp_path / "example.md"
    sample.write_text("DEEPSEEK_API_KEY=sk-your-key", encoding="utf-8")

    assert find_secret_candidates(tmp_path) == []


def test_ignores_local_runtime_secret_files(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("API_KEY=sk-" + "b" * 32, encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("API_KEY=sk-" + "c" * 32, encoding="utf-8")

    assert find_secret_candidates(tmp_path) == []

import pytest

from pytest_codex.snapshot import snapshot


def test_generated_uv_cache_never_enters_input_or_output_snapshot(tmp_path):
    (tmp_path / "pyproject.toml").write_text("project", encoding="utf-8")
    cache = tmp_path / ".uv-cache" / "sdists"
    cache.mkdir(parents=True)
    (cache / ".git").write_text("cache metadata", encoding="utf-8")
    assert list(snapshot(tmp_path)) == ["pyproject.toml"]


def test_unreadable_input_is_an_error_not_silently_omitted(tmp_path, monkeypatch):
    path = tmp_path / "input.txt"
    path.write_text("important", encoding="utf-8")

    def denied(self):
        raise PermissionError("cannot read input")

    monkeypatch.setattr(type(path), "read_bytes", denied)
    with pytest.raises(PermissionError, match="cannot read"):
        snapshot(tmp_path)

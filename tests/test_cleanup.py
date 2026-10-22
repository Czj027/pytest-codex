import stat

import pytest

from pytest_codex.cleanup import remove_tree


def test_cleanup_removes_readonly_git_style_files(tmp_path):
    root = tmp_path / "owned"
    root.mkdir()
    file = root / "readonly"
    file.write_text("data", encoding="utf-8")
    file.chmod(stat.S_IREAD)
    remove_tree(root, tmp_path)
    assert not root.exists()


def test_cleanup_refuses_parent_or_other_directory(tmp_path):
    with pytest.raises(ValueError):
        remove_tree(tmp_path, tmp_path)
    with pytest.raises(ValueError):
        remove_tree(tmp_path.parent, tmp_path)

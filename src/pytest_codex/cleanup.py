"""Remove only an explicitly owned temporary tree, including read-only Git files."""

import os
import shutil
import stat
from pathlib import Path


def remove_tree(path: Path, owner: Path) -> None:
    path, owner = Path(path).absolute(), Path(owner).resolve()
    resolved = path.resolve()
    if resolved == owner or not resolved.is_relative_to(owner) or path.is_symlink():
        raise ValueError("cleanup target must be an owned subdirectory")

    def readonly(function, name, error):
        if not isinstance(error[1], PermissionError):
            raise error[1]
        os.chmod(name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(name)

    shutil.rmtree(path, onerror=readonly)

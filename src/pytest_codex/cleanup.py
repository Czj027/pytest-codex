"""Remove only an explicitly owned temporary tree, including read-only Git files."""

import os
import shutil
import stat
from pathlib import Path

from .paths import native_path


def remove_tree(path: Path, owner: Path) -> None:
    path, owner = Path(path).absolute(), Path(owner).resolve()
    resolved = path.resolve()
    if resolved == owner or not resolved.is_relative_to(owner) or path.is_symlink():
        raise ValueError("cleanup target must be an owned subdirectory")

    def readonly(function, name, error):
        # Git maintenance may remove a scanned lock before older rmtree versions
        # unlink it. Missing descendants already satisfy cleanup; a missing root
        # still indicates an invalid target and must be reported.
        if isinstance(error[1], FileNotFoundError) and Path(name) != native_path(resolved):
            return
        if not isinstance(error[1], PermissionError):
            raise error[1]
        os.chmod(name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(name)

    # Only extend after ownership checks. Git object paths can exceed MAX_PATH.
    shutil.rmtree(native_path(resolved), onerror=readonly)

"""Best-effort discovery of the explicitly requested desktop-bundled CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_desktop_binary() -> str:
    """Find a known bundle, without invoking Codex or reading credentials."""
    explicit = os.environ.get("PYTEST_CODEX_DESKTOP_BIN")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError("PYTEST_CODEX_DESKTOP_BIN does not identify a file")
        return str(path)
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            Path.home() / "Applications/Codex.app/Contents/Resources/codex",
            Path("/Applications/Codex.app/Contents/Resources/codex"),
        ]
    elif sys.platform == "win32":
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if powershell:
            try:
                result = subprocess.run(
                    [
                        powershell,
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "@(Get-AppxPackage -Name OpenAI.Codex | Select-Object -ExpandProperty InstallLocation) | ConvertTo-Json -Compress",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    stdin=subprocess.DEVNULL,
                    check=False,
                )
                locations = (
                    json.loads(result.stdout.lstrip("\ufeff")) if result.returncode == 0 else []
                )
                if isinstance(locations, str):
                    locations = [locations]
                if isinstance(locations, list):
                    candidates = [
                        Path(p) / "app/resources/codex.exe" for p in locations if isinstance(p, str)
                    ]
            except (OSError, ValueError, subprocess.TimeoutExpired):
                candidates = []
    found = [p.resolve() for p in candidates if p.is_file()]
    if len(found) == 1:
        return str(found[0])
    if len(found) > 1:
        raise FileNotFoundError(
            "Multiple Codex desktop engines found; select --codex-bin explicitly"
        )
    raise FileNotFoundError(
        "Codex Desktop engine not found. Set PYTEST_CODEX_DESKTOP_BIN or use --codex-bin with an explicit executable path."
    )

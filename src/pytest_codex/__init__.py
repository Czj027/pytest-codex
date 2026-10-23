"""pytest-codex: assert on actual Codex behavior, live or offline."""

from .run import Run

__all__ = ["Run", "from_desktop_session"]
__version__ = "0.4.0"


def from_desktop_session(path, *, turn_id=None):
    """Import a selected desktop observation without executing Codex."""
    from .desktop import from_desktop_session as load

    return load(path, turn_id=turn_id)

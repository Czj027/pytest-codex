import pytest

from pytest_codex.events import build_items, parse_jsonl, unwrap_shell


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            '"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "uv add requests"',
            "uv add requests",
        ),
        ("powershell -NoProfile -Command 'echo hello'", "echo hello"),
        ("bash -lc 'echo hello'", "echo hello"),
        ("/bin/sh -c 'echo hello'", "echo hello"),
        ("cmd.exe /c echo hello", "echo hello"),
        ("uv add requests", "uv add requests"),
    ],
)
def test_shell_unwrap(raw, expected):
    assert unwrap_shell(raw) == expected


def test_parser_handles_noise_unknown_items_and_updates():
    events = parse_jsonl(
        'noise\n{broken\n\ufeff{"type":"item.started","item":{"id":"x","type":"new_type"}}\n{"type":"item.completed","item":{"id":"x","type":"new_type","extra":42}}'
    )
    assert len(events) == 2
    items = build_items(events)
    assert len(items) == 1 and items[0].raw["extra"] == 42

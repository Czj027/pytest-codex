"""pytest integration. No model is called unless live/record/auto is selected."""

from __future__ import annotations

import hashlib
import inspect
import math
import os
import re
import uuid
from pathlib import Path

import pytest

from .cassette import cassette_key, load_cassette, save_cassette
from .cleanup import remove_tree
from .runner import cli_version, execute
from .sandbox import make_sandbox
from .snapshot import snapshot


def pytest_addoption(parser):
    group = parser.getgroup("codex", "Codex behavior tests")
    group.addoption(
        "--codex-mode",
        choices=["replay", "record", "live", "auto"],
        default="replay",
        help="replay (default, offline), record, live, or auto (record missing only)",
    )
    group.addoption("--codex-record", action="store_true", help="alias for --codex-mode=record")
    group.addoption("--codex-live", action="store_true", help="alias for --codex-mode=live")
    group.addoption("--codex-bin", default="codex", help="Codex CLI executable")
    group.addoption("--codex-model", default=None, help="model passed to Codex")
    parser.addini("codex_project", "project directory relative to pytest root", default=".")
    parser.addini("codex_isolation", "none, config or full", default="full")
    parser.addini("codex_timeout", "timeout in seconds for each execution", default="300")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "codex(runs=1, pass_rate=1.0, project=None): repeat a synchronous test with a required passing fraction",
    )
    if config.getoption("codex_record") and config.getoption("codex_live"):
        raise pytest.UsageError("--codex-record and --codex-live cannot be combined")
    config._codex_rates = []


def marker_settings(item):
    marker = item.get_closest_marker("codex")
    options = marker.kwargs if marker else {}
    runs, rate = options.get("runs", 1), options.get("pass_rate", 1.0)
    if (
        marker
        and marker.args
        or set(options) - {"runs", "pass_rate", "project"}
        or isinstance(runs, bool)
        or not isinstance(runs, int)
        or runs < 1
        or isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(rate)
        or not 0 <= rate <= 1
    ):
        raise pytest.UsageError(
            f"invalid codex marker on {item.nodeid}: use runs>=1 and 0<=pass_rate<=1"
        )
    return runs, rate


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("codex"):
            marker_settings(item)
            if inspect.iscoroutinefunction(item.obj):
                raise pytest.UsageError("codex runs/pass_rate supports synchronous tests only")


def _slug(name):
    short = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip(".-")[:80] or "test"
    return short + "-" + hashlib.sha256(name.encode()).hexdigest()[:10]


class Codex:
    """Factory scoped to a pytest test; every exec receives a fresh project copy."""

    def __init__(self, request, temp_root):
        self.request = request
        self.temp_root = temp_root
        self.attempt = 1
        self._call = 0
        self._total_calls = 0
        self._version = None

    def exec(
        self,
        prompt: str,
        *,
        model=None,
        sandbox="workspace-write",
        config=None,
        files=None,
        project=None,
        timeout=None,
    ):
        settings = self.request.config
        marker = self.request.node.get_closest_marker("codex")
        selected = (
            project if project is not None else (marker.kwargs.get("project") if marker else None)
        )
        selected = selected if selected is not None else settings.getini("codex_project")
        source = Path(selected)
        if not source.is_absolute():
            source = settings.rootpath / source
        self._call += 1
        self._total_calls += 1
        target = self.temp_root / f"run-{self._total_calls}"
        root = make_sandbox(source, target, files)
        model = model if model is not None else settings.getoption("codex_model")
        isolation = settings.getini("codex_isolation")
        key = cassette_key(prompt, model, config or {}, sandbox, snapshot(root), isolation)
        node = self.request.node
        module = Path(str(node.path)).relative_to(settings.rootpath).as_posix()
        test_name = node.nodeid.split("::", 1)[-1]
        runs, _ = marker_settings(node)
        suffix = f"-attempt-{self.attempt}" if runs > 1 else ""
        suffix += f"-call-{self._call}"
        path = (
            Path(str(node.path)).parent
            / "cassettes"
            / _slug(module)
            / (_slug(test_name) + suffix + ".json")
        )
        mode = settings.getoption("codex_mode")
        if settings.getoption("codex_record"):
            mode = "record"
        elif settings.getoption("codex_live"):
            mode = "live"
        if mode == "replay" or mode == "auto" and path.exists():
            return load_cassette(path, key, root)
        binary = settings.getoption("codex_bin")
        if mode in {"record", "auto"} and self._version is None:
            self._version = cli_version(binary)
        run = execute(
            prompt,
            root,
            codex_bin=binary,
            model=model,
            sandbox=sandbox,
            config=config,
            isolation=isolation,
            timeout=float(settings.getini("codex_timeout")) if timeout is None else timeout,
        )
        if mode in {"record", "auto"}:
            save_cassette(path, key, run, self._version)
        return run


@pytest.fixture
def codex(request, tmp_path):
    settings = request.config
    live_mode = (
        settings.getoption("codex_mode") != "replay"
        or settings.getoption("codex_record")
        or settings.getoption("codex_live")
    )
    if os.name == "nt" and live_mode:
        # Python/pytest temp parents may have a user-only DACL which denies
        # traversal to the Codex sandbox account. Use an ordinary cache directory.
        base = Path.home() / ".cache" / "pytest-codex" / "projects"
        base.mkdir(parents=True, exist_ok=True)
        root = base / uuid.uuid4().hex
        root.mkdir()
        try:
            yield Codex(request, root)
        finally:
            remove_tree(root, base)
    else:
        yield Codex(request, tmp_path)


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if pyfuncitem.get_closest_marker("codex") is None:
        return None
    runs, required = marker_settings(pyfuncitem)
    arguments = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    factory = pyfuncitem.funcargs.get("codex")
    failures = []
    for attempt in range(1, runs + 1):
        if factory is not None:
            factory.attempt = attempt
            factory._call = 0
        try:
            result = pyfuncitem.obj(**arguments)
            if result is not None:
                raise TypeError("codex-marked tests must return None")
        except (AssertionError, pytest.fail.Exception) as exc:
            failures.append(f"attempt {attempt}: {exc}")
    passed = runs - len(failures)
    summary = f"{pyfuncitem.nodeid}: {passed}/{runs} ({passed / runs:.1%}), required {required:.1%}"
    pyfuncitem.config._codex_rates.append(summary)
    pyfuncitem.user_properties.extend([("codex_passed", passed), ("codex_runs", runs)])
    if passed / runs < required:
        pytest.fail(summary + "\n" + "\n".join(failures), pytrace=False)
    return True


def pytest_terminal_summary(terminalreporter):
    summaries = getattr(terminalreporter.config, "_codex_rates", [])
    if summaries:
        terminalreporter.section(
            "Codex pass rates (fixtures shared; each exec uses a fresh sandbox)"
        )
        for summary in summaries:
            terminalreporter.write_line(summary)

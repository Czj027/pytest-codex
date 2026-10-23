"""pytest integration. No model is called unless live/record/auto is selected."""

from __future__ import annotations

import hashlib
import inspect
import math
import os
import re
import time
import uuid
from pathlib import Path

import pytest

from . import results
from .cassette import cassette_key, check_cli_version, load_cassette, save_cassette
from .cleanup import remove_tree
from .desktop_engine import find_desktop_binary
from .paths import native_path
from .runner import cli_version, execute
from .sandbox import make_sandbox
from .snapshot import snapshot, tree_hash


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
    group.addoption(
        "--codex-desktop",
        action="store_true",
        help="explicitly use the desktop-bundled engine for live/record (replay stays offline)",
    )
    group.addoption("--codex-model", default=None, help="model passed to Codex")
    group.addoption("--codex-recording-set", default=None, help="isolated named cassette set")
    group.addoption("--codex-results", default=None, help="write new per-attempt JSON results")
    group.addoption(
        "--codex-cli-version", default=None, help="expected recording CLI version (offline check)"
    )
    group.addoption(
        "--codex-check-cli",
        action="store_true",
        help="check recordings against installed codex --version; requires an explicit model",
    )
    parser.addini("codex_project", "project directory relative to pytest root", default=".")
    parser.addini("codex_isolation", "none, config or full", default="full")
    parser.addini("codex_timeout", "timeout in seconds for each execution", default="300")
    parser.addini("codex_cli_version", "expected CLI version for recording/replay", default="")
    parser.addini("codex_model", "explicit model, overridden by --codex-model or exec", default="")
    parser.addini(
        "codex_grader_files",
        "additional trusted acceptance files relative to pytest root",
        type="linelist",
        default=[],
    )


def pytest_configure(config):
    results.configure(config)
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
        if item.config._codex_result_path is not None and "codex" in item.fixturenames:
            item._codex_grader_hash = results.grader_hash(item)
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
        self._result_calls = []

    def from_desktop_session(self, path, *, turn_id=None):
        """Read one explicit historical session; never executes a model or restores files."""
        from .desktop import from_desktop_session

        if self.request.config._codex_result_path is not None:
            raise pytest.UsageError(
                "Desktop observations cannot enter --codex-results fresh comparisons; export an observation separately"
            )
        return from_desktop_session(path, turn_id=turn_id)

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
        model = (
            model
            if model is not None
            else (settings.getoption("codex_model") or settings.getini("codex_model") or None)
        )
        expected_version = (
            settings.getoption("codex_cli_version") or settings.getini("codex_cli_version") or None
        )
        check_local = settings.getoption("codex_check_cli")
        if (expected_version or check_local) and not model:
            raise pytest.UsageError(
                "version-checked runs require an explicit model: use --codex-model, "
                "codex_model, or exec(model=...) so default model changes cannot go unnoticed"
            )
        binary = settings.getoption("codex_bin")
        desktop_selected = settings.getoption("codex_desktop")
        if desktop_selected and binary != "codex":
            raise pytest.UsageError("Choose either --codex-desktop or --codex-bin")
        if desktop_selected and check_local:
            binary = find_desktop_binary()
        if check_local:
            if self._version is None:
                self._version = cli_version(binary)
            if expected_version is not None:
                check_cli_version(self._version, expected_version)
            expected_version = self._version
        isolation = settings.getini("codex_isolation")
        inputs = snapshot(root)
        key = cassette_key(prompt, model, config or {}, sandbox, inputs, isolation)
        node = self.request.node
        module = Path(str(node.path)).relative_to(settings.rootpath).as_posix()
        test_name = node.nodeid.split("::", 1)[-1]
        runs, _ = marker_settings(node)
        suffix = f"-attempt-{self.attempt}" if runs > 1 else ""
        suffix += f"-call-{self._call}"
        directory = Path(str(node.path)).parent / "cassettes"
        selected_set = settings.getoption("codex_recording_set")
        if selected_set is not None:
            directory = directory / selected_set
        path = directory / _slug(module) / (_slug(test_name) + suffix + ".json")
        mode = settings.getoption("codex_mode")
        if settings.getoption("codex_record"):
            mode = "record"
        elif settings.getoption("codex_live"):
            mode = "live"
        if selected_set is not None and mode == "record" and native_path(path).exists():
            raise FileExistsError(
                "Named recording already exists; choose a new --codex-recording-set"
            )
        started = time.perf_counter()
        if mode == "replay" or mode == "auto" and native_path(path).exists():
            run = load_cassette(path, key, root, expected_version=expected_version)
        else:
            if desktop_selected and not check_local:
                binary = find_desktop_binary()
            if (
                mode in {"record", "auto"} or expected_version or settings._codex_result_path
            ) and self._version is None:
                self._version = cli_version(binary)
            if expected_version is not None:
                check_cli_version(self._version, expected_version)
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
                save_cassette(path, key, run, self._version, overwrite=selected_set is None)
        if settings._codex_result_path is not None:
            self._result_calls.append(
                {
                    "input_hash": tree_hash(inputs),
                    "prompt_hash": results.digest(prompt),
                    "config_hash": results.digest(config or {}),
                    "sandbox": sandbox,
                    "isolation": isolation,
                    "model": model,
                    "cli_version": self._version or expected_version,
                    "replayed": run.replayed,
                    "succeeded": run.succeeded,
                    "execution_error": results.execution_error(run),
                    "duration_seconds": round(time.perf_counter() - started, 6),
                    "timeout": float(settings.getini("codex_timeout"))
                    if timeout is None
                    else timeout,
                    "behavior": {
                        "command_exits": [command.exit_code for command in run.commands],
                        "changed_files": run.changed_files,
                        "mcp_tools": [
                            f"{call.server}.{call.tool}:{call.status}" for call in run.mcp_calls
                        ],
                    },
                    "usage": {
                        "input_tokens": run.usage.input_tokens,
                        "cached_input_tokens": run.usage.cached_input_tokens,
                        "output_tokens": run.usage.output_tokens,
                    },
                }
            )
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
            factory._result_calls = []
        try:
            result = pyfuncitem.obj(**arguments)
            if result is not None:
                raise TypeError("codex-marked tests must return None")
        except pytest.xfail.Exception:
            results.record_case(pyfuncitem, factory, "skipped", "XFailed")
            raise
        except (AssertionError, pytest.fail.Exception) as exc:
            failures.append(f"attempt {attempt}: {exc}")
            results.record_case(pyfuncitem, factory, "failed", type(exc).__name__)
        except pytest.skip.Exception:
            results.record_case(pyfuncitem, factory, "skipped", "Skipped")
            raise
        except Exception as exc:
            results.record_case(pyfuncitem, factory, "error", type(exc).__name__)
            raise
        else:
            results.record_case(pyfuncitem, factory, "passed")
    passed = runs - len(failures)
    summary = f"{pyfuncitem.nodeid}: {passed}/{runs} ({passed / runs:.1%}), required {required:.1%}"
    pyfuncitem.config._codex_rates.append(summary)
    pyfuncitem.user_properties.extend([("codex_passed", passed), ("codex_runs", runs)])
    if passed / runs < required:
        pytest.fail(summary + "\n" + "\n".join(failures), pytrace=False)
    return True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if item.config._codex_result_path is None or "codex" not in item.fixturenames:
        return
    factory = item.funcargs.get("codex")
    error_type = call.excinfo.type.__name__ if call.excinfo is not None else None
    if report.when == "setup" and (report.failed or report.skipped):
        results.record_case(
            item, factory, "skipped" if report.skipped else "error", error_type, "setup"
        )
    elif report.when == "call" and not getattr(item, "_codex_exported", False):
        status = "passed" if report.passed else "skipped" if report.skipped else "failed"
        if report.failed and error_type not in {"AssertionError", "Failed"}:
            status = "error"
        results.record_case(item, factory, status, error_type)
    elif report.when == "teardown" and report.failed:
        for row in item.config._codex_results["attempts"]:
            if row["case"] == results.case_id(item):
                row.update(status="error", phase="teardown", error_type=error_type)


def pytest_sessionfinish(session):
    results.finish(session.config)


def pytest_terminal_summary(terminalreporter):
    summaries = getattr(terminalreporter.config, "_codex_rates", [])
    if summaries:
        terminalreporter.section(
            "Codex pass rates (fixtures shared; each exec uses a fresh sandbox)"
        )
        for summary in summaries:
            terminalreporter.write_line(summary)

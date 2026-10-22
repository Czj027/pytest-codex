# Changelog

## 0.1.0

- Filter command assertions by exit status with `run.ran(pattern, ok=True/False)`.

- Add the automatically discovered `codex` pytest fixture and fresh Git project copies.
- Add command, file-change, message, MCP-call and token queries on `Run`.
- Add explicit record/live modes and offline replay by default, with input fingerprint checks.
- Restore binary files and deletions during replay; reject unsafe paths and symlinks.
- Add synchronous repeated tests with required pass rates and separate attempt recordings.
- Isolate Codex configuration, handle stdin, and terminate processes on timeout or interruption.
- Add bilingual documentation, a real recorded conventions example and an offline CI matrix.

## 0.0.1 — 2026-10-22

- Publish the event parser and file-snapshot core preview.
- This version did not register a pytest plugin.

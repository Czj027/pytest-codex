# Changelog

## 0.3.0 — candidate

- Add immutable named recording sets and opt-in per-attempt JSON results.
- Compare matched fresh model or CLI observations with separate task failures,
  execution/grader errors and skips; reject replay and changed task contracts.
- Include five independently checked tasks and all 30 reviewed pilot recordings,
  including unsuccessful attempts and disclosed Windows shell startup errors.
- Keep runtime dependencies unchanged and ordinary tests fully offline.

## 0.2.0 — 2026-10-22

- Add offline CLI version pins and an opt-in installed-version check; require an
  explicit model for version-checked runs and validate before replay writes or model calls.
- Honor Git-ignored untracked inputs when copying a source repository; fail closed
  when its ignore rules cannot be read.
- Resolve relative CLI launchers before changing the execution directory.
- Support long recording filenames, Git object paths and owned-tree cleanup on Windows.
- Dogfood this project's AGENTS.md across two models and repeated fresh attempts.
- Include reviewed real MCP and Skill recordings, all replayable offline.
- Add a daily latest-CLI protocol check against a local fixture with no model calls,
  plus an opt-in live CI template.
- Add a reproducible failure animation, bilingual worked articles and an integration guide.

## 0.1.0 — 2026-10-22

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

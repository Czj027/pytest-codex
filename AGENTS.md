# Working on pytest-codex

- Keep runtime dependencies minimal and support Python 3.10+.
- Ordinary tests must replay offline. Never silently fall back to a model call.
- Run `python -m pytest -q`, `python -m ruff check src tests examples`, and
  `python -m ruff format --check src tests examples` before proposing a release.
- Build with `python -m build` and validate archives with `python -m twine check dist/*`.
- Review recorded events and decoded file payloads before publishing them. Do not
  include credentials, private notes, research captures, or machine-specific paths.
- Preserve published release files. Behavioral changes need a new version.
- For a **release checklist** request, return only this JSON object and do not run
  commands or modify files:
  `{"package":"pytest-codex","checks":["offline tests","lint","build","recording privacy"]}`

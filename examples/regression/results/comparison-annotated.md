# Fresh Codex task comparison

Factor: **model**.

Baseline: gpt-6-luna / CLI codex-cli 0.163.0.
Candidate: gpt-6.1-sol / CLI codex-cli 0.163.0.

| Task | Baseline | Candidate | Observation |
|---|---|---|---|
| tasks.py::test_dependency_declaration | 1/1 (100.0%); errors=2, skipped=0 | 3/3 (100.0%); errors=0, skipped=0 | inconclusive |
| tasks.py::test_fix_average | 1/2 (50.0%); errors=1, skipped=0 | 2/2 (100.0%); errors=1, skipped=0 | inconclusive |
| tasks.py::test_mcp_result | 3/3 (100.0%); errors=0, skipped=0 | 3/3 (100.0%); errors=0, skipped=0 | unchanged |
| tasks.py::test_preserve_legacy | 1/2 (50.0%); errors=1, skipped=0 | 3/3 (100.0%); errors=0, skipped=0 | inconclusive |
| tasks.py::test_skill_artifact | 2/2 (100.0%); errors=1, skipped=0 | 3/3 (100.0%); errors=0, skipped=0 | inconclusive |

Each score uses completed attempts only; execution/grader errors and skips are separate.
Any case with errors/skips is inconclusive rather than an apparent model improvement.
This is a small sample of observed outcomes, not a model ranking or statistical proof of regression.
A model alias may change server-side; these are requested model IDs, not verified weight snapshots.
Environment hashes cover recorded inputs/configuration, not all inherited machine state.

## Execution totals

| Cohort | Input (includes cached) | Cached subset | Output | Seconds |
|---|---:|---:|---:|---:|
| baseline | 745179 | 670720 | 3394 | 285.37 |
| candidate | 703528 | 633600 | 3760 | 373.05 |

Times include invocation/recording overhead. Token counters are not an API invoice.

## Task acceptance and execution health

Acceptance includes recovered/contaminated turns; it is not the clean comparison score above.
Older reports without task_status retain their conservative status (no recovered result is invented).

| Task | Cohort | Accepted | Rejected | Grader/setup error | Skipped | Execution-error turns |
|---|---|---:|---:|---:|---:|---:|
| tasks.py::test_dependency_declaration | baseline | 2 | 1 | 0 | 0 | 2 |
| tasks.py::test_dependency_declaration | candidate | 3 | 0 | 0 | 0 | 0 |
| tasks.py::test_fix_average | baseline | 1 | 2 | 0 | 0 | 1 |
| tasks.py::test_fix_average | candidate | 3 | 0 | 0 | 0 | 1 |
| tasks.py::test_mcp_result | baseline | 3 | 0 | 0 | 0 | 0 |
| tasks.py::test_mcp_result | candidate | 3 | 0 | 0 | 0 | 0 |
| tasks.py::test_preserve_legacy | baseline | 2 | 1 | 0 | 0 | 1 |
| tasks.py::test_preserve_legacy | candidate | 3 | 0 | 0 | 0 | 0 |
| tasks.py::test_skill_artifact | baseline | 3 | 0 | 0 | 0 | 1 |
| tasks.py::test_skill_artifact | candidate | 3 | 0 | 0 | 0 | 0 |

## Per-attempt observations

### tasks.py::test_dependency_declaration
- Attempt 1: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 2: error → passed (error types: ShellStartupError / None).
  Task acceptance: failed → passed; execution errors: ['ShellStartupError'] / [].
- Attempt 3: error → passed (error types: ShellStartupError / None).
  Task acceptance: passed → passed; execution errors: ['ShellStartupError'] / [].

### tasks.py::test_fix_average
- Attempt 1: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 2: error → passed (error types: ShellStartupError / None).
  Task acceptance: failed → passed; execution errors: ['ShellStartupError'] / [].
- Attempt 3: failed → error (error types: AssertionError / ShellStartupError).
  Task acceptance: failed → passed; execution errors: [] / ['ShellStartupError'].

### tasks.py::test_mcp_result
- Attempt 1: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 2: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 3: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].

### tasks.py::test_preserve_legacy
- Attempt 1: error → passed (error types: ShellStartupError / None).
  Task acceptance: passed → passed; execution errors: ['ShellStartupError'] / [].
- Attempt 2: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 3: failed → passed (error types: AssertionError / None).
  Task acceptance: failed → passed; execution errors: [] / [].

### tasks.py::test_skill_artifact
- Attempt 1: error → passed (error types: ShellStartupError / None).
  Task acceptance: passed → passed; execution errors: ['ShellStartupError'] / [].
- Attempt 2: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].
- Attempt 3: passed → passed (error types: None / None).
  Task acceptance: passed → passed; execution errors: [] / [].


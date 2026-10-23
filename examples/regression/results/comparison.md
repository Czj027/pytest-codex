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

## Per-attempt observations

### tasks.py::test_dependency_declaration
- Attempt 1: passed → passed (error types: None / None).
- Attempt 2: error → passed (error types: ShellStartupError / None).
- Attempt 3: error → passed (error types: ShellStartupError / None).

### tasks.py::test_fix_average
- Attempt 1: passed → passed (error types: None / None).
- Attempt 2: error → passed (error types: ShellStartupError / None).
- Attempt 3: failed → error (error types: AssertionError / ShellStartupError).

### tasks.py::test_mcp_result
- Attempt 1: passed → passed (error types: None / None).
- Attempt 2: passed → passed (error types: None / None).
- Attempt 3: passed → passed (error types: None / None).

### tasks.py::test_preserve_legacy
- Attempt 1: error → passed (error types: ShellStartupError / None).
- Attempt 2: passed → passed (error types: None / None).
- Attempt 3: failed → passed (error types: AssertionError / None).

### tasks.py::test_skill_artifact
- Attempt 1: error → passed (error types: ShellStartupError / None).
- Attempt 2: passed → passed (error types: None / None).
- Attempt 3: passed → passed (error types: None / None).


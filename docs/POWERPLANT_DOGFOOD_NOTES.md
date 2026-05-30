# Powerplant Dogfood Notes — Pipeline Simulator

**Date:** 2026-05-30
**Branch:** `dogfood/powerplant-sim-harness-readiness`
**Powerplant version:** 0.1.0 (local — `~/Downloads/grok/claude_powerplant`)
**Repo:** Universal Extrapolative Engine — multi-tier simulator / LLM test bench
**Goal:** Harness readiness only. No new simulator features.

---

## What worked

- `powerplant init --stack python --yes --force` generated syntactically valid POLICY.yaml and VERIFY.yaml immediately.
- `powerplant verify` sandbox isolation worked: clean subprocess env, no credentials passed, no original project mounted, `denyIfPresentAfterCopy` enforced.
- Syntax-check (`python3 -m compileall -q .`) passes reliably once `.venv/__pycache__` are excluded from POLICY.yaml includePaths.
- Smoke-tests (`python3 -m pytest tests/ -q`) passes once `seeds/` and `hypotheses/` fixture paths are added to includePaths.
- PATH inheritance allowed `.venv/bin/python3` (with pytest, torch, etc.) to be found in the sandbox subprocess — no extra install step needed.
- 394/394 tests pass in sandbox.

---

## What was confusing

- `--force` flag needed even on an empty `.powerplant/` directory; the empty-dir check triggered before checking whether YAML files actually exist. Minor UX friction.
- `powerplant init` did not communicate that `.venv/`, `seeds/`, `hypotheses/`, or `docs/` paths would be absent from the sandbox. Users must discover missing paths by running `verify` and reading the JSON report.
- The generated VERIFY.yaml used `python3 -m pytest` (no `tests/` path) — would collect from everywhere including `scp/tolsv3/` which has its own test files and separate deps.

---

## CLI issues

- `powerplant --version` is not a recognized command (exits 1 with usage). No version flag available.
- Error message on empty `.powerplant/` dir says "already exists" which is misleading — the directory is empty, not "already initialized."

---

## Init/POLICY/VERIFY issues

### POLICY.yaml — generated shape too narrow for research repos

Generated includePaths omits non-Python fixture files that tests depend on:
- `seeds/*.yaml` — opened by `test_regression_main.py::test_load_seed_file_real_gaming`
- `hypotheses/*.yaml` — opened by `test_neural_arch.py::test_yaml_loads_neural_arch_type`

**Fix applied:** Added `seeds/**` and `hypotheses/*.yaml` to both includePaths and allowedReadPaths.

Generated excludePaths omits:
- `.venv/**` — venv is huge (~1GB); not in includePaths but should be explicitly excluded to avoid confusion
- `**/__pycache__/**`
- large binary/media files (`*.pdf`, `curriculum/**`, `*.skill`)
- `logs/**` (contains run artifacts, not source)

**Fix applied:** Added all of the above to excludePaths.

### VERIFY.yaml — `python3 -m pytest` without testpath

Generated command runs pytest with no path argument. `pyproject.toml` specifies `testpaths = ["tests"]` so this is fine locally, but `compileall` is safer and the scope is still implicit. Narrowed to `python3 -m pytest tests/ -q`.

### VERIFY.yaml — shell-substitution command rejected

Original attempt used `py_compile $(find ...)`. Powerplant's `splitCommand` splits on whitespace only — no shell, no `$()` expansion. The `$(find ...)` was passed as a literal argument to py_compile.

**Workaround:** Replaced with `python3 -m compileall -q .` — no shell substitution needed, stdlib-only, exits 1 on any compilation error.

**Powerplant issue to fix:** Either document this limitation clearly in VERIFY.yaml template/docs, or support `shell: true` for commands that need it.

### verificationProfile: null not accepted

`verificationProfile: null` in VERIFY.yaml produces: `'verificationProfile' must be a non-empty string when present`. The field must be omitted entirely (not set to null) when no profile is needed.

**Powerplant issue to fix:** Accept `null` as equivalent to omitting the key, or suppress the key from generated YAML.

---

## powerplant run issues

### Run ID: pp-run-1780146702497 — FAILED_TOOL_BUDGET_EXHAUSTED

The run hit the 30-tool safety cap before calling the finalization step.

Classification: `FAILED_TOOL_BUDGET_EXHAUSTED`, `finalizeAttempted: false`, `artifactsComplete: false`

Tool call breakdown:
- `project_list_files`: 1
- `project_read_file`: 19 (reading POLICY, VERIFY, pyproject.toml, requirements.txt, main.py, orchestrator.py, simulator.py, seeds/gaming.yaml, etc.)
- `project_run_check`: 2 (both passed: syntax-check and smoke-tests)
- `project_write_file`: 8 (6 successful writes, 2 rejected `.gitignore` writes)
- Total: 30 → cap hit

The agent was writing `simulator_errors.py`, `orchestrator_enhanced.py`, `tests/test_simulator_errors.py`, `tests/test_artifact_manager.py` when the budget ran out. No PATCH.diff was written. The sandbox workspace was discarded.

**Powerplant issue:** For multi-file research repos, 30 tool calls is insufficient to read project context + run checks + write new files + finalize. The agent spent ~20 calls on discovery (reads + check runs) leaving only ~10 for writes and finalization.

**Scope concern:** The agent's writes (`orchestrator_enhanced.py`) suggest it was adding new infrastructure rather than minimal harness fixes. This aligns with the task wording being too broad. A narrower run ("fix only the VERIFY/POLICY portability and the SyntaxWarning") would have fit within the budget.

### Review TUI with exhausted-budget runs

`powerplant review pp-run-1780146702497` shows `[FAIL]` with no diff, no checks, no risks — misleading if you don't also read RUN_CLASSIFICATION.json. The TUI should differentiate between "run completed with failing checks" and "run terminated before finalization."

**Powerplant issue to fix:** `review` should surface `terminationReason` when `artifactsComplete: false`. Current display gives no actionable signal.

### README.md and .gitignore not readable/writable

The agent attempted to read `README.md` (rejected — not in allowedReadPaths) and write `.gitignore` (rejected twice — not in allowedWritePaths). The `.gitignore` write was likely scope creep; the README.md read was legitimate (project overview).

**Fix applied:** Not adding README.md or .gitignore to allowedReadPaths/allowedWritePaths — those are outside the harness readiness scope.

**Powerplant issue:** README.md exclusion is expected, but the init generator should include it in allowedReadPaths for context, not allowedWritePaths.

---

## Approve flow issues

Not exercised — no PATCH.diff was produced (run terminated before finalization).

---

## Sandbox / subprocess issues

- PATH is inherited from parent process, so `.venv/bin/python3` is found in the sandbox. This is convenient but makes verification results environment-dependent: a CI machine without the venv activated would fail smoke-tests.
- **Recommendation:** VERIFY.yaml should document (or powerplant should enforce) that commands must work with `python3` resolved to the system Python OR that `pip install -e ".[dev]"` should be a setup check preceding test checks.

---

## Test flake issues

None observed. 394/394 passing consistently. CUDA warning present (old driver) but non-fatal.

---

## Safety / claim-integrity concerns

- No benchmark/performance claims added.
- No scoring formulas changed.
- No stochastic tests made deterministic.
- The SyntaxWarning fix in `scp/tolsv3/artifact_lens_project/artifact_lens_project/dashboard.py` is limited to raw-string LaTeX labels — rendering identical output, zero semantic change.
- POLICY/VERIFY changes are additive only (more paths included, stricter excludes).

---

## Deterministic blockers fixed in this session

| Blocker | Root cause | Fix |
|---------|-----------|-----|
| `powerplant verify` syntax-check FAIL | `splitCommand` doesn't evaluate shell `$()` | Replaced `py_compile $(find ...)` with `compileall -q .` |
| `powerplant verify` smoke-tests FAIL — seeds | `seeds/` not in POLICY includePaths | Added `seeds/**` |
| `powerplant verify` smoke-tests FAIL — hypotheses | `hypotheses/` not in POLICY includePaths | Added `hypotheses/*.yaml` |
| SyntaxWarning in `artifact_lens_project/dashboard.py` | `\k` invalid escape in LaTeX label strings | Changed to raw strings `r"$\kappa$"` |
| `verificationProfile: null` parse error | Powerplant rejects null, expects omission | Removed the key from VERIFY.yaml |

---

## Follow-up fixes for claude-powerplant

1. **`splitCommand` documentation**: Document in VERIFY.yaml template/generated comments that commands must be simple (no shell operators, no `$()`, no pipes). Current failure mode is silent/confusing.
2. **`verificationProfile: null` handling**: Accept null as equivalent to omitting the key.
3. **`--version` flag**: Add `powerplant --version` / `powerplant version` command.
4. **Empty-dir `--force` UX**: Don't require `--force` when `.powerplant/` exists but contains no YAML files.
5. **Init missing-fixture warning**: After generating POLICY.yaml, scan test files for `open(...)` calls pointing outside includePaths and warn.
6. **PATH dependency documentation**: Clarify that verify subprocess inherits parent PATH, making results environment-dependent for venv-based projects.
7. **Tool budget for research repos**: 30-call cap is exhausted by discovery alone on multi-file repos. Consider per-phase budgets (discovery / write / finalize) or a higher cap for `powerplant run`.
8. **`review` surfaces `terminationReason`**: When `artifactsComplete: false`, the review TUI should show the termination reason rather than a bare FAIL with no diff. Actionable message: "Run terminated before finalization (budget exhausted) — no patch produced."
9. **README.md in allowedReadPaths by default**: Init should include README.md (read-only) so agent has project context. Currently rejected at read time.

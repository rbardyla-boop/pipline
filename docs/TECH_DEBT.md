# Tech Debt Register — Universal Extrapolative Engine / UAF

**Audited:** 2026-05-27  
**Last fixed:** 2026-05-27 — TD-001, 002, 003, 004, 008, 009, 010, 012, 013 resolved (see statuses below)  
**Test suite state:** 217 tests passing (all green)  
**Branch:** main (up to date with origin)  
**Untracked:** `scp/` directory only

This document is the authoritative tech debt register. Findings are permanent entries — do not delete. Mark resolved items with ✅ and the commit SHA.

---

## CRITICAL

### TD-001 · `write_terminal_archive` method missing deduplication guard
**File:** [engine.py:160](../engine.py#L160)  
**Severity:** CRITICAL — data corruption  
**Status:** ✅ RESOLVED — method now delegates to module-level function (dedup guard inherited)

The module-level function `write_terminal_archive` (line 19) deduplicates via:

```python
if any(e["concept_hash"] == concept_hash for e in entries):
    return
```

The `NoveltySearchEngine.write_terminal_archive` method (line 160) is an identical copy but **omits this guard entirely**. It is not called anywhere in the current codebase, but being a public method it is a latent corruption vector: any caller will write duplicate terminal archive entries, breaking the hash-set invariant that `load_terminal_archive()` relies on for parent selection.

**Fix:** Add the dedup check before `entries.append(...)` at line 169, then either delete the method or make it delegate to the module-level function.

---

## HIGH

### TD-002 · Subprocess f-string code injection in `_write_audit_record`
**File:** [orchestrator.py:375–393](../orchestrator.py#L375)  
**Severity:** HIGH — security / code injection  
**Status:** ✅ RESOLVED — subprocess replaced with inline `jsonschema.validate()` using `_AUDIT_SCHEMA`; no f-string embedding

`_write_audit_record` embeds a Python dict directly into a subprocess `-c` argument via f-string:

```python
subprocess.run([sys.executable, "-c", f"""record = {json.dumps(audit_record)}..."""])
```

Fields `state['run_id']`, `state['domain']`, and `verdict` are included in `audit_record` without sanitization. A crafted `run_id` containing `"""` or a triple-quote sequence can break out of the Python literal and execute arbitrary code in the subprocess. The subprocess is launched with `capture_output=True` so the injection is non-interactive but still executes.

**Fix:** Pass `audit_record` as stdin JSON, validate in the subprocess via `json.load(sys.stdin)`, not via f-string embedding. Or replace the subprocess entirely with the `jsonschema` package (already in `requirements-security.txt`).

---

### TD-003 · `NoveltySearchEngine` instantiated on every node call — model loaded repeatedly
**File:** [orchestrator.py:96](../orchestrator.py#L96), [orchestrator.py:177](../orchestrator.py#L177)  
**Severity:** HIGH — performance regression  
**Status:** ✅ RESOLVED — module-level `_ENGINE` singleton + `_get_engine()` lazy initializer; model loaded once per process

`mutate_node` constructs `engine = NoveltySearchEngine()` on line 96 and `refine_node` constructs `engine_for_emb = NoveltySearchEngine()` on line 177. Each construction calls `SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))`, which loads a ~90 MB model from disk. In a 4-loop refinement run this loads the model 5+ times (1 × mutate + 1 × refine per loop), adding ~2–5 s latency per loop and re-allocating CPU/GPU memory unnecessarily.

**Fix:** Extract a module-level singleton `_ENGINE = None` or pass the engine through `PipelineState`. The `refine_node` usage is purely for `.embed()` — expose that via the engine already created in `mutate_node` by storing it in state, or add a standalone `embed(text)` helper that shares the loaded model.

---

### TD-004 · OBSERVE and PLAN states are dead code in `SimulationKernel`
**File:** [uaf/kernel/simulation.py:133–136](../uaf/kernel/simulation.py#L133)  
**Severity:** HIGH — undocumented behaviour / misleading state machine  
**Status:** ✅ RESOLVED — `OBSERVE` and `PLAN` removed from `SimulatorState` enum; dead assignment removed from loop; docstring updated

The class docstring promises:
```
INIT → OBSERVE → PLAN → EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE
```

The actual loop sets `sim_state = SimulatorState.OBSERVE` then immediately overwrites it with `sim_state = SimulatorState.EXECUTE` on the next line, skipping PLAN entirely. `CycleRecord.state` is written from `vresult.verdict` (a string), not `sim_state`, so the enum has zero effect on observable behaviour. Any future observer, test, or extension built on the documented state machine will silently break.

**Fix (choose one):**
- Implement the OBSERVE step (memory context refresh before execution) and PLAN step (planner pre-routing); or
- Remove `OBSERVE` and `PLAN` from `SimulatorState` and update the docstring to match the actual `EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE` cycle.

---

### TD-005 · No dependency version pins — no `pyproject.toml` or lockfile
**File:** [requirements.txt](../requirements.txt)  
**Severity:** HIGH — non-reproducible builds  
**Status:** ✅ RESOLVED — `pyproject.toml` created with compatible-release pins; `requirements.txt` updated with lower-bound versions

All 10 direct dependencies are unpinned:
```
sentence-transformers   # upstream breaks regularly
langgraph               # major API changes across minor versions
anthropic               # SDK shape changes affect typing
```

There is no `pyproject.toml`, no `setup.py`, and no `requirements.lock`. CI resolves to `latest` on every run, making builds non-deterministic.

**Fix:** Add `pyproject.toml` with `[project.dependencies]` using compatible-release pins (`anthropic>=0.25,<1.0`). Generate a `requirements.lock` via `pip-compile` (from `pip-tools`) or `uv lock`. Commit the lockfile.

**Minimum viable unblock:**
```
sentence-transformers>=2.7,<3.0
langgraph>=0.2,<0.3
anthropic>=0.25,<1.0
numpy>=1.26,<3.0
scikit-learn>=1.4,<2.0
```

---

## MEDIUM

### TD-006 · AgentGateway and LlamaFirewall are opt-in fallbacks, not hard dependencies
**Files:** [security/gateway/gateway_client.py:66–70](../security/gateway/gateway_client.py#L66), [security/firewall/llamafirewall_wrapper.py:187–194](../security/firewall/llamafirewall_wrapper.py#L187)  
**Severity:** MEDIUM — security layer bypassed in local dev  
**Status:** OPEN (by design in local dev; documented in `.env.example`)

`GATEWAY_URL` defaults to empty. When unset, both clients fall back silently to direct Anthropic/Tavily connections. The real API key from `.env` is passed directly to the SDK when the gateway is absent. The ARCHITECTURE.md claim that "AgentGateway proxies all outbound calls" is only true when running the Docker stack.

**Note:** This is intentional per `.env.example` ("Leave empty for direct API calls in local dev"). The gap is that ARCHITECTURE.md presents gateway-enforcement as unconditional. Document the gap explicitly in ARCHITECTURE.md or add a startup warning when `GATEWAY_URL` is unset in non-dev environments.

---

### TD-007 · Node governance non-enforcing by default (`STRICT_NODE_GOVERNANCE=false`)
**File:** [security/governance/node_identity.py:21](../security/governance/node_identity.py#L21)  
**Severity:** MEDIUM — documented invariant not enforced at runtime  
**Status:** OPEN

`STRICT_NODE_GOVERNANCE` defaults to `false`, so `assert_can_call_llm()` on the `signals` node logs an error rather than raising. The architectural guarantee that "signals node cannot make LLM calls" is advisory-only in local development.

**Fix:** Change default to `true` in `.env.example` or add a startup assertion that fails loudly when the signals node bypasses the check.

---

### TD-008 · `import numpy as np` inside refinement loop body
**File:** [orchestrator.py:182](../orchestrator.py#L182)  
**Severity:** MEDIUM — non-idiomatic, hides dependency  
**Status:** ✅ RESOLVED — moved to top-level imports

---

### TD-009 · Silent exception swallowing in `_write_audit_record`
**File:** [orchestrator.py:404](../orchestrator.py#L404)  
**Severity:** MEDIUM — audit failures invisible in logs  
**Status:** ✅ RESOLVED — `traceback.format_exc()` included in except handler; `sys` and `traceback` hoisted to top-level imports

The outer `except Exception as e` catch logs only `str(e)`, discarding the traceback. Any audit write failure (permission denied, serialisation error, subprocess crash) is reduced to a one-line message with no stack context.

**Fix:**
```python
import traceback
except Exception as e:
    print(f"[AUDIT] Failed to write audit record: {e}\n{traceback.format_exc()}", file=sys.stderr)
```

---

### TD-010 · `_PhoenixVerification` accesses private `_hash_embed` method of peer class
**File:** [uaf/research/trial_runner.py:155, 161](../uaf/research/trial_runner.py#L155)  
**Severity:** MEDIUM — couples verification layer to adapter internals  
**Status:** ✅ RESOLVED — replaced with module-level `_fingerprint(text)` using `hashlib.sha256`; no adapter dependency

`_PhoenixVerification.score()` constructs a throwaway `ParametricCognition(seed=0)` instance solely to call its private `_hash_embed(candidate)` method. This breaks clean-room isolation and couples the verification layer to a specific adapter's implementation detail.

**Fix:** Expose `embed(text: str) -> list[float]` as a method on the `CognitionEngine` interface, or use the existing `ConceptRater` embedding path already available via `self._rater`.

---

### TD-011 · Pervasive `print()` throughout — no structured logging
**Files:** `engine.py`, `orchestrator.py`, `uaf/kernel/simulation.py` (pervasive)  
**Severity:** MEDIUM — no log levels, no filtering, no timestamps  
**Status:** OPEN

All pipeline progress output uses bare `print()`. There is no ability to adjust verbosity, redirect by severity, or integrate with a logging aggregator.

**Fix:** Replace with `logging.getLogger(__name__)` calls. Configure a root handler in `main.py`. Use `logger.info` for progress, `logger.warning` for recoverable issues, `logger.error` for failures.

---

### TD-012 · Stale docstring in `SimulationKernel` contradicts `.env.example`
**File:** [uaf/kernel/simulation.py:8–10](../uaf/kernel/simulation.py#L8)  
**Severity:** MEDIUM — documentation drift  
**Status:** ✅ RESOLVED — docstring now accurately states UAF is default; actual state machine documented

---

## LOW

### TD-013 · `concept_preview` appends `"..."` unconditionally
**File:** [engine.py:33](../engine.py#L33), [engine.py:171](../engine.py#L171)  
**Severity:** LOW — misleading preview for short concepts  
**Status:** ✅ RESOLVED — conditional ellipsis applied

---

### TD-014 · CUDA driver mismatch warning on startup
**Severity:** LOW — cosmetic noise, not a code issue  
**Status:** OPEN (environment, not code)

PyTorch emits `UserWarning: CUDA initialization: NVIDIA driver version 12090 is too old` on every test run and import. The model runs on CPU so this has no functional impact, but the warning pollutes test output.

**Context:** Sentence-transformers uses PyTorch for CPU-only embedding. No CUDA features are used.
**Fix:** Either suppress via `PYTORCH_CUDA_ALLOC_CONF=0` or install a CPU-only PyTorch build (`torch --index-url https://download.pytorch.org/whl/cpu`).

---

### TD-015 · `scp/` directory untracked — relationship to pipeline unclear
**File:** `scp/` (git untracked)  
**Severity:** LOW — housekeeping  
**Status:** OPEN

`scp/` contains a Rust project with `SCP_SPEC.md`, `STATE_SEMANTICS.md`, `OPERATOR_DOCTRINE.md`, and wire-format definitions. Its relationship to the Python pipeline is undocumented.

**Fix:** Either add `scp/` to `.gitignore` if it is a separate project, or commit it with a note in ARCHITECTURE.md explaining its role (e.g., "SCP relay protocol — prospective integration point").

---

## Test Coverage Gaps

These modules have **zero test coverage** as of the audit. Listed by priority:

| Priority | Module | Lines | Why it Matters |
|----------|--------|-------|----------------|
| 1 | `security/firewall/llamafirewall_wrapper.py` | ~120 | Trust boundary for all LLM I/O — injection prevention |
| 2 | `security/gateway/gateway_client.py` | ~90 | Trust boundary for all search I/O |
| 3 | `security/governance/node_identity.py` | ~60 | Node isolation contracts |
| 4 | `orchestrator.py` nodes | ~270 | Legacy path with complex branching logic |
| 5 | `concept_rater.py` | ~180 | Core scoring; Phoenix rubric weights |
| 6 | `sandbox.py` | ~140 | Cultural sim — verdict logic |
| 7 | `signals.py` | ~100 | Deterministic signal layer |
| 8 | `zeitgeist.py` | ~80 | Context injection |
| 9 | `dashboard.py` | ~318 | CLI display — low risk, high surface area |
| 10 | `frontend/app.py` + `frontend/state.py` | ~540 | Streamlit UI — BackgroundRunner thread safety |

**Minimum next test sprint:** Add `tests/test_security.py` covering at least `scan_input`/`scan_output` with a known injection payload and a known clean payload.

---

## Build Steps to Continue

### Immediate (before next run)

1. **Rotate API credentials** — the `.env` file contains live `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`. Rotate both at [console.anthropic.com](https://console.anthropic.com) and [tavily.com](https://tavily.com). The `.gitignore` is correct — never committed — but local filesystem exposure is sufficient risk.

2. **Verify full test suite:**
   ```bash
   pytest tests/ -q
   # Expected: 217 passed
   ```

### ✅ Completed this session (2026-05-27)

| TD | Fix |
|----|-----|
| TD-001 | `write_terminal_archive` method delegates to module-level function (dedup guard) |
| TD-002 | Subprocess injection replaced with `jsonschema.validate()` |
| TD-003 | `NoveltySearchEngine` singleton — model loaded once per process |
| TD-004 | Dead `OBSERVE`/`PLAN` states removed from `SimulatorState` enum |
| TD-005 | `pyproject.toml` created; `requirements.txt` pinned |
| TD-008 | `numpy` import moved to top-level |
| TD-009 | `traceback.format_exc()` in audit exception handler |
| TD-010 | `_PhoenixVerification` uses `_fingerprint()` — no private adapter coupling |
| TD-012 | `simulation.py` docstring reflects actual state machine + UAF-as-default |
| TD-013 | Conditional ellipsis in `concept_preview` |

### Open: Infrastructure (next sprint)

- **TD-011** — Replace `print()` with `logging` throughout `engine.py` and `orchestrator.py`
- **TD-015** — Decide on `scp/` — add to `.gitignore` or commit with ARCHITECTURE.md note

### Open: Test Coverage (1–3 days)

Add `tests/test_security.py` — minimum viable: `scan_input`/`scan_output` with a known injection payload and a clean payload

Add `tests/test_orchestrator_nodes.py` — unit tests for `ingest_node`, `mutate_node`, `refine_node`, `route_after_refine` using a minimal mock `PipelineState`

Add `tests/test_concept_rater.py` — Phoenix rubric weights, `FRICTION_PATTERNS`/`ANTI_OPT_PATTERNS` regex

---

## Deferred / External Blockers

| Item | Status | Notes |
|------|--------|-------|
| `vercel-labs/deepsec` in ARCHITECTURE.md | Placeholder — repo unconfirmed | Do not integrate until confirmed live |
| LlamaFirewall PyPI package | Not yet stable; rule-based fallback active | See `requirements-security.txt` comment |
| CUDA driver 12090 | System-level, not code | Upgrade or use CPU-only PyTorch |

---

*Last updated: 2026-05-27 | Auditor: Claude (automated + sub-agent review)*

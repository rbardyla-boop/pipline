# TruthLens Pipeline — Agent Security Stack Architecture

## Repo Mapping Table

| Repo | Module | Purpose | Integration Point | Threat Surface | Mitigation |
|------|--------|---------|-------------------|---------------|------------|
| ProjectRecon/awesome-ai-agents-security | `security/threat-intel/` | Agent threat catalog (reference only) | CI threat model design | Doc injection via adversarial examples | Content isolation: docs only, never executed |
| promptfoo/promptfoo | `ci/tests/` | Red-team adversarial test runner | CI gate on all Claude API call sites | Test config injection | OPA validates configs before execution |
| aquasecurity/trivy | `ci/scanning/` | Container + Python dep CVE scanner | CI pre-merge + pre-deploy | False negatives on zero-days | Fail-open: unknowns require human sign-off |
| open-policy-agent/opa | `ci/policies/` | Policy-as-code for constitutional invariants | CI + runtime enforcement | Policy bypass via eval input manipulation | Rego policies signed, read-only in CI |
| AgentGateway | `security/gateway/` | Proxy for all outbound agent calls | Runtime — replaces direct API calls | Bypass via hardcoded URLs | grep-enforced: no raw `Anthropic()` outside security layer |
| microsoft/agent-governance-toolkit | `security/governance/` | Per-node identity + authorization contracts | Runtime — each LangGraph node governed | Node identity spoofing | Node signing + per-node allowlist |
| claude-code-security-review | `ci/scanning/` | Static analysis of Claude API usage patterns | CI — merged into bandit + grep checks | Regex evasion via encoding | Multi-layer: bandit + grep + OPA |
| vercel-labs/deepsec | `security/deepsec/` | **REQUIRES HUMAN VALIDATION** — repo availability unconfirmed | Deferred — placeholder only | Unknown | Do not integrate until confirmed live |
| dagger/container-use | `agent_sandbox/container/dagger.ts` | Reproducible container builds + trivy scan | CI + production build pipeline | Image tampering | Pinned digest + trivy scan on every build |
| meta-llama/LlamaFirewall | `security/firewall/` | Pre/post hook on all LLM calls | Runtime — wraps every `messages.create()` | Adversarial evasion | Multi-layer: keyword regex + LlamaFirewall package |
| microsandbox/microsandbox | `agent_sandbox/container/microsandbox.toml` | Per-execution hardware-level isolation | Runtime container config | Syscall-level escalation | seccomp BPF profile: deny mount/pivot_root/ptrace/bpf |

**Overlap resolution**: `claude-code-security-review` and `trivy` both do static scanning — merged into `ci/scanning/` as a single stage (trivy for deps/containers, claude-code patterns inform OPA rules).

---

## System Boundary Diagram

```
╔══════════════════════════════════════════════════════════════════╗
║                     CONSTITUTIONAL LAYER                         ║
║  truthlens-audit-schema-v1.json  (additionalProperties: false)  ║
║  PROTOCOL_INVARIANTS.md + MINIMAL_GOVERNANCE.md                 ║
║  OPA: constitutional.rego + dependency.rego + audit-schema.rego  ║
║  CI: check_imports.py + validate-constitution.ts (TS)           ║
╚══════════════════════════════════════════════════════════════════╝
                              ↕ enforces
╔══════════════════════════════════════════════════════════════════╗
║                     CI ENFORCEMENT LAYER                         ║
║  trivy → Python deps + Docker image CVE scan (CRITICAL/HIGH)    ║
║  bandit → Python static security analysis (HIGH severity)       ║
║  promptfoo → adversarial red-team on Claude API call sites      ║
║  framing-injection.yaml → interpretation layer attack tests     ║
║  OPA → policy-as-code gate (import graph + schema + telemetry)  ║
╚══════════════════════════════════════════════════════════════════╝
                              ↕ gates runtime
╔══════════════════════════════════════════════════════════════════╗
║                     AGENT GATEWAY LAYER                          ║
║  AgentGateway (localhost:8080) — all outbound calls proxied     ║
║  ├─ rate limiting (Claude: 60/min, Tavily: 30/min)             ║
║  ├─ credential injection (gateway holds keys; pipeline has none)║
║  ├─ output sanitization (strips embedded injection patterns)    ║
║  └─ audit event emission → logs/audit/                         ║
║  LlamaFirewallClient — pre/post hook on every LLM call         ║
║     ├─ keyword pattern scan (regex-based, always on)           ║
║     └─ LlamaFirewall package (semantic, if installed)          ║
║  NodeIdentity — per-node identity + tool allowlist             ║
╚══════════════════════════════════════════════════════════════════╝
           ↙  TRUST BOUNDARY  ↘
╔═══════════════════╗    ╔═════════════════════════════════════════╗
║  SIGNAL LAYER     ║    ║        INTERPRETATION LAYER             ║
║  signals.py       ║───→║  concept_rater.py  (Phoenix rubric)     ║
║  (deterministic)  ║    ║  sandbox.py        (cultural sim)       ║
║  NO LLM CALLS     ║    ║  ← reads signals only, CANNOT modify   ║
║  NO NETWORK       ║    ║  ← LLM calls via LlamaFirewallClient   ║
║  IMMUTABLE        ║    ║  ← Tavily via GatewayTavilyClient      ║
╚═══════════════════╝    ╚═════════════════════════════════════════╝
                                        ↓
╔══════════════════════════════════════════════════════════════════╗
║                   CONTAINER SANDBOX LAYER                        ║
║  docker/Dockerfile: python:3.12-slim@sha256:<pinned>           ║
║  uid=65534, read-only rootfs, /tmp tmpfs only                   ║
║  seccomp: block mount/pivot_root/ptrace/bpf/setuid             ║
║  no-new-privileges: true | cap_drop: ALL                        ║
║  network: internal Docker only → gateway:8080                   ║
║  microsandbox.toml: per-exec hardware isolation profile         ║
║  dagger.ts: reproducible builds + trivy scan on every build     ║
╚══════════════════════════════════════════════════════════════════╝
                              ↓
╔══════════════════════════════════════════════════════════════════╗
║                    AUDIT EXPORT LAYER                            ║
║  logs/runs/full_run_*.json  (pipeline run data)                 ║
║  logs/audit/audit_*.json    (schema-conformant audit records)   ║
║  AJV validates before write — hard fail on schema violation     ║
║  agent_sandbox/src/audit.ts — Node.js schema validator          ║
║  orchestrator.py _write_audit_record() — Python emitter         ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Key Integration Points by Module

### `security/firewall/llamafirewall_wrapper.py`
- Wraps `anthropic.Anthropic()` — every `messages.create()` call is intercepted
- Pre-call: scans all message content for injection patterns (14 regex rules)
- Post-call: scans response for credential leakage + injection bleed-through
- Delegates to real LlamaFirewall package if installed, rule-based fallback if not
- `get_secure_client()` is the only permitted factory for Claude clients

### `security/gateway/gateway_client.py`
- Wraps `tavily.TavilyClient` — routes through AgentGateway in containerized mode
- Post-fetch: scans every result snippet for injection payloads
- Suppresses blocked content (replaces with `[BLOCKED: reason]`)

### `security/governance/node_identity.py`
- Registry of per-node identity contracts (`NODES` dict)
- `signals` node: `may_call_llm=False`, `may_call_network=False` (enforced at runtime)
- `mutate`/`refine` nodes: `may_call_llm=True` (Claude only, via firewall)
- `ingest` node: `may_call_network=True` (Tavily only, via gateway)

### `ci/scripts/check_imports.py`
- Static import graph analyser — produces OPA input + grep-based fallback
- Run: `python ci/scripts/check_imports.py`
- Exit 1 = constitutional violation detected

### `agent_sandbox/src/runtime.ts`
- Node.js orchestrator for containerized pipeline runs
- Pre-flight: verifies Docker image, seccomp profile, gateway health
- Post-run: parses output, builds audit record, validates with AJV, writes

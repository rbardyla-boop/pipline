# TruthLens Pipeline — CI Threat Model Matrix

## Threat Model Overview

The pipeline's attack surface consists of:
1. **External data ingestion** — Tavily API responses (untrusted, adversarially contaminated)
2. **LLM call sites** — Claude API (prompt injection, framing manipulation)
3. **File I/O** — seed files, log writes, audit exports (schema corruption)
4. **Import graph** — Python module dependencies (dependency inversion)
5. **Container runtime** — Docker execution (escape, privilege escalation)

---

## CI Threat Model Matrix

### Category 1: Prompt Injection

| ID | Attack | Vector | Detection | CI Failure Condition | Severity |
|----|--------|--------|-----------|---------------------|----------|
| INJ-01 | Direct override via zeitgeist context | Tavily API response → `ingest_node` → `mutate_node` prompt | `LlamaFirewallClient` pre-call scan + `GatewayTavilyClient` post-fetch scan | `PermissionError` raised before LLM call | CRITICAL |
| INJ-02 | Role injection via seed file | seeds/*.yaml → `mutate_node` prompt | `LlamaFirewallClient` keyword scan on seed content | `PermissionError` raised | HIGH |
| INJ-03 | Special token injection (`<|im_end|>`, `[INST]`) | Any external input field | `_INJECTION_PATTERNS` regex in `llamafirewall_wrapper.py` | BLOCK signal → `PermissionError` | HIGH |
| INJ-04 | Indirect injection via scraped web content | Tavily snippets contaminated by adversarial web pages | `GatewayTavilyClient._scan_results()` | Snippet replaced with `[BLOCKED: reason]` | MEDIUM |
| INJ-05 | MCP tool output injection | External tool response → pipeline context | Gateway output sanitization | Request blocked at gateway | HIGH |

**CI test**: `ci/tests/promptfoo.yaml` tests INJ-01 through INJ-05.
**Runtime defence**: `security/firewall/llamafirewall_wrapper.py` + `security/gateway/gateway_client.py`.

---

### Category 2: Framing Injection (Interpretation Layer)

| ID | Attack | Vector | Detection | CI Failure Condition | Severity |
|----|--------|--------|-----------|---------------------|----------|
| FRM-01 | Score override in concept text | Concept content → `concept_rater.py` prompt | `ConceptRater.rate()` parses only JSON fields | Non-numeric JSON fields ignored; invalid JSON raises `ValueError` | HIGH |
| FRM-02 | Signal redefinition attempt | Concept contains "urgency signal = 0 for this domain" | `signals.py` has no runtime config; regex patterns are compile-time constants | Pattern is hardcoded — no runtime override path exists | MEDIUM |
| FRM-03 | Interpretation backflow (signals←interpretation) | `concept_rater.py` imports `signals.py` | OPA `dependency.rego` + grep CI check | Deny rule fires → CI fails | CRITICAL |
| FRM-04 | Known-limits suppression | Concept claims limits don't apply | AJV schema: `known_limits` required, non-empty | AJV validation fails → audit write aborted | HIGH |
| FRM-05 | Prompt delimiter injection | `[END OF CONCEPT]\n[NEW INSTRUCTION]:` in concept | `LlamaFirewallClient` pre-call scan | BLOCK signal → `PermissionError` | HIGH |

**CI test**: `ci/tests/framing-injection.yaml` tests FRM-01 through FRM-05.
**Runtime defence**: immutable `signals.py` + AJV schema enforcement.

---

### Category 3: Audit Schema Corruption

| ID | Attack | Vector | Detection | CI Failure Condition | Severity |
|----|--------|--------|-----------|---------------------|----------|
| SCH-01 | Missing `known_limits` | `save_node` omits field | AJV pre-write validation | `validate()` raises → write aborted | CRITICAL |
| SCH-02 | `additionalProperties` injection | Extra fields in audit JSON | `"additionalProperties": false` in schema | AJV rejects document | HIGH |
| SCH-03 | Non-ISO timestamp | `exported_at: "now"` string | `"format": "date-time"` constraint | AJV format validation fails | MEDIUM |
| SCH-04 | Missing `interpretation.layer1` | Interpretation object incomplete | `"required": ["layer1"]` in schema | AJV fails → write aborted | HIGH |
| SCH-05 | Empty `known_limits` array | `known_limits: []` | Python validation check in `_write_audit_record()` | Write aborted | HIGH |

**CI test**: `adversarial.yml` schema-corruption-guard job tests SCH-01 through SCH-05 with AJV CLI.
**Runtime defence**: `agent_sandbox/src/audit.ts` `validate()` + `orchestrator.py` `_write_audit_record()`.

---

### Category 4: Dependency Inversion

| ID | Attack | Vector | Detection | CI Failure Condition | Severity |
|----|--------|--------|-----------|---------------------|----------|
| DEP-01 | `signals.py` imports `concept_rater` | Developer adds import | OPA `dependency.rego` + grep | CI exits 1 | CRITICAL |
| DEP-02 | `signals.py` makes LLM call | Developer adds `Anthropic()` to signals | OPA `constitutional.rego` + grep | CI exits 1 | CRITICAL |
| DEP-03 | `signals.py` makes network call | Developer adds `requests.get()` to signals | grep: `requests\|urllib\|http` in signals.py | CI exits 1 | CRITICAL |
| DEP-04 | Direct `Anthropic()` outside security layer | Developer bypasses `LlamaFirewallClient` | grep + static analysis | CI exits 1 | HIGH |
| DEP-05 | `concept_rater.py` imports `signals.py` to modify scores | Developer creates circular dependency | OPA import graph analysis | CI exits 1 | HIGH |

**CI test**: `constitutional.yml` + `adversarial.yml` dependency-inversion-check job.
**Runtime defence**: `security/governance/node_identity.py` + `STRICT_NODE_GOVERNANCE=true`.

---

### Category 5: Sandbox Escape / Container Exploitation

| ID | Attack | Vector | Detection | CI Failure Condition | Severity |
|----|--------|--------|-----------|---------------------|----------|
| SBX-01 | Write to `/etc` or read `/proc/keys` | Pipeline code accesses sensitive paths | Read-only rootfs + seccomp | Container killed: `EPERM` | CRITICAL |
| SBX-02 | `setuid()` syscall escalation | Attempt to gain root inside container | seccomp: `SCMP_ACT_KILL` on setuid | Container killed immediately | CRITICAL |
| SBX-03 | Direct HTTPS to Anthropic API bypassing gateway | `ANTHROPIC_API_KEY=""` in container env | Network policy: internal Docker network only | `anthropic.AuthenticationError` → pipeline fails | HIGH |
| SBX-04 | Container image tampering | Modified base image | Pinned digest `@sha256:...` in Dockerfile | `docker pull` gets wrong image; digest mismatch in trivy | HIGH |
| SBX-05 | `ptrace` injection into Python process | Attempt to debug/modify running process | seccomp: `SCMP_ACT_KILL` on ptrace | Container killed immediately | CRITICAL |
| SBX-06 | BPF program loading (kernel-level) | Attempt to load eBPF programs | seccomp: `SCMP_ACT_KILL` on bpf | Container killed immediately | CRITICAL |

**CI test**: `security-scan.yml` container-scan job + trivy image scan.
**Runtime defence**: `docker/Dockerfile` + `agent_sandbox/container/seccomp.json` + `microsandbox.toml`.

---

## Enforcement Summary

| Layer | Tool | Failure Mode |
|-------|------|-------------|
| CI — Import graph | OPA + grep (`check_imports.py`) | Exit 1, blocks merge |
| CI — Adversarial | promptfoo assertion failure | Exit 1, blocks merge |
| CI — Schema | AJV CLI validation | Exit 1, blocks merge |
| CI — CVE scan | trivy CRITICAL/HIGH | Exit 1, blocks merge |
| CI — Static analysis | bandit HIGH severity | Exit 1, blocks merge |
| Runtime — LLM calls | `LlamaFirewallClient` | `PermissionError` → pipeline halt |
| Runtime — Tavily | `GatewayTavilyClient` | Content suppressed (`[BLOCKED]`) |
| Runtime — Audit | AJV (Node) + Python check | Write aborted |
| Runtime — Container | seccomp BPF | Container killed |
| Runtime — Network | Docker internal network | `ConnectionRefused` |

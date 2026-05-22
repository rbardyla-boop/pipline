# TruthLens Pipeline — Security Boundary Diagram

## Trust Zone Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZONE 0: EXTERNAL (UNTRUSTED)                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │  api.anthropic   │  │  api.tavily.com  │  │  Web content (Tavily        │ │
│  │  .com            │  │                  │  │  search results)            │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────┬──────────────┘│
└───────────┼─────────────────────┼────────────────────────────┼──────────────┘
            │                     │                            │
            │   GATEWAY BOUNDARY  │                            │
            ▼                     ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZONE 1: GATEWAY (SEMI-TRUSTED)                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  AgentGateway (localhost:8080 / gateway:8080 in Docker)              │  │
│  │  ├─ Holds: ANTHROPIC_API_KEY, TAVILY_API_KEY (environment vars)      │  │
│  │  ├─ Rate limits: Claude 60/min, Tavily 30/min                        │  │
│  │  ├─ Injection scan: blocks patterns from gateway_config.yaml         │  │
│  │  ├─ Credential strip: never logs API keys                            │  │
│  │  └─ Audit events: emits to logs/audit/ (schema-conformant)          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  Trust level: Gateway-owned secrets; validates but does not execute code    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    FIREWALL BOUNDARY (LlamaFirewall)
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZONE 2: PIPELINE EXECUTION (CONTROLLED)                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LLM CALL SITES (mutate_node, refine_node)                         │   │
│  │  All calls via LlamaFirewallClient:                                 │   │
│  │    pre-call scan → [gateway:8080/anthropic] → post-call scan        │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│           ONE-WAY DEPENDENCY BOUNDARY                                      │
│                               │                                            │
│  ┌────────────────────┐       │       ┌───────────────────────────────┐    │
│  │  SIGNAL LAYER      │       │       │  INTERPRETATION LAYER         │    │
│  │  signals.py        │──────→│       │  concept_rater.py             │    │
│  │                    │               │  sandbox.py                   │    │
│  │  Properties:       │               │                               │    │
│  │  ✓ Deterministic   │               │  Properties:                  │    │
│  │  ✓ No LLM calls    │               │  ✓ Reads signals (one-way)    │    │
│  │  ✓ No network      │               │  ✗ Cannot write to signals    │    │
│  │  ✓ Immutable       │               │  ✓ LLM via firewall           │    │
│  └────────────────────┘               └───────────────────────────────┘    │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  RUNTIME ISOLATION: Container (Docker + microsandbox)                │  │
│  │  ├─ Base: python:3.12-slim@sha256:<pinned>                          │  │
│  │  ├─ User: uid=65534 (nobody), no capabilities                       │  │
│  │  ├─ Rootfs: read-only (only /tmp and /app/logs writable)            │  │
│  │  ├─ seccomp: kill on mount/pivot_root/ptrace/bpf/setuid             │  │
│  │  ├─ Network: internal Docker only (→ gateway, no internet)          │  │
│  │  └─ Env: no credentials (ANTHROPIC_API_KEY="", TAVILY_API_KEY="")  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    AUDIT BOUNDARY (Schema Validation)
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ZONE 3: AUDIT OUTPUT (IMMUTABLE)                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  logs/audit/audit_*.json                                             │  │
│  │  Validated by AJV against truthlens-audit-schema-v1.json            │  │
│  │  ├─ Required: protocol, article, signals, interpretation,            │  │
│  │  │           known_limits, exported_at                               │  │
│  │  ├─ additionalProperties: false (no injection via extra fields)     │  │
│  │  ├─ known_limits: non-empty (explicit limitation documentation)     │  │
│  │  └─ Write mode: wx (fail if exists — no overwrite, append-only)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  Trust level: Schema-validated, immutable once written                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## CI/CD Gate Model

```
Developer Push
      │
      ▼
┌─────────────────────────────────┐
│  constitutional.yml             │  Hard fail on:
│  ├─ OPA + grep import check     │  - signals imports interpretation
│  ├─ signals.py purity check     │  - LLM/network in signals layer
│  ├─ no hardcoded API keys       │  - Hardcoded credentials
│  ├─ TruthLens constitution      │  - Constitutional term violations
│  └─ Audit schema sample test    │  - Schema validation failure
└────────────┬────────────────────┘
             │ PASS
             ▼
┌─────────────────────────────────┐
│  security-scan.yml              │  Hard fail on:
│  ├─ trivy filesystem scan       │  - CRITICAL/HIGH CVE in deps
│  ├─ trivy Docker image scan     │  - CRITICAL/HIGH CVE in image
│  ├─ bandit static analysis      │  - HIGH severity Python vulns
│  └─ direct client instantiation │  - Anthropic() outside security/
└────────────┬────────────────────┘
             │ PASS
             ▼
┌─────────────────────────────────┐
│  adversarial.yml                │  Hard fail on:
│  ├─ promptfoo injection tests   │  - Any injection test passes through
│  ├─ framing injection tests     │  - Score manipulation succeeds
│  ├─ dependency inversion check  │  - signals.py purity violated
│  └─ schema corruption tests     │  - AJV accepts invalid record
└────────────┬────────────────────┘
             │ ALL PASS
             ▼
           Merge allowed
```

## Invariant Registry

| Invariant | Enforcement | Failure |
|-----------|-------------|---------|
| `signals/` → `interpretation/` one-way | OPA + grep + pytest | CI hard fail |
| `signals.py` deterministic (no LLM, no network) | OPA + grep | CI hard fail |
| No hardcoded credentials | trivy + grep | CI hard fail |
| All LLM calls via `LlamaFirewallClient` | grep CI check | CI hard fail |
| Audit exports schema-conformant | AJV (Node.js) | Write aborted |
| `known_limits` non-empty in all audit records | AJV + Python check | Write aborted |
| No telemetry calls | OPA constitutional.rego | CI hard fail |
| Container runs as uid=65534 | Dockerfile + compose | Build-time enforced |
| Container has no credentials | Dockerfile ENV="" | Build-time enforced |
| seccomp profile applied | compose security_opt | Runtime enforced |

# Universal Extrapolative Engine (UEE)

A research pipeline that evolves creative concepts across generational mutation cycles using novelty search, cultural simulation, and LLM-based scoring. Built on the **Universal Agentic Framework (UAF)** — an architecture-agnostic simulation kernel with pluggable cognition engines.

**Status:** Phase 10 · 217 tests passing · Python ≥ 3.12

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-security.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and TAVILY_API_KEY

# 4. Run the pipeline
python main.py seeds/gaming.yaml
```

## Commands

<!-- AUTO-GENERATED -->
| Command | Description |
|---------|-------------|
| `python main.py seeds/gaming.yaml` | Run the UAF pipeline on the gaming seed file (default mode) |
| `python main.py seeds/film.yaml` | Run on the film seed file |
| `python main.py seeds/saas.yaml` | Run on the SaaS seed file |
| `UAF_KERNEL=false python main.py seeds/gaming.yaml` | Run via legacy LangGraph orchestrator |
| `python run_hypothesis.py hypotheses/attention_heads_experiment.yaml` | Execute a YAML-defined hypothesis via ExperimentLoop |
| `./scripts/research_ui.sh` | Launch the Streamlit research workbench UI |
| `streamlit run frontend/app.py --server.port 8501` | Launch research UI directly |
| `pytest` | Run the full test suite |
| `pytest --cov=. --cov-report=term-missing` | Run tests with coverage report |
| `python ci/scripts/check_imports.py` | Run constitutional import-graph analysis (CI gate) |
| `bandit -r . -lll` | Run Python security scan (HIGH severity) |
| `docker compose -f docker/docker-compose.yml up` | Run in hardened container stack (gateway + pipeline) |
<!-- END AUTO-GENERATED -->

## Pipeline Architecture

### UAF Kernel Path (default: `UAF_KERNEL=true`)

```
seeds/*.yaml
    ↓
[LOAD]    make_creative_evolution_experiment() — wires 5 adapters
    ↓
[KERNEL]  SimulationKernel — architecture-agnostic state machine
          INIT → EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE → [HALT | EXECUTE]
    ↓
[RECORD]  DynamicsRecorder — per-cycle snapshots (candidate, score, verdict, duration)
    ↓
[LEDGER]  ExperimentLedger — tracks and compares runs
    ↓
[SAVE]    logs/runs/full_run_*.json + logs/audit/audit_*.json
```

### Legacy LangGraph Path (`UAF_KERNEL=false`)

```
seeds/*.yaml
    ↓
[INGEST]  ZeitgeistInjector — pulls live cultural context via Tavily
    ↓
[ENTROPY] Decay archive novelty scores each refinement loop
    ↓
[MUTATE]  NoveltySearchEngine.evolve() — 10 generations × 6 variants/gen
    ↓
[SANDBOX] CulturalSandbox — simulates 5-week social adoption curve
    ↓
[REFINE]  ConceptRater — Phoenix rubric scoring (0–5), Goodhart guard
    ↓
[GATE]    EphemeralGate — optional human resonance checkpoint
    ↓
[SAVE]    logs/runs/full_run_*.json + logs/audit/audit_*.json
```

Refinement loops until score plateaus or `MAX_IMPROVEMENT_LOOPS` is reached. Verdicts: `HIT` | `SLOP` | `COUNTER_SIGNAL`.

## Environment Variables

See [.env.example](.env.example) for the full list with descriptions.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `TAVILY_API_KEY` | Yes | — | Tavily search API key |
| `NOVELTY_THRESHOLD` | No | `0.68` | Min cosine distance to admit concept to archive |
| `ARCHIVE_MAX` | No | `500` | Max archive size |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | sentence-transformers model |
| `UAF_KERNEL` | No | `true` | Use UAF kernel path (`false` = legacy LangGraph) |
| `V5_SIMULATOR` | No | `false` | Enable v5 trajectory simulator |
| `EPHEMERAL_GATE` | No | `false` | Enable human resonance checkpoint |
| `ENTROPY_DECAY_RATE` | No | `0.05` | Per-generation archive decay rate |
| `TERMINAL_ARCHIVE_PATH` | No | `logs/terminal_archive.json` | Path for retired high-scoring concepts |
| `STRICT_NODE_GOVERNANCE` | No | `false` | Enforce per-node identity contracts (`true` in Docker) |
| `GATEWAY_URL` | No | `""` | AgentGateway URL (required in Docker mode) |
| `RESEARCH_UI_PORT` | No | `8501` | Streamlit UI port |

## Project Structure

```
pipline/
├── main.py                   # Entry point — dispatches to UAF or legacy path
├── orchestrator.py           # Legacy LangGraph pipeline (UAF_KERNEL=false)
├── engine.py                 # NoveltySearchEngine — embedding + evolution
├── concept_rater.py          # Phoenix rubric scorer
├── sandbox.py                # CulturalSandbox — 5-week simulation
├── simulator.py              # V5 trajectory simulator
├── signals.py                # Deterministic signal extractors (no LLM/network)
├── zeitgeist.py              # ZeitgeistInjector — live cultural context
├── experiment.py             # Experiment execution helpers
├── run_hypothesis.py         # CLI runner for YAML-defined hypotheses (ExperimentLoop)
├── dashboard.py              # Research dashboard utilities
├── uaf/                      # Universal Agentic Framework
│   ├── kernel/               # SimulationKernel, state machine, invariants
│   ├── interfaces/           # Abstract interfaces (cognition, memory, planner, verification, runtime)
│   ├── experiments/          # ExperimentRunner, ExperimentLedger, ExperimentDefinition, comparison
│   ├── dynamics/             # Trajectory recorder, metrics
│   ├── llm/                  # LLM integration layer (11 modules)
│   │   ├── transformer.py    # Transformer utilities + RMSNorm
│   │   ├── memory_stack.py   # Conversation memory management
│   │   ├── context_manager.py# Dynamic context management
│   │   ├── prompt_system.py  # Prompt construction
│   │   ├── evaluator.py      # LLM output evaluation
│   │   ├── retrieval.py      # RAG/retrieval integration
│   │   ├── metrics.py        # LLM performance metrics
│   │   ├── multi_agent.py    # Multi-agent orchestration
│   │   ├── guardrails.py     # LLM safety guardrails
│   │   └── router.py         # LLM routing logic
│   └── research/             # Hypothesis runner, research panel, trial harness
│       ├── trial_runner.py
│       ├── panel.py
│       ├── hypothesis.py
│       └── loop.py
├── experiments/
│   └── creative_evolution/   # Concrete UAF experiment (definition + 4 adapters)
├── architectures/            # Pluggable generation backends
│   ├── neural/               # TinyTransformer + char tokenizer
│   ├── symbolic_grammar/     # Symbolic grammar adapter
│   ├── parametric/           # Parametric template adapter
│   ├── claude_novelty/       # Claude-based novelty adapter
│   └── llm_arch/             # LLM generation architecture
├── frontend/                 # Streamlit research workbench
│   └── components/           # UI panels (hypotheses, dynamics, journal, controls)
├── security/
│   ├── firewall/             # LlamaFirewall wrapper (pre/post LLM hook)
│   ├── gateway/              # AgentGateway client (Tavily proxy)
│   ├── governance/           # Per-node identity contracts
│   └── threat-intel/         # Threat catalog
├── ci/
│   ├── scripts/              # check_imports.py — constitutional analysis
│   ├── policies/             # OPA Rego policies (constitutional, dependency, audit-schema)
│   ├── scanning/             # trivy configs + .trivyignore
│   └── tests/                # promptfoo adversarial + framing-injection configs
├── .github/
│   └── workflows/            # adversarial.yml, constitutional.yml, security-scan.yml
├── docker/
│   ├── Dockerfile            # Hardened image (uid=65534, read-only rootfs, pinned digest)
│   └── docker-compose.yml    # Gateway + pipeline isolation stack
├── seeds/                    # Domain seed YAML files (gaming, film, saas, pipeline_v3)
├── hypotheses/               # Experiment hypothesis YAML + results JSON
├── logs/                     # Runtime output (gitignored except .gitkeep)
├── docs/                     # Architecture, security, research, and tech debt docs
├── pyproject.toml            # Package config (uee-pipeline 0.1.0), pytest config
├── requirements.txt
├── requirements-security.txt
└── .env.example
```

## Research Hypotheses

Hypotheses are defined as YAML files in `hypotheses/` and executed via `run_hypothesis.py`:

| Hypothesis | Question | Status |
|------------|----------|--------|
| `attention_heads_experiment.yaml` | Does increasing attention head count improve coherence at fixed embed_dim=64? (1/2/4/8 heads) | Results available |
| `coherence_diversity_frontier.yaml` | Which `coherence_mode × template_count` maximises mean score and final convergence? (2×2 grid) | Results available |
| `template_complexity.yaml` | Impact of template count and coherence mode on output quality | Defined |

Results are written to `hypotheses/*.json` alongside the YAML definitions.

## Security

The pipeline runs behind a layered security stack:

- **LlamaFirewall** — pre/post hook on every Claude API call (14 regex rules + semantic check)
- **AgentGateway** — credential proxy; pipeline container holds no API keys
- **Node governance** — per-node identity contracts (`STRICT_NODE_GOVERNANCE=true` in Docker)
- **Constitutional CI** — OPA policies + `check_imports.py` enforce import-graph invariants (hard fail, no bypass)
- **Adversarial CI** — `promptfoo` red-team suite (prompt injection, framing injection) runs on push + weekly schedule
- **Dependency scanning** — Trivy CRITICAL/HIGH scan on push + daily schedule; results uploaded to GitHub Security tab
- **Hardened container** — uid=65534, read-only rootfs, seccomp BPF, `cap_drop: ALL`, `no-new-privileges: true`

See [docs/SECURITY_BOUNDARY.md](docs/SECURITY_BOUNDARY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for details.

## CI Workflows

| Workflow | Trigger | Gate |
|----------|---------|------|
| `constitutional.yml` | push / PR to main | Import graph + OPA policy check — hard fail |
| `security-scan.yml` | push / PR + daily 06:00 UTC | Trivy CRITICAL/HIGH — fail on findings |
| `adversarial.yml` | push / PR + weekly Monday 08:00 UTC | promptfoo injection red-team |

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Security stack and system boundary diagram |
| [docs/OPERATIONAL_ARCHITECTURE.md](docs/OPERATIONAL_ARCHITECTURE.md) | Runtime node flow and state machine |
| [docs/SECURITY_BOUNDARY.md](docs/SECURITY_BOUNDARY.md) | Trust boundary definitions |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Threat model and mitigations |
| [docs/DESIGN_DOCTRINE.md](docs/DESIGN_DOCTRINE.md) | Architectural design principles |
| [docs/UEE_RESEARCH_DOCTRINE_v1.md](docs/UEE_RESEARCH_DOCTRINE_v1.md) | Research methodology |
| [docs/EXPERIMENTAL_LEDGER.md](docs/EXPERIMENTAL_LEDGER.md) | Experiment tracking schema |
| [docs/RESEARCH_FINDINGS.md](docs/RESEARCH_FINDINGS.md) | Research findings log |
| [docs/TECH_DEBT.md](docs/TECH_DEBT.md) | Active tech debt register |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Development setup and workflow |

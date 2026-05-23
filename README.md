# Universal Extrapolative Engine (UEE)

A research pipeline that evolves creative concepts across generational mutation cycles using novelty search, cultural simulation, and LLM-based scoring.

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
| `./scripts/research_ui.sh` | Launch the Streamlit research workbench UI |
| `streamlit run frontend/app.py --server.port 8501` | Launch research UI directly |
| `pytest` | Run the full test suite |
| `pytest --cov=. --cov-report=term-missing` | Run tests with coverage report |
| `python ci/scripts/check_imports.py` | Run constitutional import-graph analysis (CI gate) |
| `bandit -r . -lll` | Run Python security scan (HIGH severity) |
| `docker compose -f docker/docker-compose.yml up` | Run in hardened container stack (gateway + pipeline) |
<!-- END AUTO-GENERATED -->

## Pipeline Architecture

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

Refinement loops until score plateaus or `MAX_IMPROVEMENT_LOOPS` is reached.

## Environment Variables

See [.env.example](.env.example) for the full list with descriptions.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `TAVILY_API_KEY` | Yes | — | Tavily search API key |
| `NOVELTY_THRESHOLD` | No | `0.68` | Min cosine distance to admit concept to archive |
| `ARCHIVE_MAX` | No | `500` | Max archive size |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | sentence-transformers model |
| `UAF_KERNEL` | No | `true` | Use UAF kernel path (`false` = legacy) |
| `V5_SIMULATOR` | No | `false` | Enable v5 trajectory simulator |
| `EPHEMERAL_GATE` | No | `false` | Enable human resonance checkpoint |
| `ENTROPY_DECAY_RATE` | No | `0.05` | Per-generation archive decay rate |
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
├── uaf/                      # Universal Agent Framework
│   ├── kernel/               # SimulationKernel, state, invariants
│   ├── interfaces/           # Abstract interfaces (cognition, memory, planner…)
│   ├── experiments/          # ExperimentRunner, ExperimentLedger, comparison
│   ├── dynamics/             # Trajectory recorder, metrics
│   └── research/             # Hypothesis runner, research panel
├── experiments/
│   └── creative_evolution/   # Concrete UAF experiment definition + adapters
├── architectures/            # Pluggable generation backends
│   ├── neural/               # TinyTransformer + char tokenizer
│   ├── symbolic_grammar/     # Symbolic grammar adapter
│   ├── parametric/           # Parametric adapter
│   └── claude_novelty/       # Claude-based novelty adapter
├── frontend/                 # Streamlit research workbench
│   └── components/           # UI panels (hypotheses, dynamics, journal, controls)
├── security/
│   ├── firewall/             # LlamaFirewall wrapper (pre/post LLM hook)
│   ├── gateway/              # AgentGateway client (Tavily proxy)
│   └── governance/           # Per-node identity contracts
├── ci/
│   ├── scripts/              # check_imports.py — constitutional analysis
│   ├── policies/             # OPA Rego policies
│   ├── scanning/             # trivy configs
│   └── tests/                # promptfoo adversarial test configs
├── docker/
│   ├── Dockerfile            # Hardened image (uid=65534, read-only rootfs)
│   └── docker-compose.yml    # Gateway + pipeline isolation stack
├── seeds/                    # Domain seed YAML files
├── hypotheses/               # Experiment hypothesis YAML + results
├── logs/                     # Runtime output (gitignored except .gitkeep)
├── docs/                     # Architecture, security, and research docs
├── requirements.txt
├── requirements-security.txt
└── .env.example
```

## Security

The pipeline runs behind a layered security stack:

- **LlamaFirewall** — pre/post hook on every Claude API call (14 regex rules + semantic check)
- **AgentGateway** — credential proxy; pipeline container holds no API keys
- **Node governance** — per-LangGraph-node identity contracts (signals node: no LLM, no network)
- **Constitutional CI** — OPA policies + `check_imports.py` enforce import-graph invariants
- **Hardened container** — uid=65534, read-only rootfs, seccomp BPF, `cap_drop: ALL`

See [docs/SECURITY_BOUNDARY.md](docs/SECURITY_BOUNDARY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for details.

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
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Development setup and workflow |

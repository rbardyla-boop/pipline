# Contributing

## Prerequisites

- Python 3.12+
- `git`
- Docker + Docker Compose (optional, for containerised runs)

## Development Setup

```bash
# Clone and enter the repo
git clone <repo-url>
cd pipline

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-security.txt

# Configure environment
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY and TAVILY_API_KEY
```

## Available Commands

<!-- AUTO-GENERATED -->
| Command | Description |
|---------|-------------|
| `python main.py seeds/gaming.yaml` | Run UAF pipeline (gaming domain) |
| `python main.py seeds/film.yaml` | Run UAF pipeline (film domain) |
| `python main.py seeds/saas.yaml` | Run UAF pipeline (SaaS domain) |
| `UAF_KERNEL=false python main.py seeds/gaming.yaml` | Run via legacy LangGraph orchestrator |
| `./scripts/research_ui.sh` | Launch Streamlit research workbench |
| `streamlit run frontend/app.py --server.port 8501` | Launch research UI directly |
| `pytest` | Run the full test suite |
| `pytest -x` | Run tests, stop on first failure |
| `pytest --cov=. --cov-report=term-missing` | Run tests with coverage report |
| `pytest tests/test_kernel.py` | Run a specific test module |
| `python ci/scripts/check_imports.py` | Constitutional import-graph analysis |
| `bandit -r . -lll` | Python security scan (HIGH+ severity) |
| `docker compose -f docker/docker-compose.yml up` | Run hardened container stack |
<!-- END AUTO-GENERATED -->

## Testing

Tests live in `tests/`. Run them with `pytest` from the project root — `conftest.py` adds the root to `sys.path` automatically.

```bash
pytest                             # all tests
pytest tests/test_kernel.py        # single module
pytest -k "novelty"                # keyword filter
pytest --cov=. --cov-report=html   # HTML coverage report → htmlcov/
```

Minimum coverage target: **80%**. New functionality must include tests. Follow the Red → Green → Refactor cycle.

Test modules and what they cover:

| File | Coverage |
|------|---------|
| `tests/test_kernel.py` | UAF SimulationKernel |
| `tests/test_interfaces.py` | UAF abstract interfaces |
| `tests/test_adapters.py` | Architecture adapters |
| `tests/test_dynamics.py` | Trajectory recorder and metrics (unit) |
| `tests/test_dynamics_real.py` | Dynamics recorder integration — Phase 10 session-embedding fix |
| `tests/test_research.py` | Hypothesis runner and research panel |
| `tests/test_panel.py` | Research panel |
| `tests/test_neural_arch.py` | TinyTransformer + char tokenizer |
| `tests/test_symbolic_arch.py` | Symbolic grammar adapter |
| `tests/test_novelty.py` | Novelty search engine |
| `tests/test_regression_main.py` | End-to-end regression |

**Modules with no coverage** (priority gaps — see `docs/TECH_DEBT.md`):
`security/firewall/`, `security/gateway/`, `security/governance/`, `orchestrator.py` nodes, `concept_rater.py`, `sandbox.py`, `signals.py`, `zeitgeist.py`, `dashboard.py`, `frontend/`

## Code Style

- Follow **PEP 8**; use type annotations on all function signatures.
- Prefer immutable data structures (frozen dataclasses, NamedTuples).
- Functions: <50 lines. Files: <800 lines. Nesting: ≤4 levels.
- Handle errors explicitly — never swallow exceptions silently.
- No hardcoded secrets. Validate required env vars at startup.

## Seed Files

Domain seeds live in `seeds/*.yaml`. Each file has a `domain` key and a `seeds` list of concept strings:

```yaml
domain: gaming
seeds:
  - "A free-to-play mobile fantasy gacha squad-battler..."
```

Add a new seed file to experiment with a new domain — no code changes needed.

## Hypothesis Files

Experiment hypotheses live in `hypotheses/*.yaml`. See existing files for the schema. Results are appended to `hypotheses/` and tracked in `logs/experiment_ledger.jsonl`.

## Security

Before committing:

- Run `python ci/scripts/check_imports.py` — must exit 0.
- Run `bandit -r . -lll` — no HIGH/CRITICAL findings.
- Confirm no API keys or secrets are staged (`git diff --cached`).
- Do not commit `.env` or any `*.key` / `*.pem` file.

See [SECURITY_BOUNDARY.md](SECURITY_BOUNDARY.md) and [THREAT_MODEL.md](THREAT_MODEL.md).

## CI Gates

The following checks must pass before a PR is merged:

1. `pytest` — full test suite green
2. `python ci/scripts/check_imports.py` — no constitutional violations
3. `bandit -r . -lll` — no HIGH or CRITICAL findings
4. `trivy` container and dep scan (CI pipeline)
5. `promptfoo` adversarial red-team tests (CI pipeline)

## Commit Messages

Follow Conventional Commits:

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Example: `feat: add coherence_diversity_frontier hypothesis runner`

## Pull Request Checklist

- [ ] Tests added or updated for all changed behaviour
- [ ] `pytest` passes locally
- [ ] `python ci/scripts/check_imports.py` exits 0
- [ ] No secrets or credentials in staged files
- [ ] Commit messages follow Conventional Commits format
- [ ] PR description explains the *why*, not just the *what*

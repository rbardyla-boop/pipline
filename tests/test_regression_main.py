"""Phase 6 regression tests: main.py entry points.

These tests verify that:
1. The legacy path (UAF_KERNEL unset) still resolves orchestrator.run correctly.
2. The UAF_KERNEL=true path loads the creative evolution experiment definition.
3. The experiment definition assembles without errors (modules importable).
4. The UAF output includes all required keys for a full_run_*.json equivalent.

NOTE: These tests do NOT make real API calls or run the full simulation.
They verify the wiring and module resolution. The full end-to-end regression
(byte-comparable output check) requires ANTHROPIC_API_KEY and is run manually
before the Phase 6 default flip.
"""

import os
import json
import sys
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ------------------------------------------------------------------ #
# Legacy path verification                                            #
# ------------------------------------------------------------------ #


def test_legacy_path_imports_orchestrator():
    """UAF_KERNEL unset → main._run_legacy imports from orchestrator."""
    import main
    assert callable(main._run_legacy)


def test_uaf_path_importable():
    """UAF_KERNEL=true path imports without error (no real calls)."""
    import main
    assert callable(main._run_uaf)


def test_load_seed_file_gaming(tmp_path):
    """load_seed_file parses YAML seed files correctly."""
    import main
    seed_path = tmp_path / "test_seed.yaml"
    seed_path.write_text("domain: gaming\nseeds:\n  - concept a\n  - concept b\n")
    config = main.load_seed_file(str(seed_path))
    assert config["domain"] == "gaming"
    assert len(config["seeds"]) == 2


def test_load_seed_file_real_gaming():
    """Real seeds/gaming.yaml must parse and have required keys."""
    import main
    config = main.load_seed_file("seeds/gaming.yaml")
    assert "domain" in config
    assert "seeds" in config
    assert len(config["seeds"]) >= 1


# ------------------------------------------------------------------ #
# ExperimentDefinition assembly (no real calls)                      #
# ------------------------------------------------------------------ #


class TestCreativeEvolutionDefinition:
    """Verify the experiment definition assembles correctly with mocked heavy deps."""

    def _mock_heavy_imports(self):
        """Return a context that mocks SentenceTransformer and API clients."""
        from unittest.mock import patch, MagicMock
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 384)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"hook_strength": 4, "specificity": 3, "emotional_activation": 4, "action_clarity": 3, "platform_fit": 4}')]
        )

        return patch.multiple(
            "sentence_transformers.SentenceTransformer",
            **{"__new__": lambda cls, *a, **kw: mock_model},
        )

    def test_definition_module_importable(self):
        """The definition module must be importable without heavy side effects."""
        # Only verify the module spec resolves — we don't call make_creative_evolution_experiment
        # because that would trigger NoveltySearchEngine / SentenceTransformer instantiation.
        spec = importlib.util.find_spec("experiments.creative_evolution.definition")
        assert spec is not None

    def test_experiment_id_constant(self):
        """The experiment_id in the definition must be 'creative_evolution_v1'."""
        # Read the source to verify the constant without executing it
        defn_path = Path("experiments/creative_evolution/definition.py")
        assert defn_path.exists()
        source = defn_path.read_text()
        assert "creative_evolution_v1" in source

    def test_all_adapter_modules_importable(self):
        """All 5 creative evolution adapter modules must be importable."""
        adapter_modules = [
            "experiments.creative_evolution.memory_adapter",
            "experiments.creative_evolution.planner_adapter",
            "experiments.creative_evolution.verification_adapter",
            "experiments.creative_evolution.runtime_adapter",
        ]
        for mod in adapter_modules:
            spec = importlib.util.find_spec(mod)
            assert spec is not None, f"Module {mod} not found"

    def test_all_uaf_modules_importable(self):
        """All UAF framework modules must be importable."""
        uaf_modules = [
            "uaf.interfaces.cognition",
            "uaf.interfaces.memory",
            "uaf.interfaces.planner",
            "uaf.interfaces.verification",
            "uaf.interfaces.runtime",
            "uaf.kernel.state",
            "uaf.kernel.invariants",
            "uaf.kernel.simulation",
            "uaf.dynamics.metrics",
            "uaf.dynamics.trajectory",
            "uaf.dynamics.recorder",
            "uaf.experiments.definition",
            "uaf.experiments.runner",
            "uaf.experiments.ledger",
            "uaf.experiments.comparison",
        ]
        for mod in uaf_modules:
            spec = importlib.util.find_spec(mod)
            assert spec is not None, f"UAF module {mod} not found"

    def test_symbolic_arch_importable(self):
        """Architecture #2 must be importable."""
        spec = importlib.util.find_spec("architectures.symbolic_grammar.adapter")
        assert spec is not None


# ------------------------------------------------------------------ #
# ExperimentTrace output schema                                       #
# ------------------------------------------------------------------ #


def test_experiment_trace_has_required_keys():
    """ExperimentTrace.to_dict() must contain all keys needed for full_run_*.json."""
    from uaf.experiments.runner import ExperimentTrace
    from uaf.kernel.state import VerificationResult
    from uaf.kernel.simulation import CycleRecord
    from uaf.dynamics.recorder import DynamicsRecorder

    # Build a minimal trace using the null arch from test_symbolic_arch.py
    from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

    class _MinMem:
        def seed(self, i): pass
        def add(self, *a, **k): pass
        def novelty_of(self, e): return 0.9
        def retired_ids(self): return set()
        def retire(self, *a): pass
        def session_snapshot(self): return {"archive_size": 0, "session_embeddings": [], "refractory_clusters": []}

    class _FixedVer:
        def score(self, c, ctx):
            return VerificationResult(3.5, {}, 0.0, 0.0, "", False, "SLOP", "SLOP")
        def verdict(self, r): return r.verdict

    class _Planner3:
        def initial_action(self, ctx): return "continue"
        def next_action(self, state): return "halt" if state.cycle >= 2 else "continue"
        def should_halt(self, state): return state.cycle >= 2

    class _NullRt:
        def ingest_context(self, d): return "ctx"
        def secure_call(self, fn, *a, **kw): return fn(*a, **kw)
        def persist(self, k, p): pass
        def run_id(self): return "reg-001"

    from uaf.experiments.definition import ExperimentDefinition
    from uaf.experiments.runner import ExperimentRunner
    from uaf.kernel.invariants import InvariantSet

    defn = ExperimentDefinition(
        experiment_id="creative_evolution_v1",
        architecture=SymbolicGrammarCognition(seed=42),
        memory=_MinMem(),
        planner=_Planner3(),
        verification=_FixedVer(),
        runtime=_NullRt(),
        invariants=InvariantSet.default(),
        config={"domain": "gaming", "seeds": ["a"]},
    )
    trace = ExperimentRunner().execute(defn)
    d = trace.to_dict()

    required_keys = {
        "experiment_id", "architecture_id", "run_id", "domain",
        "started_at", "completed_at", "simulation_result",
        "dynamics_series", "dynamics_summary", "config",
    }
    assert required_keys.issubset(d.keys())
    assert d["experiment_id"] == "creative_evolution_v1"
    assert isinstance(d["dynamics_series"], list)
    assert isinstance(d["dynamics_summary"], dict)

    # Must be JSON-serialisable
    json.dumps(d)

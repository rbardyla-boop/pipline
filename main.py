import os
import yaml
import sys


def load_seed_file(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _run_legacy(domain: str, seeds: list) -> None:
    from orchestrator import run
    run(domain=domain, seeds=seeds)


def _run_uaf(domain: str, seeds: list) -> None:
    """UAF_KERNEL=true path — runs via SimulationKernel + ExperimentRunner."""
    import json
    from uaf.experiments.runner import ExperimentRunner
    from uaf.experiments.ledger import ExperimentLedger
    from experiments.creative_evolution.definition import make_creative_evolution_experiment

    defn = make_creative_evolution_experiment(domain=domain, seeds=seeds)
    runner = ExperimentRunner()
    trace = runner.execute(defn)

    # Mirror legacy output format: write full_run_*.json
    from pathlib import Path
    Path("logs/runs").mkdir(parents=True, exist_ok=True)
    run_path = f"logs/runs/full_run_{trace.run_id}.json"
    with open(run_path, "w") as f:
        json.dump(trace.to_dict(), f, indent=2)
    print(f"[UAF] Run complete → {run_path}")
    print(f"[UAF] Best candidate ({trace.simulation_result['best_score']:.2f}): "
          f"{trace.simulation_result['best_candidate'][:80]}...")
    print(f"[UAF] Halt reason: {trace.simulation_result['halt_reason']}")

    # Record to experiment ledger
    ExperimentLedger().record(trace)


if __name__ == "__main__":
    seed_file = sys.argv[1] if len(sys.argv) > 1 else "seeds/gaming.yaml"
    config = load_seed_file(seed_file)
    domain = config["domain"]
    seeds = config["seeds"]

    if os.getenv("UAF_KERNEL", "true").lower() == "true":
        _run_uaf(domain=domain, seeds=seeds)
    else:
        _run_legacy(domain=domain, seeds=seeds)

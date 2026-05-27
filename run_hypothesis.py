"""Runner for hypothesis-driven experiment loops.

Usage:
    .venv/bin/python run_hypothesis.py hypotheses/coherence_diversity_frontier.yaml
    .venv/bin/python run_hypothesis.py hypotheses/attention_heads_experiment.yaml

Loads a Hypothesis YAML, runs ExperimentLoop, and saves the result to
hypotheses/<hypothesis_id>_<timestamp>.json.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from uaf.research.hypothesis import Hypothesis
from uaf.research.loop import ExperimentLoop


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: run_hypothesis.py <hypothesis.yaml>")
        sys.exit(1)

    yaml_path = sys.argv[1]
    hypothesis = Hypothesis.from_yaml(yaml_path)

    print(f"Loaded: {hypothesis.hypothesis_id}")
    print(f"Variants: {[v.variant_id for v in hypothesis.variants]}")
    print(f"Stopping: {hypothesis.stopping_criterion} | max_cycles={hypothesis.max_cycles}")

    loop = ExperimentLoop(max_iterations=5, record_to_ledger=True, verbose=True)
    result = loop.run(hypothesis)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path("hypotheses") / f"{result.hypothesis_id}_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"\nResult saved → {out_path}")
    print(f"Resolved: {result.resolved}")
    if result.resolution:
        print(f"Resolution: {result.resolution}")
    if result.findings:
        print("Findings:")
        for finding in result.findings:
            print(f"  - {finding}")


if __name__ == "__main__":
    main()

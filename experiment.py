"""experiment.py — CLI entry point for the hypothesis-driven discovery loop.

Usage
-----
# Run a hypothesis from a YAML file:
  python experiment.py --file hypotheses/template_complexity.yaml

# Quick one-liner (Claude generates starting variants automatically):
  python experiment.py --question "Does context injection improve score diversity?" \\
      --domain gaming --cycles 3 --iterations 4

# Set target score and stop when hit:
  python experiment.py --file hypotheses/my_hyp.yaml --target 4.3

# Fast mode — heuristic scoring, no Phoenix API calls:
  python experiment.py --file hypotheses/my_hyp.yaml --verification heuristic

# Full Phoenix scoring:
  python experiment.py --file hypotheses/my_hyp.yaml --verification phoenix

# Save final hypothesis state to JSONL ledger:
  python experiment.py --file hypotheses/my_hyp.yaml --save-result
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


# ------------------------------------------------------------------ #
# Auto-generate starting variants via Claude                          #
# ------------------------------------------------------------------ #


def _generate_initial_variants(
    question: str,
    domain: str,
    n_variants: int,
    client,
) -> list[dict]:
    """Ask Claude to design the starting variant set for a new question."""
    param_docs = """Available parameters for arch_type="parametric":
  - template_count: int 1-8 (production pool size)
  - context_injection: bool
  - coherence_mode: "slot_ratio" | "length" | "entropy"
  - embed_strategy: "hash" | "transformer"
  - seed: int"""

    prompt = f"""You are an AI architecture researcher.

Research question: {question}
Domain: {domain}

{param_docs}

Design {n_variants} ParametricCognition variants that form a good starting point
for answering this research question. Space them across the parameter range so
the first iteration gives maximum information.

Respond ONLY with a valid JSON array, no markdown:
[
  {{
    "variant_id": "iter1_v1",
    "description": "baseline — minimal configuration",
    "arch_type": "parametric",
    "params": {{...}}
  }}
]"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ------------------------------------------------------------------ #
# Hypothesis YAML skeleton writer                                     #
# ------------------------------------------------------------------ #


def _write_skeleton(path: str, question: str, domain: str) -> None:
    """Write a hypothesis YAML skeleton the user can edit."""
    skeleton = {
        "hypothesis_id": Path(path).stem,
        "question": question,
        "predicted_outcome": "TODO: what you expect to find",
        "domain": domain,
        "seeds": ["TODO: seed concept A", "TODO: seed concept B"],
        "max_cycles": 3,
        "stopping_criterion": "max_iterations",
        "target_score": 4.3,
        "verification_mode": "heuristic",
        "variants": [
            {
                "variant_id": "iter1_v1",
                "description": "baseline",
                "arch_type": "parametric",
                "params": {"template_count": 4, "context_injection": False, "seed": 42},
            },
            {
                "variant_id": "iter1_v2",
                "description": "with context injection",
                "arch_type": "parametric",
                "params": {"template_count": 4, "context_injection": True, "seed": 42},
            },
            {
                "variant_id": "iter1_v3",
                "description": "full template pool + context injection",
                "arch_type": "parametric",
                "params": {"template_count": 8, "context_injection": True, "seed": 42},
            },
        ],
    }
    with open(path, "w") as f:
        yaml.dump(skeleton, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"[skeleton] Written → {path}")
    print("  Edit the file and re-run with --file to start the experiment.")


# ------------------------------------------------------------------ #
# Result persistence                                                  #
# ------------------------------------------------------------------ #


def _save_result(hypothesis, out_dir: str = "logs/experiments") -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    fname = f"{out_dir}/{hypothesis.hypothesis_id}_final.json"
    with open(fname, "w") as f:
        json.dump(hypothesis.to_dict(), f, indent=2)
    return fname


# ------------------------------------------------------------------ #
# CLI                                                                 #
# ------------------------------------------------------------------ #


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="experiment.py",
        description="Hypothesis-driven AI architecture discovery loop",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--file", "-f", metavar="YAML", help="Hypothesis YAML file")
    src.add_argument(
        "--question", "-q", metavar="Q",
        help="Research question (auto-generates starting variants)",
    )
    src.add_argument(
        "--skeleton", metavar="PATH",
        help="Write a hypothesis YAML skeleton and exit",
    )

    p.add_argument("--domain", "-d", default="gaming",
                   help="Seed domain (default: gaming)")
    p.add_argument("--seeds", metavar="S1,S2,...",
                   help="Comma-separated seed concepts (overrides YAML)")
    p.add_argument("--cycles", "-c", type=int, default=3,
                   help="Simulation cycles per variant (default: 3)")
    p.add_argument("--iterations", "-i", type=int, default=4,
                   help="Max discovery loop iterations (default: 4)")
    p.add_argument("--variants", "-n", type=int, default=3,
                   help="Starting variants when using --question (default: 3)")
    p.add_argument("--target", "-t", type=float, default=None,
                   help="Stop when best score >= target (overrides YAML)")
    p.add_argument(
        "--stopping", choices=["max_iterations", "score_threshold", "hypothesis_confirmed"],
        default=None, help="Stopping criterion (overrides YAML)",
    )
    p.add_argument(
        "--verification", choices=["heuristic", "phoenix"], default=None,
        help="Verification mode: heuristic (free) | phoenix (real API, overrides YAML)",
    )
    p.add_argument("--save-result", action="store_true",
                   help="Write final hypothesis state to logs/experiments/")
    p.add_argument("--no-ledger", action="store_true",
                   help="Do not record traces to experiment ledger")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ── skeleton writer ──────────────────────────────────────────────
    if args.skeleton:
        _write_skeleton(args.skeleton, args.question or "Your research question here", args.domain)
        return

    # ── build hypothesis ─────────────────────────────────────────────
    if args.file:
        from uaf.research.hypothesis import Hypothesis
        hypothesis = Hypothesis.from_yaml(args.file)

    elif args.question:
        from uaf.research.hypothesis import Hypothesis, VariantSpec
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        seeds_raw = args.seeds or "a mystery game where memory works backwards,a survival game where sacrifice is the economy,a horror game with procedurally generated grief"
        seeds = [s.strip() for s in seeds_raw.split(",")]

        print(f"[init] Generating {args.variants} starting variants for: {args.question!r}")
        variants_data = _generate_initial_variants(args.question, args.domain, args.variants, client)
        variants = [VariantSpec.from_dict(v) for v in variants_data]

        hypothesis = Hypothesis(
            hypothesis_id=f"auto_{abs(hash(args.question)) % 100000:05d}",
            question=args.question,
            predicted_outcome="To be discovered by the loop",
            domain=args.domain,
            seeds=seeds,
            variants=variants,
            max_cycles=args.cycles,
            stopping_criterion=args.stopping or "max_iterations",
            target_score=args.target or 4.5,
            verification_mode=args.verification or "heuristic",
        )
    else:
        parser.print_help()
        sys.exit(0)

    # ── apply CLI overrides ──────────────────────────────────────────
    if args.cycles:
        hypothesis.max_cycles = args.cycles
    if args.target is not None:
        hypothesis.target_score = args.target
        hypothesis.stopping_criterion = "score_threshold"
    if args.stopping:
        hypothesis.stopping_criterion = args.stopping
    if args.verification:
        hypothesis.verification_mode = args.verification
    if args.seeds:
        hypothesis.seeds = [s.strip() for s in args.seeds.split(",")]

    # ── run the loop ─────────────────────────────────────────────────
    from uaf.research.loop import ExperimentLoop
    loop = ExperimentLoop(
        max_iterations=args.iterations,
        record_to_ledger=not args.no_ledger,
        verbose=True,
    )
    final = loop.run(hypothesis)

    # ── persist result ───────────────────────────────────────────────
    if args.save_result:
        path = _save_result(final)
        print(f"\n[saved] {path}")

    # ── summary ──────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(f"  EXPERIMENT COMPLETE")
    print(f"  Question:    {final.question}")
    print(f"  Resolution:  {final.resolution}")
    print(f"  Best score:  {final.best_score_so_far():.2f}")
    print(f"  Iterations:  {final.iteration}")
    if final.findings:
        print(f"\n  Findings:")
        for f in final.findings:
            print(f"    {f}")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()

"""
tols/cli.py
Command-line interface: python -m tols.cli --experiment 1 --seed 42
"""

import argparse
import json
import sys
import os
from .experiments import run_faithful_rate, run_basin_radius


def main():
    parser = argparse.ArgumentParser(description="TOLS v3 CLI")
    parser.add_argument("--experiment", type=int, choices=[1, 2], required=True,
                        help="1=K_eff ablation faithful rate, 2=basin radius sweep")
    parser.add_argument("--P", type=int, default=16, help="Number of patterns")
    parser.add_argument("--N", type=int, default=32, help="Number of oscillators")
    parser.add_argument("--D", type=int, default=8, help="Pattern dimension")
    parser.add_argument("--K", type=float, default=4.0, help="Base coupling strength")
    parser.add_argument("--adaptive-K", action="store_true", default=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-json", type=str, default=None,
                        help="Write results dict to this JSON file")
    args = parser.parse_args()

    if args.experiment == 1:
        result = run_faithful_rate(
            P=args.P, N=args.N, D=args.D, base_K=args.K,
            adaptive_K=args.adaptive_K, seed=args.seed
        )
    elif args.experiment == 2:
        result = run_basin_radius(
            P=args.P, N=args.N, D=args.D, base_K=args.K,
            adaptive_K=args.adaptive_K, seed=args.seed
        )

    print(json.dumps(result, indent=2))

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output_json}")


if __name__ == "__main__":
    main()

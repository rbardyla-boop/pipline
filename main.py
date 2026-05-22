import yaml
import sys
from orchestrator import run


def load_seed_file(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    seed_file = sys.argv[1] if len(sys.argv) > 1 else "seeds/gaming.yaml"
    config = load_seed_file(seed_file)
    run(domain=config["domain"], seeds=config["seeds"])

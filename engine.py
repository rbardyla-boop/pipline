import os
import json
import random
import time
import hashlib
import numpy as np
import anthropic as _anthropic
from anthropic._exceptions import OverloadedError as _OverloadedError
from typing import List, Dict, Any, Optional, Set
from sentence_transformers import SentenceTransformer
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from security.firewall import LlamaFirewallClient

load_dotenv()


def write_terminal_archive(concept: str, phoenix_score: float, combined: float, run_id: str):
    """Permanently retire a concept. Module-level so callers don't need the embedding model."""
    terminal_path = os.getenv("TERMINAL_ARCHIVE_PATH", "logs/terminal_archive.json")
    Path("logs").mkdir(exist_ok=True)
    entries = []
    try:
        with open(terminal_path) as f:
            entries = json.load(f)
    except FileNotFoundError:
        pass
    concept_hash = hashlib.sha256(concept.encode()).hexdigest()[:16]
    if any(e["concept_hash"] == concept_hash for e in entries):
        return
    entries.append({
        "concept_hash": concept_hash,
        "concept_preview": concept[:120] + "...",
        "phoenix_score": phoenix_score,
        "combined": combined,
        "run_id": run_id,
        "retired_at": datetime.now().strftime("%Y%m%d_%H%M%S")
    })
    with open(terminal_path, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"[TERMINAL] Concept permanently retired (Phoenix {phoenix_score:.2f}, combined {combined:.3f})")


def _call_with_retry(client, max_retries: int = 8, base_delay: float = 5.0, **kwargs):
    for attempt in range(max_retries):
        try:
            return client.messages.create(**kwargs)
        except (_anthropic.RateLimitError, _OverloadedError) as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), 60.0)
            print(f"[RETRY] {type(e).__name__} — waiting {delay:.0f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(delay)


class NoveltySearchEngine:
    def __init__(self):
        self.model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        self.client = LlamaFirewallClient()
        self.threshold = float(os.getenv("NOVELTY_THRESHOLD", 0.68))
        self.max_archive = int(os.getenv("ARCHIVE_MAX", 500))
        self.archive: List[Dict[str, Any]] = []

    def embed(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True)

    def cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(1.0 - np.dot(a, b))

    def novelty_score(self, candidate_emb: np.ndarray) -> float:
        if not self.archive:
            return 1.0
        distances = [self.cosine_distance(candidate_emb, item["embedding"])
                     for item in self.archive]
        return float(min(distances))

    def seed_archive(self, seeds: List[str]):
        for seed in seeds:
            emb = self.embed(seed)
            self.archive.append({
                "concept": seed,
                "embedding": emb,
                "generation": 0,
                "novelty": 1.0
            })
        print(f"[ENGINE] Archive seeded with {len(seeds)} concepts.")

    def mutate(self, parent: str, zeitgeist_context: str) -> str:
        prompt = f"""You are a creative extrapolation engine. Your job is to mutate the following concept OUTSIDE its existing genre conventions.

PARENT CONCEPT:
{parent}

LIVE 2026 CULTURAL CONTEXT (inject these fractures):
{zeitgeist_context}

HARD RULES:
1. Violate at least one core convention of the parent concept's domain.
2. Directly address at least two fractures from the 2026 context.
3. Apply SATS framing: write the mutation as if it already exists and is inevitable.
4. Output ONLY the mutated concept. No preamble. No explanation. One paragraph max.

MUTATED CONCEPT:"""

        response = _call_with_retry(
            self.client,
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    def coherence_score(self, candidate: str) -> float:
        prompt = f"""Rate this concept's internal logical coherence on a scale of 0.0 to 1.0.
0.0 = complete nonsense, no internal logic
1.0 = perfectly coherent, could exist as a real product/story/game

Concept: {candidate}

Output ONLY a decimal number between 0.0 and 1.0. Nothing else."""

        response = _call_with_retry(
            self.client,
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            return float(response.content[0].text.strip())
        except ValueError:
            return 0.5

    def prune_archive(self):
        if len(self.archive) > self.max_archive:
            self.archive.sort(key=lambda x: x["novelty"], reverse=True)
            self.archive = self.archive[:self.max_archive]

    def apply_entropy(self):
        if not self.archive:
            return
        max_gen = max(e["generation"] for e in self.archive)
        if max_gen == 0:
            return
        decay_rate = float(os.getenv("ENTROPY_DECAY_RATE", "0.05"))
        for entry in self.archive:
            age = max_gen - entry["generation"]
            decay = max(0.1, 1.0 - (age * decay_rate))
            entry["novelty"] = round(entry["novelty"] * decay, 4)
        self.prune_archive()

    def load_terminal_archive(self) -> Set[str]:
        terminal_path = os.getenv("TERMINAL_ARCHIVE_PATH", "logs/terminal_archive.json")
        try:
            with open(terminal_path) as f:
                return {e["concept_hash"] for e in json.load(f)}
        except FileNotFoundError:
            return set()

    def write_terminal_archive(self, concept: str, phoenix_score: float, combined: float, run_id: str):
        terminal_path = os.getenv("TERMINAL_ARCHIVE_PATH", "logs/terminal_archive.json")
        Path("logs").mkdir(exist_ok=True)
        entries = []
        try:
            with open(terminal_path) as f:
                entries = json.load(f)
        except FileNotFoundError:
            pass
        concept_hash = hashlib.sha256(concept.encode()).hexdigest()[:16]
        entries.append({
            "concept_hash": concept_hash,
            "concept_preview": concept[:120] + "...",
            "phoenix_score": phoenix_score,
            "combined": combined,
            "run_id": run_id,
            "retired_at": datetime.now().strftime("%Y%m%d_%H%M%S")
        })
        with open(terminal_path, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"[TERMINAL] Concept permanently retired (Phoenix {phoenix_score:.2f}, combined {combined:.3f})")

    def evolve(
        self,
        zeitgeist_context: str,
        generations: int = 10,
        variants_per_gen: int = 8,
        top_k_parents: int = 3
    ) -> List[Dict]:
        results = []
        terminal_hashes = self.load_terminal_archive()

        for gen in range(generations):
            if gen > 0:
                self.apply_entropy()

            gen_results = []
            eligible = [
                p for p in sorted(self.archive, key=lambda x: x["novelty"], reverse=True)
                if hashlib.sha256(p["concept"].encode()).hexdigest()[:16] not in terminal_hashes
            ]
            parents = eligible[:top_k_parents] or sorted(
                self.archive, key=lambda x: x["novelty"], reverse=True
            )[:top_k_parents]

            print(f"[GEN {gen+1}/{generations}] Running {variants_per_gen} mutations...")

            for v in range(variants_per_gen):
                parent = random.choice(parents)["concept"]
                try:
                    candidate = self.mutate(parent, zeitgeist_context)
                    coherence = self.coherence_score(candidate)
                except (_anthropic.RateLimitError, _OverloadedError) as e:
                    print(f"  Variant {v+1}: SKIPPED — {type(e).__name__} after all retries")
                    continue
                emb = self.embed(candidate)
                novelty = self.novelty_score(emb)
                combined = novelty * coherence

                entry = {
                    "generation": gen + 1,
                    "variant": v + 1,
                    "parent": parent[:80] + "...",
                    "candidate": candidate,
                    "novelty": round(novelty, 4),
                    "coherence": round(coherence, 4),
                    "combined": round(combined, 4),
                    "archived": False
                }

                if novelty > self.threshold:
                    self.archive.append({
                        "concept": candidate,
                        "embedding": emb,
                        "generation": gen + 1,
                        "novelty": novelty
                    })
                    entry["archived"] = True
                    self.prune_archive()

                gen_results.append(entry)
                print(f"  Variant {v+1}: novelty={novelty:.3f} coherence={coherence:.3f} combined={combined:.3f}")

            results.extend(sorted(gen_results, key=lambda x: x["combined"], reverse=True)[:3])

        return sorted(results, key=lambda x: x["combined"], reverse=True)[:15]

    def save_run(self, results: List[Dict], domain: str) -> str:
        Path("logs/runs").mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"logs/runs/{domain}_{timestamp}.json"
        with open(filepath, "w") as f:
            json.dump({
                "domain": domain,
                "timestamp": timestamp,
                "archive_size": len(self.archive),
                "top_results": results
            }, f, indent=2)
        print(f"[ENGINE] Run saved → {filepath}")
        return filepath

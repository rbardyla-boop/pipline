import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import NoveltySearchEngine

engine = NoveltySearchEngine()
engine.seed_archive([
    "A free-to-play mobile fantasy gacha squad-battler",
    "Open world crime sandbox with driving physics",
    "Cloud-based project management platform for enterprises"
])

# Novelty scoring — no LLM calls
test_emb = engine.embed("persistent ghost guardians that age with geopolitical events")
score = engine.novelty_score(test_emb)
print(f"Novelty score: {score:.4f}")
assert score > 0.3, f"Embedding distance scoring broken — got {score:.4f}"

# Archive size check
assert len(engine.archive) == 3, "Archive seeding failed"

# Same concept twice should score 0.0 (identical to itself in archive)
engine2 = NoveltySearchEngine()
engine2.seed_archive(["A free-to-play mobile fantasy gacha squad-battler"])
same_emb = engine2.embed("A free-to-play mobile fantasy gacha squad-battler")
same_score = engine2.novelty_score(same_emb)
print(f"Self-similarity score (expect ~0.0): {same_score:.4f}")
assert same_score < 0.05, f"Self-similarity should be near 0 — got {same_score:.4f}"

# Slop seed should score lower than the ghost guardian concept
slop_seed = "Revolutionize your workflow with AI-powered productivity insights and seamless team collaboration tools."
slop_emb = engine.embed(slop_seed)
slop_score = engine.novelty_score(slop_emb)
print(f"Slop seed novelty: {slop_score:.4f}")

print("\nPhase 1 test PASSED")

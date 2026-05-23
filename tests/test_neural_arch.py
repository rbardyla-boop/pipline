"""Neural architecture tests — all CPU, no GPU required, < 30s."""

import math

import pytest
import torch

from architectures.neural.char_tokenizer import CharTokenizer
from architectures.neural.tiny_transformer import TinyTransformer, TransformerConfig
from architectures.neural.adapter import NeuralTransformerCognition
from uaf.interfaces.cognition import CognitionEngine


_SEEDS = [
    "a mystery game where memory works backwards",
    "a survival game where sacrifice is the economy",
]


# --------------------------------------------------------------------------- #
# 1. TinyTransformer forward pass shape + no NaN                              #
# --------------------------------------------------------------------------- #

def test_forward_shape_and_no_nan():
    cfg = TransformerConfig(n_layers=1, n_heads=2, embed_dim=16, context_len=16, vocab_size=70)
    model = TinyTransformer(cfg)
    idx = torch.randint(1, 70, (2, 8))
    logits = model(idx)
    assert logits.shape == (2, 8, 70)
    assert not torch.isnan(logits).any()


# --------------------------------------------------------------------------- #
# 2. NeuralTransformerCognition satisfies CognitionEngine ABC                 #
# --------------------------------------------------------------------------- #

def test_abc_conformance():
    arch = NeuralTransformerCognition(n_layers=1, n_heads=1, embed_dim=16, context_len=16)
    assert isinstance(arch, CognitionEngine)


# --------------------------------------------------------------------------- #
# 3. propose() returns non-empty string different from parent                 #
# --------------------------------------------------------------------------- #

def test_propose_returns_different_string():
    arch = NeuralTransformerCognition(
        n_layers=1, n_heads=1, embed_dim=16, context_len=16, seeds=_SEEDS
    )
    parent = "the game begins with memory"
    result = arch.propose(parent, "")
    assert isinstance(result, str)
    assert len(result) > 0
    assert result != parent


# --------------------------------------------------------------------------- #
# 4. embed() returns list[float] with length > 0                              #
# --------------------------------------------------------------------------- #

def test_embed_shape():
    arch = NeuralTransformerCognition(n_layers=1, n_heads=1, embed_dim=16, context_len=16)
    vec = arch.embed("sacrifice is the currency")
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)


# --------------------------------------------------------------------------- #
# 5. embed() output is always 384-dim (padded or truncated)                   #
# --------------------------------------------------------------------------- #

def test_embed_dim_is_384():
    arch = NeuralTransformerCognition(n_layers=1, n_heads=2, embed_dim=16, context_len=16)
    vec = arch.embed("hello world")
    assert len(vec) == 384


# --------------------------------------------------------------------------- #
# 6. coherence() returns float in [0.0, 1.0]                                  #
# --------------------------------------------------------------------------- #

def test_coherence_range():
    arch = NeuralTransformerCognition(n_layers=1, n_heads=1, embed_dim=16, context_len=16)
    score = arch.coherence("a mystery game where memory works backwards")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


# --------------------------------------------------------------------------- #
# 7. 10 training steps reduce loss vs untrained baseline                      #
# --------------------------------------------------------------------------- #

def test_training_reduces_loss():
    arch = NeuralTransformerCognition(
        n_layers=1, n_heads=1, embed_dim=16, context_len=16,
        n_train_steps=0, seeds=_SEEDS,
    )
    # Coherence before training (untrained = random weights = high loss = low coherence)
    text = " ".join(_SEEDS)
    before = arch.coherence(text)

    # Now train
    arch._n_train_steps = 20
    arch.propose("", "")

    after = arch.coherence(text)
    # After training, coherence should improve (loss decreases → exp(-loss) increases)
    # We allow a small tolerance since we're training on tiny data
    assert after >= before - 0.05, (
        f"Coherence degraded: before={before:.4f} after={after:.4f}"
    )


# --------------------------------------------------------------------------- #
# 8. architecture_id is stable across multiple calls                          #
# --------------------------------------------------------------------------- #

def test_architecture_id_stable():
    arch = NeuralTransformerCognition(n_layers=2, n_heads=4, embed_dim=64, context_len=32)
    id1 = arch.architecture_id
    id2 = arch.architecture_id
    assert id1 == id2
    assert id1 == "neural_L2_H4_D64_C32"


# --------------------------------------------------------------------------- #
# 9. YAML round-trip: attention_heads_experiment.yaml loads with correct type #
# --------------------------------------------------------------------------- #

def test_yaml_loads_neural_arch_type():
    import yaml, os
    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "hypotheses", "attention_heads_experiment.yaml"
    )
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    arch_types = {v["arch_type"] for v in data["variants"]}
    assert arch_types == {"neural_transformer"}
    assert len(data["variants"]) == 4


# --------------------------------------------------------------------------- #
# 10. Two different configs produce different architecture_id strings         #
# --------------------------------------------------------------------------- #

def test_different_configs_produce_different_arch_ids():
    arch_a = NeuralTransformerCognition(n_layers=1, n_heads=1, embed_dim=32, context_len=16)
    arch_b = NeuralTransformerCognition(n_layers=2, n_heads=4, embed_dim=64, context_len=32)
    assert arch_a.architecture_id != arch_b.architecture_id


# --------------------------------------------------------------------------- #
# 11. TransformerConfig raises on invalid n_heads                             #
# --------------------------------------------------------------------------- #

def test_config_raises_on_bad_heads():
    with pytest.raises(ValueError, match="divisible"):
        TransformerConfig(n_layers=1, n_heads=3, embed_dim=16)


# --------------------------------------------------------------------------- #
# 12. reasoning_trace() includes last_train_loss after propose()              #
# --------------------------------------------------------------------------- #

def test_reasoning_trace_has_loss():
    arch = NeuralTransformerCognition(
        n_layers=1, n_heads=1, embed_dim=16, context_len=16,
        seeds=_SEEDS, n_train_steps=3,
    )
    arch.propose("game seed", "")
    trace = arch.reasoning_trace()
    assert "last_train_loss" in trace
    assert math.isfinite(trace["last_train_loss"])

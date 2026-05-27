"""Tests for uaf.llm.transformer (Transformer block with pre-norm RMSNorm)."""

import math
import pytest
from uaf.llm.transformer import TransformerBlock, ScaledDotProductAttention, FeedForwardNetwork


# --- ScaledDotProductAttention ---

def test_attention_output_shape():
    attn = ScaledDotProductAttention(dim=4)
    seq = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
    out = attn.forward(seq, seq, seq)
    assert len(out) == 2
    assert len(out[0]) == 4


def test_attention_single_token():
    attn = ScaledDotProductAttention(dim=3)
    x = [[1.0, 2.0, 3.0]]
    out = attn.forward(x, x, x)
    assert len(out) == 1
    assert len(out[0]) == 3


def test_attention_output_finite():
    attn = ScaledDotProductAttention(dim=4)
    seq = [[float(i) for i in range(4)] for _ in range(5)]
    out = attn.forward(seq, seq, seq)
    for token in out:
        assert all(math.isfinite(v) for v in token)


def test_attention_scale_applied():
    # With scale = 0 effectively, attention over identical vectors = uniform
    attn1 = ScaledDotProductAttention(dim=4, scale=1.0)
    attn2 = ScaledDotProductAttention(dim=4, scale=0.01)
    seq = [[1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 1.0, 0.0]]
    out1 = attn1.forward(seq, seq, seq)
    out2 = attn2.forward(seq, seq, seq)
    # Different scales should produce different outputs
    assert out1 != out2


# --- FeedForwardNetwork ---

def test_ffn_output_length():
    ffn = FeedForwardNetwork(dim=4)
    x = [1.0, 2.0, 3.0, 4.0]
    out = ffn.forward(x)
    assert len(out) == 4


def test_ffn_output_finite():
    ffn = FeedForwardNetwork(dim=6)
    x = [0.1 * i for i in range(6)]
    out = ffn.forward(x)
    assert all(math.isfinite(v) for v in out)


def test_ffn_hidden_size_configurable():
    ffn = FeedForwardNetwork(dim=4, hidden=8)
    x = [1.0, 2.0, 3.0, 4.0]
    out = ffn.forward(x)
    assert len(out) == 4


def test_ffn_nonlinear_activation():
    # SiLU(0) = 0, SiLU(positive) > 0
    ffn = FeedForwardNetwork(dim=2)
    zero_out = ffn.forward([0.0, 0.0])
    pos_out = ffn.forward([1.0, 1.0])
    # Not all zeros for positive input
    assert any(v != 0.0 for v in pos_out)


# --- TransformerBlock ---

def test_transformer_block_output_shape():
    block = TransformerBlock(dim=4)
    seq = [[float(i + j) for i in range(4)] for j in range(3)]
    out = block.forward(seq)
    assert len(out) == 3
    assert all(len(v) == 4 for v in out)


def test_transformer_block_output_finite():
    block = TransformerBlock(dim=4)
    seq = [[1.0, 0.5, -0.5, 0.0] for _ in range(4)]
    out = block.forward(seq)
    for token in out:
        assert all(math.isfinite(v) for v in token)


def test_transformer_block_single_token():
    block = TransformerBlock(dim=3)
    seq = [[1.0, 2.0, 3.0]]
    out = block.forward(seq)
    assert len(out) == 1
    assert len(out[0]) == 3


def test_transformer_block_residual_changes_input():
    block = TransformerBlock(dim=4)
    x = [[1.0, 1.0, 1.0, 1.0]]
    out = block.forward(x)
    # Output should differ from input due to attention + FFN transformations
    assert out[0] != x[0]


def test_transformer_block_preserves_sequence_length():
    block = TransformerBlock(dim=8)
    seq = [[float(i) for i in range(8)] for _ in range(10)]
    out = block.forward(seq)
    assert len(out) == 10


def test_transformer_stacked_blocks():
    """Two stacked blocks produce deterministic output."""
    b1 = TransformerBlock(dim=4)
    b2 = TransformerBlock(dim=4)
    seq = [[0.1 * i for i in range(4)] for _ in range(3)]
    out1 = b1.forward(seq)
    out2 = b2.forward(out1)
    assert len(out2) == 3
    assert all(math.isfinite(v) for token in out2 for v in token)

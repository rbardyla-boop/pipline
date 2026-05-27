"""Tests for uaf.llm.rms_norm (from LLM architecture guide)."""

import math
import pytest
from uaf.llm.rms_norm import RMSNorm


def test_rms_value_matches_manual():
    norm = RMSNorm(dim=4)
    x = [2.0, 4.0, 4.0, 8.0]
    rms = norm.rms(x)
    # Manual: sqrt((4+16+16+64)/4 + eps) = sqrt(25 + eps) ≈ 5
    assert abs(rms - 5.0) < 0.01


def test_forward_scales_by_rms():
    norm = RMSNorm(dim=4)
    x = [2.0, 4.0, 4.0, 8.0]
    result = norm.forward(x)
    rms = math.sqrt(sum(xi ** 2 for xi in x) / 4 + 1e-6)
    expected = [xi / rms for xi in x]
    for r, e in zip(result, expected):
        assert abs(r - e) < 1e-5


def test_forward_with_nonunit_gamma():
    gamma = [2.0, 2.0, 2.0, 2.0]
    norm = RMSNorm(dim=4, gamma=gamma)
    x = [1.0, 1.0, 1.0, 1.0]
    result = norm.forward(x)
    # All inputs equal → RMS = 1 (+ eps) → result ≈ gamma * 1 = 2
    assert all(abs(r - 2.0) < 0.01 for r in result)


def test_wrong_input_length_raises():
    norm = RMSNorm(dim=4)
    with pytest.raises(ValueError, match="length"):
        norm.forward([1.0, 2.0])


def test_wrong_gamma_length_raises():
    with pytest.raises(ValueError, match="gamma length"):
        RMSNorm(dim=4, gamma=[1.0, 1.0])


def test_epsilon_prevents_zero_division():
    norm = RMSNorm(dim=3, eps=1e-6)
    x = [0.0, 0.0, 0.0]
    result = norm.forward(x)
    assert all(math.isfinite(r) for r in result)


def test_output_length_equals_input():
    norm = RMSNorm(dim=5)
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = norm.forward(x)
    assert len(result) == 5


def test_normalization_reduces_large_values():
    norm = RMSNorm(dim=3)
    x = [1000.0, 2000.0, 3000.0]
    result = norm.forward(x)
    # After normalization, values should be much smaller
    assert all(abs(r) < 10.0 for r in result)


def test_layernorm_baseline_centers_output():
    x = [1.0, 2.0, 3.0, 4.0]
    result = RMSNorm.layernorm_baseline(x)
    mean = sum(result) / len(result)
    assert abs(mean) < 1e-5  # LayerNorm centers around zero


def test_rmsnorm_output_not_necessarily_zero_mean():
    norm = RMSNorm(dim=4)
    x = [1.0, 2.0, 3.0, 4.0]
    result = norm.forward(x)
    mean = sum(result) / len(result)
    # RMSNorm does NOT subtract mean, so mean != 0 for non-uniform input
    assert abs(mean) > 0.01


def test_idempotent_for_unit_rms_input():
    # If RMS of x is ~1, output ≈ gamma * x ≈ x (with gamma=1)
    norm = RMSNorm(dim=3)
    # x = [1, 1, 1] → RMS = 1
    x = [1.0, 1.0, 1.0]
    result = norm.forward(x)
    # Each value should be ~1 * 1 / 1 = ~1
    assert all(abs(r - 1.0) < 0.01 for r in result)


def test_default_gamma_is_ones():
    norm = RMSNorm(dim=3)
    assert norm.gamma == [1.0, 1.0, 1.0]

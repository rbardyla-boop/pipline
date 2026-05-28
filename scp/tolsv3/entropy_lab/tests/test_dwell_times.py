"""
Falsification tests for entropy_lab.dwell_times (Part XVII).
"""

import numpy as np
import pytest

from entropy_lab.dwell_times import DwellStats, extract_dwell_times, fit_dwell_distribution


# ---------------------------------------------------------------------------
# Test 1: single crossing — segment lengths are correct
# ---------------------------------------------------------------------------

def test_extract_single_crossing():
    """[+1, +1, +1, -1, -1] has one crossing -> two dwells of length 3 and 2."""
    phi = [1.0, 1.0, 1.0, -1.0, -1.0]
    dts = extract_dwell_times(phi)
    assert dts == [3, 2], f"expected [3, 2], got {dts}"


def test_extract_no_crossings():
    """All positive -> one dwell spanning the entire series."""
    phi = [1.0] * 10
    dts = extract_dwell_times(phi)
    assert dts == [10], f"expected [10], got {dts}"


def test_extract_zeros_inherit_sign():
    """Zeros forward-fill from the last non-zero sign.

    [+1, +1, 0, 0, -1]: zeros fill to +1 -> crossing at index 4 -> [4, 1].
    """
    phi = [1.0, 1.0, 0.0, 0.0, -1.0]
    dts = extract_dwell_times(phi)
    assert dts == [4, 1], f"expected [4, 1], got {dts}"


# ---------------------------------------------------------------------------
# Test 2: insufficient data gate
# ---------------------------------------------------------------------------

def test_fit_insufficient_data():
    """fit_dwell_distribution returns 'insufficient_data' for fewer than 5 dwells."""
    result = fit_dwell_distribution([5, 3, 7])
    assert result.fit_type == "insufficient_data", (
        f"expected insufficient_data, got {result.fit_type}"
    )
    assert result.fit_r2 is None


# ---------------------------------------------------------------------------
# Test 3: exponential distribution is detected as exponential
# ---------------------------------------------------------------------------

def test_fit_geometric_is_exponential():
    """Geometric(p=0.1) distribution should be classified as exponential.

    Geometric is the discrete exponential with lambda=p=0.1 -> mean=10.
    Use 2000 samples for stable histogram.
    """
    rng = np.random.default_rng(0)
    dts = rng.geometric(p=0.1, size=2000).tolist()
    result = fit_dwell_distribution(dts)
    assert result.fit_type == "exponential", (
        f"expected exponential, got {result.fit_type}"
    )
    if result.fit_params:
        lam_est = result.fit_params[0]
        assert abs(lam_est - 0.1) < 0.02, (
            f"lambda estimate {lam_est:.4f} too far from 0.1"
        )

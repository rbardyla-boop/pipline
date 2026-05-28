from __future__ import annotations

import numpy as np

# Agents beyond this distance repel instead of attract.
_REPULSION_DISTANCE: float = 0.8


def compute_coupling_matrix(
    mass: np.ndarray,
    x: np.ndarray,
    M_total: float,
) -> np.ndarray:
    """
    k_ij = M_i * M_j / M_total  (mass-weighted spring constant).
    Sign flips to -0.5 * k_ij (repulsion) when |x_i - x_j| > _REPULSION_DISTANCE.
    Diagonal is zero (no self-coupling).
    """
    dist = np.abs(x[:, None] - x[None, :])
    k = np.outer(mass, mass) / M_total
    k[dist > _REPULSION_DISTANCE] *= -0.5
    np.fill_diagonal(k, 0.0)
    return k


def compute_forces(
    x: np.ndarray,
    coupling: np.ndarray,
    k_conf: float = 2.0,
) -> np.ndarray:
    """Conservative spring force plus harmonic confining well.

    F_i = -∂V/∂x_i = -Σ_j k_ij (x_i - x_j) - k_conf * x_i

    The confining term prevents unbounded position growth caused by the
    repulsion branch of the coupling (agents beyond the attraction radius repel
    each other with force that grows linearly with separation).  Without
    confinement the system diverges numerically regardless of dt.  Physically
    the well represents the finite capacity of the attention space.
    """
    dx = x[:, None] - x[None, :]   # (n, n), dx[i,j] = x_i - x_j
    spring = -(coupling * dx).sum(axis=1)
    confining = -k_conf * x
    return spring + confining


def compute_kinetic(mass: np.ndarray, p: np.ndarray) -> float:
    """T = Σ_i ½ M_i p_i²"""
    return float(0.5 * (mass * p ** 2).sum())


def compute_potential(
    x: np.ndarray,
    coupling: np.ndarray,
    k_conf: float = 0.0,
) -> float:
    """V = ½ Σ_{i,j} k_ij (x_i - x_j)² + ½ k_conf Σ_i x_i²

    Including the confining well makes H the true conserved quantity for
    conservative dynamics (γ=0, no concept force), preventing false RUNAWAY
    detections when confining-well energy converts to kinetic energy.
    """
    dx = x[:, None] - x[None, :]
    V_spring = 0.5 * (coupling * dx ** 2).sum()
    V_conf = 0.5 * k_conf * (x ** 2).sum()
    return float(V_spring + V_conf)


def compute_hamiltonian(
    mass: np.ndarray,
    x: np.ndarray,
    p: np.ndarray,
    coupling: np.ndarray,
    k_conf: float = 0.0,
) -> float:
    return compute_kinetic(mass, p) + compute_potential(x, coupling, k_conf)

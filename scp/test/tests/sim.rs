// Simulation invariants (Phase 26):
//   k=n sampling reveals all providers in every query: rate=1.0 per provider, κ=1.0.
//   κ(t) decreases toward 0 as uniform k=1 samples accumulate (entropy recovery).
//   cooldown(Duration::MAX) → total_rotations = 0 regardless of policy sensitivity.
//   IntegralTriggered rotation rate is inversely proportional to threshold.
//   Simulation trace length equals number of run_epoch() calls.
//
// Phase 27 invariants (trajectory analysis):
//   kappa_slope() < 0 when κ is falling (convergence). 0 when flat. > 0 when rising.
//   pressure_budget(t) = fraction of epochs with κ > t. Decreasing in t.
//   pressure_budget(0.0) = 1.0 when κ > 0 always; pressure_budget(1.0) = 0.0 always.
//   Under natural sampling with no rotation, both slope < 0 and budget fall over time.
//   Zero samples per epoch → κ = 1.0 always → budget(0.5) = 1.0 (no evidence of diversity).
//
// Phase 28 invariants (stability polytope):
//   smoothed_kappa lags raw kappa after bursts: kappa - smoothed_kappa > 0 on burst epochs.
//   stability_margin() > 0 ↔ system inside polytope. < 0 ↔ collapse trajectory active.
//   margin_t1() < 0 when pressure_budget(0.5) + kappa_slope_penalty > 1.0.
//   margin_t2() < 0 when rotation_rate > 0.5 (thrashing boundary).
//   margin_t3() < 0 when ewma_lag > 0.3 (burst invisible to EWMA-gated policies).
//   k=n collapses the T1 boundary (κ=1.0 always, budget(0.5)=1.0, margin_t1→ -1.0).
//
// Phase 29 invariants (T4 surface and epoch lifecycle):
//   margin_t4() = (total_samples / (4*active_n) - 1).clamp(-1, 1).
//   margin_t4() < 0 when total_samples < 4*active_n (initialization window open).
//   EpochPhase: PostReset < active_n < Reconverging < 4*active_n < Steady.
//   Phase transitions are monotone — no regression without rotation.
//   Fresh pool (0 samples): T4 is binding constraint; T3 is not active (no EWMA lag).
//   stability_margin() = min(T1, T2, T3, T4) — 4-surface polytope.
//
// Phase 30 invariants (T4 admissibility gate):
//   maybe_rotate() returns RotationOutcome — explicit Rotated or Deferred(reason).
//   PostReset: all policies → Deferred(EstimatorNotConverged). No state mutation.
//   Reconverging: estimator-dependent → Deferred(EstimatorNotConverged).
//   Reconverging: QueryCount/TimeBased/Hybrid/JitteredTimeBased/Manual → admissible.
//   Steady: all policies admissible; T4 gate does not fire.
//   Gate precedes policy arm: IntegralTriggered does not accumulate during PostReset.
//
// Phase 36 invariants (stability polytope surfaces):
//   kappa_displacement_since_rotation() is a zero-cost alias for kappa_velocity.
//   steady_stability_margin() returns None when no Steady epochs exist in the trace.
//   Neutral baseline (Manual, Never, 8/4 pool) lies inside polytope: steady_margin > 0.
//   Bias sweep (QC(100) → QC(10) → QC(1)): steady margin degrades monotonically.
//   Orthogonal thrash setup (QC(1)+Never, 8/4): margin_t2 < 0, stability < 0.
//   kappa_slope() < 0 discriminates genuine convergence; thrash shows steady_margin < 0.
//   Lifecycle contamination (QC(1)+OnRotation, 2 samples/epoch): no Steady epochs → None.
//
// Phase 37 invariants (causal provider failure and polytope surface attribution):
//   T2 (rotation thrash) is caused by policy configuration, NOT by provider behaviour.
//   T1 (false equilibrium) IS exercisable via liveness failure with active_window=2.
//     Mechanism: 1 dead of 2 active → only survivor sampled → κ=1.0 →
//     pressure_budget(0.5)=1.0 → margin_t1=0.9−1.0−0=−0.1 < 0.
//   Provider failure without forced rotation: last_kappa()→1.0, margin_t1<0, margin_t2>0.
//   Surface attribution: provider failure → T1−/T2+. Policy churn → T2−/T1≥0.
//   Eviction removes offender: old counts dilute concentration; steady_margin recovers > 0.
//   Eviction does NOT create T2 thrash: evict()+add() do not increment epoch_count.
//   Repeat offender readmission rejected during liveness_cooldown_secs: EvictionCooldown.
//   Verdict: A. PROVIDER_ORIGINATED_DEGRADATION_DETECTED_AND_CORRECTED

use std::time::Duration;

use rand_core::OsRng;
use scp_cryptography::keys::KeyPair;
use scp_ledger_substrate::SubstrateLedger;
use scp_provider_pool::{
    AdmissionConfig, AdmissionError, admission_challenge_message,
    ChurnBudget, EpochPhase, EvictionConfig, EvictionReason,
    ExposureResetPolicy, PoolRotationPolicy, ProviderPool,
    SamplingStrategy,
};

// ── Simulation harness ────────────────────────────────────────────────────────

#[allow(dead_code)]
struct EpochTrace {
    kappa:                   f64,
    smoothed_kappa:          f64,
    accumulated_pressure:    f64,
    epoch:                   u32,
    total_samples:           u64,
    active_n:                usize,
    spectral_concentration:  f64,
    liveness_weighted_kappa: f64,
}

struct PoolSimulator {
    pool:  ProviderPool<SubstrateLedger>,
    trace: Vec<EpochTrace>,
    rng:   OsRng,
}

impl PoolSimulator {
    fn new(pool: ProviderPool<SubstrateLedger>) -> Self {
        Self { pool, trace: Vec::new(), rng: OsRng }
    }

    fn run_epoch(&mut self, samples: usize) {
        for _ in 0..samples { let _ = self.pool.sample(&mut self.rng); }
        let _ = self.pool.maybe_rotate(&mut self.rng);
        let cp = self.pool.convergence_pressure();
        self.trace.push(EpochTrace {
            kappa:                   cp.kappa,
            smoothed_kappa:          cp.smoothed_kappa,
            accumulated_pressure:    cp.accumulated_pressure,
            epoch:                   self.pool.epoch_count(),
            total_samples:           cp.total_samples,
            active_n:                cp.active_n,
            spectral_concentration:  cp.spectral_concentration,
            liveness_weighted_kappa: cp.liveness_weighted_kappa,
        });
    }

    fn max_kappa(&self) -> f64 {
        self.trace.iter().map(|t| t.kappa).fold(0.0_f64, f64::max)
    }

    fn total_rotations(&self) -> u32 {
        self.trace.last().map_or(0, |t| t.epoch)
    }

    fn kappa_slope(&self) -> f64 {
        let n = self.trace.len();
        if n < 2 { return 0.0; }
        let nf = n as f64;
        let mean_x = (nf - 1.0) / 2.0;
        let mean_y: f64 = self.trace.iter().map(|t| t.kappa).sum::<f64>() / nf;
        let cov: f64 = self.trace.iter().enumerate()
            .map(|(i, t)| (i as f64 - mean_x) * (t.kappa - mean_y))
            .sum();
        let var_x: f64 = (0..n).map(|i| (i as f64 - mean_x).powi(2)).sum();
        if var_x < 1e-12 { 0.0 } else { cov / var_x }
    }

    fn pressure_budget(&self, threshold: f64) -> f64 {
        if self.trace.is_empty() { return 0.0; }
        let above = self.trace.iter().filter(|t| t.kappa > threshold).count();
        above as f64 / self.trace.len() as f64
    }

    #[allow(dead_code)]
    fn stability_vector(&self) -> StabilityVector {
        let n = self.trace.len();
        let last = self.trace.last();
        StabilityVector {
            kappa:                last.map_or(1.0, |t| t.kappa),
            smoothed_kappa:       last.map_or(1.0, |t| t.smoothed_kappa),
            ewma_lag:             last.map_or(0.0, |t| t.kappa - t.smoothed_kappa),
            rotation_rate:        if n == 0 { 0.0 } else {
                self.total_rotations() as f64 / n as f64
            },
            pressure_budget_half: self.pressure_budget(0.5),
        }
    }

    // T1 margin proxy: false-equilibrium detection.
    // Positive when κ is falling (genuine convergence).
    // Boundary at budget + slope_penalty = 0.9; negative when sum exceeds that.
    fn margin_t1(&self) -> f64 {
        let slope_penalty = self.kappa_slope().max(0.0);
        (0.9 - self.pressure_budget(0.5) - slope_penalty).clamp(-1.0, 1.0)
    }

    // T2 margin proxy: churn exhaustion boundary.
    // Boundary at rotation_rate = 0.5 (half of all epochs trigger rotation).
    fn margin_t2(&self) -> f64 {
        let n = self.trace.len();
        if n == 0 { return 1.0; }
        let rate = self.total_rotations() as f64 / n as f64;
        (0.5 - rate).clamp(-1.0, 1.0)
    }

    // T3 margin proxy: EWMA lag (burst invisibility).
    // Boundary at lag = 0.3: burst has spiked raw κ while smoothed κ remains low.
    fn margin_t3(&self) -> f64 {
        let lag = self.trace.last().map_or(0.0, |t| t.kappa - t.smoothed_kappa);
        (0.3 - lag).clamp(-1.0, 1.0)
    }

    // T4 margin proxy: post-reset initialization window.
    // Boundary at total_samples = 4*active_n (≈4 observations per provider).
    // Negative when below threshold (adversary has maximum leverage on entropy estimate).
    fn margin_t4(&self) -> f64 {
        let t = match self.trace.last() { Some(t) => t, None => return 1.0 };
        if t.active_n == 0 { return 1.0; }
        let threshold = 4.0 * t.active_n as f64;
        (t.total_samples as f64 / threshold - 1.0).clamp(-1.0, 1.0)
    }

    fn last_kappa(&self) -> f64 {
        self.trace.last().map_or(1.0, |t| t.kappa)
    }

    #[allow(dead_code)]
    fn last_spectral_concentration(&self) -> f64 {
        self.trace.last().map_or(0.0, |t| t.spectral_concentration)
    }

    #[allow(dead_code)]
    fn last_liveness_weighted_kappa(&self) -> f64 {
        self.trace.last().map_or(1.0, |t| t.liveness_weighted_kappa)
    }

    // Returns None when no trace entry is in Steady phase (lifecycle contaminated).
    // Returns Some(stability_margin()) when at least one Steady epoch exists.
    fn steady_stability_margin(&self) -> Option<f64> {
        let has_steady = self.trace.iter()
            .any(|t| EpochPhase::for_pool(t.total_samples, t.active_n) == EpochPhase::Steady);
        if !has_steady { return None; }
        Some(self.stability_margin())
    }

    // Epoch lifecycle phase at trace index idx.
    fn phase_at(&self, idx: usize) -> Option<EpochPhase> {
        let t = self.trace.get(idx)?;
        Some(EpochPhase::for_pool(t.total_samples, t.active_n))
    }

    // Minimum margin across all four collapse boundaries.
    // > 0 → inside stability polytope. < 0 → at least one boundary crossed.
    fn stability_margin(&self) -> f64 {
        self.margin_t1().min(self.margin_t2()).min(self.margin_t3()).min(self.margin_t4())
    }
}

#[allow(dead_code)]
struct StabilityVector {
    kappa:                f64,
    smoothed_kappa:       f64,
    ewma_lag:             f64,
    rotation_rate:        f64,
    pressure_budget_half: f64,
}

// ── §S1. k=n sampling reveals all providers every query → κ = 1.0 ─────────────
//
// The tracker records rate as appearances[id] / total_sample_calls. With k=n,
// every provider appears in 100% of calls → rate = 1.0 → entropy = 0 bits → κ = 1.0.
// This is the WORST privacy configuration: an adversary observing any single query
// immediately knows all n providers. Used to calibrate the upper bound of κ.

#[test]
fn sim_full_coverage_sampling_has_maximum_kappa() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(4))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..10 { sim.run_epoch(100); }

    assert!(
        sim.max_kappa() > 0.99,
        "k=n sampling must have κ=1.0 on every epoch; got max κ = {}",
        sim.max_kappa()
    );
}

// ── §S2. κ(t) decreases toward 0 as uniform samples accumulate ───────────────
//
// Epoch 1: 1 sample → entropy = 0 bits → κ = 1.0 (fully concentrated).
// Epoch 2: 10_000 additional samples → entropy ≈ log₂(4) → κ ≈ 0.0.
// The 1-sample imbalance is negligible relative to 10,001 total.

#[test]
fn sim_entropy_recovers_with_dense_sampling() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(1);
    sim.run_epoch(10_000);

    assert!(
        sim.trace[0].kappa > 0.9,
        "epoch 1 (1 sample) must have κ near 1.0; got {}",
        sim.trace[0].kappa
    );
    assert!(
        sim.trace[1].kappa < 0.05,
        "epoch 2 (10,001 total samples) must have κ near 0.0; got {}",
        sim.trace[1].kappa
    );
}

// ── §S3. cooldown(MAX) blocks all auto-rotation regardless of policy ──────────
//
// QueryCount(1) fires on every maybe_rotate() call. The cooldown gate fires
// before the policy arm, so query_count never increments and rotation never occurs.

#[test]
fn sim_cooldown_max_blocks_all_autorotation() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        )
        .with_cooldown(Duration::MAX);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..20 { sim.run_epoch(0); }

    assert_eq!(
        sim.total_rotations(), 0,
        "cooldown(MAX) must block all auto-rotations; got {} rotations",
        sim.total_rotations()
    );
}

// ── §S4. IntegralTriggered rotation rate is inversely proportional to threshold
//
// RandomK(4) with active_window=4 (k=n): every query reveals all 4 providers →
// rate[i]=1.0 → entropy=0 → κ=1.0 in Steady. 16 samples/epoch ensures total_samples ≥ 16
// (4*active_n) from epoch 1, so T4 gate does not block IntegralTriggered.
// Low threshold (1.5): accumulated_kappa reaches 2.0 on epoch 2 → fires every 2 epochs.
// High threshold (9.5): accumulated_kappa reaches 10.0 only at epoch 10 → 1 rotation.
// Both thresholds ≥ 1.0: no cooldown required (safety invariant satisfied).
// 8 providers: dormant=4 ≥ active_window=4 → floor gate passes.

#[test]
fn sim_integral_threshold_governs_rotation_rate() {
    let make_pool = |threshold: f64| {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(4))
            .with_active_window(4)
            .with_rotation(
                PoolRotationPolicy::IntegralTriggered { max_accumulated_pressure: threshold },
                ChurnBudget { min_churn: 1, max_churn: 1 },
            );
        for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut sim_low  = PoolSimulator::new(make_pool(1.5));
    let mut sim_high = PoolSimulator::new(make_pool(9.5));

    for _ in 0..10 { sim_low.run_epoch(16); }
    for _ in 0..10 { sim_high.run_epoch(16); }

    assert!(
        sim_low.total_rotations() > sim_high.total_rotations(),
        "low threshold (0.5) must produce more rotations than high threshold (9.5); \
         got {} vs {}",
        sim_low.total_rotations(), sim_high.total_rotations()
    );
}

// ── §S5. Simulation trace length equals number of run_epoch() calls ───────────

#[test]
fn sim_trace_length_reflects_epoch_count() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..17 { sim.run_epoch(10); }

    assert_eq!(
        sim.trace.len(), 17,
        "run_epoch() must append exactly one EpochTrace per call"
    );
    assert_eq!(
        sim.total_rotations(), 0,
        "Manual policy must never auto-rotate; epoch_count must remain 0"
    );
}

// ── §S6. OLS slope of κ is negative under natural convergence ────────────────
//
// Epoch 1: 1 sample → one provider rate=1.0 → κ=1.0.
// Epoch 100: 100 cumulative samples near-uniform → κ ≈ 0.0.
// OLS fits a line from ~1.0 down to ~0.0: slope is strongly negative.

#[test]
fn sim_natural_convergence_slope_is_negative() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..100 { sim.run_epoch(1); }

    assert!(
        sim.kappa_slope() < 0.0,
        "OLS slope must be negative when κ falls from 1.0 toward 0.0; got {}",
        sim.kappa_slope()
    );
}

// ── §S7. pressure_budget(0.5) is low after convergence ───────────────────────
//
// Same 100-epoch run as §S6. Epoch 1: κ=1.0 > 0.5. Early epochs may also have
// κ > 0.5 before diversity accumulates. After 100 cumulative samples with 4 providers,
// the budget must be well below 0.15: sustained high-κ epochs indicate no convergence.
// (Threshold is 0.15 rather than a stricter value because the cumulative ExposureTracker
// accumulates evidence monotonically — early epochs naturally inflate the budget until
// enough diversity is observed.)

#[test]
fn sim_pressure_budget_low_after_convergence() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..100 { sim.run_epoch(1); }

    assert!(
        sim.pressure_budget(0.5) < 0.15,
        "pressure_budget(0.5) must be < 0.15 after 100 cumulative samples; got {}",
        sim.pressure_budget(0.5)
    );
}

// ── §S8. pressure_budget(0.5) = 1.0 when no samples are taken ────────────────
//
// Zero samples → tracker has no data → entropy=0 bits → κ=1.0 every epoch.
// 1.0 > 0.5 is true for all 30 epochs → budget = 30/30 = 1.0.

#[test]
fn sim_pressure_budget_one_when_no_data() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..30 { sim.run_epoch(0); }

    assert_eq!(
        sim.pressure_budget(0.5), 1.0,
        "zero samples must give κ=1.0 every epoch; pressure_budget(0.5) must be 1.0"
    );
}

// ── §S9. Dense sampling reduces pressure_budget vs zero samples ───────────────
//
// A: 30 epochs × 0 samples → κ=1.0 always → budget(0.5) = 1.0.
// B: 30 epochs × 100 samples → κ ≈ 0.0 from epoch 1 → budget(0.5) = 0.0.
// Demonstrates: evidence of diversity eliminates sustained pressure.

#[test]
fn sim_dense_sampling_reduces_pressure_budget_vs_zero_samples() {
    let make_pool = || {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4);
        for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut sim_a = PoolSimulator::new(make_pool());
    let mut sim_b = PoolSimulator::new(make_pool());

    for _ in 0..30 { sim_a.run_epoch(0); }
    for _ in 0..30 { sim_b.run_epoch(100); }

    assert!(
        sim_a.pressure_budget(0.5) > sim_b.pressure_budget(0.5),
        "zero-sample budget ({}) must exceed dense-sample budget ({})",
        sim_a.pressure_budget(0.5), sim_b.pressure_budget(0.5)
    );
}

// ── §S10. pressure_budget boundary conditions ─────────────────────────────────
//
// Final state (30 total samples): 30 mod 4 ≠ 0 → cannot be perfectly uniform → κ > 0.
// Intermediate epochs (4,8,…,28) can momentarily hit κ=0 by chance (uniform split),
// so budget(0.0) is high but not guaranteed to equal 1.0. Tested with > 0.8.
// κ ≤ 1.0 always → budget(1.0) = 0.0 (strict: κ > 1.0 never).
// Monotonicity: budget(0.0) ≥ budget(0.5) ≥ budget(1.0).

#[test]
fn sim_pressure_budget_boundary_conditions() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..30 { sim.run_epoch(1); }

    assert!(
        sim.pressure_budget(0.0) > 0.8,
        "κ > 0 in most epochs (imperfect distribution) → budget(0.0) must be high; got {}",
        sim.pressure_budget(0.0)
    );
    assert_eq!(
        sim.pressure_budget(1.0), 0.0,
        "κ ≤ 1.0 always → budget(1.0) must be 0.0"
    );
    assert!(
        sim.pressure_budget(0.0) >= sim.pressure_budget(0.5),
        "pressure_budget must be monotone decreasing in threshold"
    );
    assert!(
        sim.pressure_budget(0.5) >= sim.pressure_budget(1.0),
        "pressure_budget must be monotone decreasing in threshold"
    );
}

// ── §S11. Healthy operation lies inside the stability polytope ────────────────
//
// 100 epochs × 10 samples: κ converges, slope negative, rotation_rate=0, lag≈0.
// All three margins positive → stability_margin() > 0.

#[test]
fn sim_stability_margin_positive_under_natural_convergence() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..100 { sim.run_epoch(10); }

    assert!(
        sim.stability_margin() > 0.0,
        "healthy convergent operation must lie inside the stability polytope; \
         got stability_margin = {}, margin_t1 = {}, margin_t2 = {}, margin_t3 = {}",
        sim.stability_margin(), sim.margin_t1(), sim.margin_t2(), sim.margin_t3()
    );
}

// ── §S12. T3 margin reveals EWMA lag after tracker reset ─────────────────────
//
// Phase 1 (warm): 10_000 samples → EWMA converges: smoothed_entropy ≈ log₂(4).
// Phase 2 (reset): force_rotate() with OnRotation policy → raw counts cleared,
//   smoothed_entropy retained.
// Phase 3 (snapshot): run_epoch(0) → total_samples=0 → raw entropy=0 → raw κ=1.0.
//   smoothed_kappa ≈ 0 (smoothed_entropy still ≈ log₂(4)).
//   ewma_lag = raw κ - smoothed_kappa ≈ 1.0 > 0.5.

#[test]
fn sim_t3_margin_reveals_ewma_lag() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(10_000);                // warm: EWMA converges to near-uniform
    sim.pool.force_rotate(&mut sim.rng);  // reset raw counts; smoothed_entropy retained
    sim.run_epoch(0);                     // snapshot: raw κ=1.0, smoothed_kappa≈0

    let lag = sim.trace[1].kappa - sim.trace[1].smoothed_kappa;
    assert!(
        lag > 0.5,
        "after warm+reset, ewma_lag must exceed 0.5; got lag = {} \
         (raw κ = {}, smoothed κ = {})",
        lag, sim.trace[1].kappa, sim.trace[1].smoothed_kappa
    );
    assert!(
        sim.margin_t3() < 0.0,
        "T3 margin must be negative when ewma_lag > 0.3; got margin_t3 = {}",
        sim.margin_t3()
    );
}

// ── §S13. T2 margin is negative under high rotation rate ─────────────────────
//
// QueryCount(1) rotates on every maybe_rotate() call.
// 5 samples/epoch ensures total_samples ≥ active_n=4 from epoch 1 (Reconverging),
// where QueryCount is admissible. rotation_rate ≈ 1.0 → margin_t2 = -0.5 < 0.

#[test]
fn sim_t2_margin_negative_under_high_rotation_rate() {
    // 8 providers: dormant=4 ≥ active_window=4 → floor gate passes.
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..10 { sim.run_epoch(5); }

    assert!(
        sim.margin_t2() < 0.0,
        "rotation_rate near 1.0 must cross T2 boundary; got margin_t2 = {}",
        sim.margin_t2()
    );
    assert!(
        sim.stability_margin() < 0.0,
        "T2 boundary crossing must make stability_margin() negative; got {}",
        sim.stability_margin()
    );
}

// ── §S14. Stability volume shrinks under k=n (worst privacy config) ───────────
//
// A: RandomK(1) — 50 epochs × 10 samples → κ converges, slope negative, margin_t1 > 0.
// B: RandomK(4) — 50 epochs × 10 samples → κ=1.0 always, budget(0.5)=1.0, margin_t1 < 0.
// stability_margin(A) > stability_margin(B).

#[test]
fn sim_stability_volume_shrinks_under_k_equals_n() {
    let make_pool = |k: usize| {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(k))
            .with_active_window(4);
        for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut sim_a = PoolSimulator::new(make_pool(1));
    let mut sim_b = PoolSimulator::new(make_pool(4));

    for _ in 0..50 { sim_a.run_epoch(10); }
    for _ in 0..50 { sim_b.run_epoch(10); }

    assert!(
        sim_a.stability_margin() > sim_b.stability_margin(),
        "k=1 must have larger stability margin than k=n; got {} vs {}",
        sim_a.stability_margin(), sim_b.stability_margin()
    );
    assert!(
        sim_b.margin_t1() < 0.0,
        "k=n must collapse the T1 boundary; got margin_t1 = {}",
        sim_b.margin_t1()
    );
}

// ── §S15. smoothed_kappa lags raw kappa after reset ───────────────────────────
//
// After 10_000 samples: EWMA converged, lag ≈ 0 (both raw and smoothed near 0).
// After force_rotate() + run_epoch(0): raw κ=1.0 (no data), smoothed_kappa≈0.
// raw κ > smoothed κ (raw leads smoothed after reset).

#[test]
fn sim_smoothed_kappa_lags_raw_kappa_after_dense_then_sparse() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(10_000);                // warm: EWMA converges to near-uniform
    sim.pool.force_rotate(&mut sim.rng);  // reset raw counts; smoothed_entropy retained
    sim.run_epoch(0);                     // snapshot: raw κ=1.0, smoothed_kappa≈0

    let warm_lag = sim.trace[0].kappa - sim.trace[0].smoothed_kappa;
    let burst_lag = sim.trace[1].kappa - sim.trace[1].smoothed_kappa;

    assert!(
        warm_lag.abs() < 0.05,
        "after 10_000 samples EWMA must have converged; lag must be near 0, got {}",
        warm_lag
    );
    assert!(
        burst_lag > 0.5,
        "after tracker reset, raw κ=1.0 and smoothed_kappa≈0 → lag must exceed 0.5; got {}",
        burst_lag
    );
    assert!(
        sim.trace[1].kappa > sim.trace[1].smoothed_kappa,
        "raw kappa must lead smoothed_kappa after reset"
    );
}

// ── §S16. T4 margin is negative immediately after rotation reset ──────────────
//
// After force_rotate() with OnRotation policy, total_samples = 0.
// margin_t4 = (0 / (4*4) - 1).clamp(-1,1) = -1.0 < 0.
// System is in PostReset phase: maximum adversarial leverage on entropy estimate.

#[test]
fn sim_t4_margin_negative_immediately_after_rotation() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(10_000);                // warm: establish EWMA history
    sim.pool.force_rotate(&mut sim.rng);  // reset raw counts; total_samples → 0
    sim.run_epoch(0);                     // snapshot: total_samples=0, active_n=4

    assert!(
        sim.margin_t4() < 0.0,
        "T4 margin must be negative immediately after rotation reset; got {}",
        sim.margin_t4()
    );
    assert_eq!(
        sim.phase_at(1),
        Some(EpochPhase::PostReset),
        "system must be in PostReset phase after rotation reset; got {:?}",
        sim.phase_at(1)
    );
}

// ── §S17. T4 margin recovers after sufficient post-reset samples ──────────────
//
// 32 samples with active_n=4 → 32 ≥ 4*4=16 → Steady phase.
// margin_t4 = (32/16 - 1).clamp(-1,1) = 1.0 > 0.

#[test]
fn sim_t4_margin_recovers_with_post_reset_samples() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(10_000);                // warm
    sim.pool.force_rotate(&mut sim.rng);  // reset
    sim.run_epoch(32);                    // 32 ≥ 4*4=16 → margin_t4 > 0

    assert!(
        sim.margin_t4() > 0.0,
        "T4 margin must be positive after 32 post-reset samples (threshold=16); got {}",
        sim.margin_t4()
    );
    assert_eq!(
        sim.phase_at(1),
        Some(EpochPhase::Steady),
        "32 samples with active_n=4 must be Steady phase; got {:?}",
        sim.phase_at(1)
    );
}

// ── §S18. Epoch lifecycle traverses PostReset → Reconverging → Steady ─────────
//
// force_rotate() → total_samples=0 before any run_epoch.
// run_epoch(0):  total=0 < 4      → PostReset
// run_epoch(3):  total=3 < 4      → PostReset
// run_epoch(4):  total=7 ≥ 4, < 16 → Reconverging
// run_epoch(20): total=27 ≥ 16    → Steady

#[test]
fn sim_epoch_lifecycle_traverses_phases_in_order() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..5u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.pool.force_rotate(&mut sim.rng);  // total_samples → 0

    sim.run_epoch(0);   // trace[0]: total_samples=0  → PostReset
    sim.run_epoch(3);   // trace[1]: total_samples=3  → PostReset
    sim.run_epoch(4);   // trace[2]: total_samples=7  → Reconverging
    sim.run_epoch(20);  // trace[3]: total_samples=27 → Steady

    assert_eq!(sim.phase_at(0), Some(EpochPhase::PostReset),
        "trace[0]: 0 samples → PostReset; got {:?}", sim.phase_at(0));
    assert_eq!(sim.phase_at(1), Some(EpochPhase::PostReset),
        "trace[1]: 3 samples < 4 → PostReset; got {:?}", sim.phase_at(1));
    assert_eq!(sim.phase_at(2), Some(EpochPhase::Reconverging),
        "trace[2]: 7 samples ≥ 4 < 16 → Reconverging; got {:?}", sim.phase_at(2));
    assert_eq!(sim.phase_at(3), Some(EpochPhase::Steady),
        "trace[3]: 27 samples ≥ 16 → Steady; got {:?}", sim.phase_at(3));
}

// ── §S19. T4 is the binding constraint in a fresh pool ───────────────────────
//
// Fresh pool, no warm-up: run_epoch(0) → total_samples=0 → margin_t4=-1.0.
// No EWMA history → smoothed_entropy=0 → lag=0 → margin_t3=0.3 > 0.
// T4 is the binding constraint: stability_margin() < margin_t3().

#[test]
fn sim_t4_is_binding_constraint_in_fresh_pool() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.run_epoch(0);  // fresh pool: total_samples=0

    assert!(
        sim.margin_t4() < 0.0,
        "T4 margin must be negative in fresh pool (total_samples=0); got {}",
        sim.margin_t4()
    );
    assert!(
        sim.margin_t3() > 0.0,
        "T3 margin must be positive in fresh pool (no EWMA lag); got {}",
        sim.margin_t3()
    );
    assert!(
        sim.stability_margin() < sim.margin_t3(),
        "T4 must bind below T3 in fresh pool; stability={} margin_t3={}",
        sim.stability_margin(), sim.margin_t3()
    );
}

// ── §S20. T4 window closes predictably with sample accumulation ───────────────
//
// Sim A: run_epoch(0)  → total_samples=0 → T4 open (margin_t4 < 0).
// Sim B: run_epoch(0) + run_epoch(32) → total_samples=32 ≥ 16 → T4 closed (margin_t4 > 0).
// Demonstrates: the system's own sampling rate controls T4 exposure duration.

#[test]
fn sim_t4_window_closes_with_sufficient_post_reset_samples() {
    let make_pool = || {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4);
        for i in 0..4u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut sim_a = PoolSimulator::new(make_pool());
    let mut sim_b = PoolSimulator::new(make_pool());

    sim_a.run_epoch(0);   // total_samples=0 → margin_t4=-1.0
    sim_b.run_epoch(0);   // trace[0]: total_samples=0
    sim_b.run_epoch(32);  // trace[1]: total_samples=32 ≥ 16 → margin_t4=1.0

    assert!(
        sim_a.margin_t4() < 0.0,
        "Sim A: T4 must be open at 0 samples; got margin_t4={}",
        sim_a.margin_t4()
    );
    assert!(
        sim_b.margin_t4() > 0.0,
        "Sim B: T4 must close at 32 samples (threshold=16); got margin_t4={}",
        sim_b.margin_t4()
    );
    assert!(
        sim_b.stability_margin() > sim_a.stability_margin(),
        "Sim B stability ({}) must exceed Sim A stability ({}) after T4 closes",
        sim_b.stability_margin(), sim_a.stability_margin()
    );
}

// Phase 34 invariants (Phase Opacity — adversarial identification):
//   tick() output traces are phase-indistinguishable under Manual policy.
//   tick() faithfully wraps maybe_rotate(): same epoch progression for same policy.

// ── §S21. tick() trace is phase-indistinguishable under Manual policy ─────────
//
// Pool A (PostReset, 0 samples): T4 gate fires → DeferralReason::EstimatorNotConverged →
// tick() returns false.
// Pool B (Steady, 16 samples): Manual policy → PolicyThresholdNotMet → tick() returns false.
// An adversary observing only the boolean trace cannot distinguish the two pools.

#[test]
fn sim_tick_behavioral_identity_across_phases() {
    let mut rng = OsRng;

    let make_pool = || {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4)
            .with_rotation(
                PoolRotationPolicy::Manual,
                ChurnBudget { min_churn: 1, max_churn: 1 },
            );
        for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut pool_a = make_pool();  // PostReset: 0 samples — no sample() calls.
    let mut pool_b = make_pool();  // Steady: 16 samples.
    for _ in 0..16 { let _ = pool_b.sample(&mut rng); }

    let trace_a: Vec<bool> = (0..10).map(|_| pool_a.tick(&mut rng)).collect();
    let trace_b: Vec<bool> = (0..10).map(|_| pool_b.tick(&mut rng)).collect();

    assert_eq!(trace_a, vec![false; 10],
        "Pool A (PostReset, Manual): all tick() calls must return false");
    assert_eq!(trace_b, vec![false; 10],
        "Pool B (Steady, Manual): all tick() calls must return false");
    assert_eq!(trace_a, trace_b,
        "tick() traces must be identical across EpochPhases with Manual policy");
}

// ── §S22. tick() faithfully wraps maybe_rotate() ─────────────────────────────
//
// QueryCount(2) in Steady: fires every 2 calls → 3 rotations in 6 calls.
// Both tick() and maybe_rotate() pools must produce the same epoch count.

#[test]
fn sim_tick_faithfully_wraps_maybe_rotate() {
    let mut rng = OsRng;

    let make_pool = || {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4)
            .with_rotation(
                PoolRotationPolicy::QueryCount(2),
                ChurnBudget { min_churn: 1, max_churn: 1 },
            );
        for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut pool_a = make_pool();
    let mut pool_b = make_pool();

    // Put both in Steady (16 samples).
    for _ in 0..16 {
        let _ = pool_a.sample(&mut rng);
        let _ = pool_b.sample(&mut rng);
    }

    for _ in 0..6 { pool_a.tick(&mut rng); }
    for _ in 0..6 { pool_b.maybe_rotate(&mut rng); }

    assert_eq!(pool_a.epoch_count(), pool_b.epoch_count(),
        "tick() and maybe_rotate() must produce identical epoch progressions; \
         got tick={} vs rotate={}", pool_a.epoch_count(), pool_b.epoch_count());
    assert_eq!(pool_a.epoch_count(), 3,
        "QueryCount(2) × 6 calls → 3 rotations expected; got {}", pool_a.epoch_count());
}

// ── §S23. BurstTriggered (always-fire) integrates with epoch lifecycle ────────

#[test]
fn sim_burst_triggered_threshold_always_met_produces_rotation() {
    let mut rng = OsRng;
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::BurstTriggered {
                min_burst_magnitude: -2.0,
                response_jitter_max: Duration::ZERO,
            },
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    // Drive to Steady.
    for _ in 0..16 { let _ = pool.sample(&mut rng); }

    // With threshold=-2.0 and jitter=0, every call should fire.
    for _ in 0..5 { pool.maybe_rotate(&mut rng); }
    assert_eq!(pool.epoch_count(), 5,
        "BurstTriggered fires on every call when threshold is always met; got {}",
        pool.epoch_count());
}

// ── §S24. BurstTriggered response jitter reduces rotation count ───────────────

#[test]
fn sim_burst_triggered_response_jitter_reduces_rotation_count() {
    let mut rng = OsRng;
    // Use a short jitter so the test can also verify eventual firing without a long sleep.
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::BurstTriggered {
                min_burst_magnitude: -2.0,
                response_jitter_max: Duration::from_millis(10),
            },
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    // Drive to Steady.
    for _ in 0..16 { let _ = pool.sample(&mut rng); }

    // Phase A: 6 immediate calls. The first call sets a deadline in [0, 10ms).
    // Subsequent calls find the deadline in the future and are suppressed.
    // Jitter prevents the adversary from predicting rotation timing (forced-trajectory resistance).
    for _ in 0..6 { pool.maybe_rotate(&mut rng); }
    let after_immediate = pool.epoch_count();
    assert!(after_immediate < 6,
        "jitter must suppress some rotations; expected < 6, got {after_immediate}");

    // Phase B: wait for the deadline to elapse, then one more call must fire.
    std::thread::sleep(Duration::from_millis(15));
    pool.maybe_rotate(&mut rng);
    assert!(pool.epoch_count() > after_immediate,
        "rotation must occur after jitter deadline elapses; \
         before={after_immediate} after={}", pool.epoch_count());
}

// ── §Phase 36: kappa_displacement alias ──────────────────────────────────────
//
// kappa_displacement_since_rotation() is a zero-cost alias for kappa_velocity.
// Before first rotation: both None. After rotation: both Some(same value).

#[test]
fn sim_kappa_displacement_alias_agrees_with_kappa_velocity() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::Manual,
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
    let mut rng = OsRng;

    // Before first rotation: both must be None.
    let cp = pool.convergence_pressure();
    assert_eq!(
        cp.kappa_velocity, cp.kappa_displacement_since_rotation(),
        "alias must equal field before any rotation"
    );

    // After a rotation: both must be Some(identical value).
    pool.force_rotate(&mut rng);
    let cp = pool.convergence_pressure();
    assert_eq!(
        cp.kappa_velocity, cp.kappa_displacement_since_rotation(),
        "alias must equal field after first rotation"
    );
}

// ── §S29. Neutral steady baseline lies inside the polytope ───────────────────
//
// 8 providers (4 active), Manual, Never. 50 epochs × 100 samples = 5000 total.
// With near-uniform selection, κ converges to ≈ 0, all four margins positive.
// steady_stability_margin() = Some(> 0).

#[test]
fn sim_s29_neutral_steady_baseline_inside_polytope() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..50 { sim.run_epoch(100); }

    assert!(
        sim.last_kappa() < 0.05,
        "neutral baseline with 5000 samples: κ must be near 0.0; got {}",
        sim.last_kappa()
    );
    let steady = sim.steady_stability_margin()
        .expect("neutral baseline: must reach Steady");
    assert!(
        steady > 0.0,
        "neutral baseline must be inside polytope; got steady_margin={}", steady
    );
}

// ── §S30. Bias sweep: monotone steady-margin degradation with rotation rate ───
//
// QC(100): 0 rotations in 50 epochs → stability bounded by T3 ≈ 0.3.
// QC(10):  ~5 rotations → same T3 bound but higher T2 cost → same or lower margin.
// QC(1):   ~50 rotations → margin_t2 < 0 → stability < 0.
// Monotone: m100 ≥ m10 ≥ m1. κ remains low in all three (Never dilutes concentration).

#[test]
fn sim_s30_bias_sweep_monotonic_steady_margin_degradation() {
    let make_pool = |qc: u64| {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4)
            .with_rotation(
                PoolRotationPolicy::QueryCount(qc),
                ChurnBudget { min_churn: 1, max_churn: 1 },
            );
        for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };

    let mut sim100 = PoolSimulator::new(make_pool(100));
    let mut sim10  = PoolSimulator::new(make_pool(10));
    let mut sim1   = PoolSimulator::new(make_pool(1));

    for _ in 0..50 { sim100.run_epoch(10); }
    for _ in 0..50 { sim10.run_epoch(10); }
    for _ in 0..50 { sim1.run_epoch(10); }

    let m100 = sim100.steady_stability_margin().expect("QC(100): must reach Steady");
    let m10  = sim10.steady_stability_margin().expect("QC(10): must reach Steady");
    let m1   = sim1.steady_stability_margin().expect("QC(1)+Never: must reach Steady");

    assert!(m100 >= m10, "m100 ({}) >= m10 ({}) required for monotonicity", m100, m10);
    assert!(m10  >= m1,  "m10 ({}) >= m1 ({}) required for monotonicity",   m10,  m1);
    assert!(m1 < 0.0,    "QC(1) must cross the stability boundary; got m1={}", m1);

    assert!(sim100.last_kappa() < 0.1,
        "QC(100)+Never: κ must stay low (diluted by accumulation); got {}", sim100.last_kappa());
    assert!(sim10.last_kappa() < 0.1,
        "QC(10)+Never: κ must stay low; got {}", sim10.last_kappa());
    assert!(sim1.last_kappa() < 0.1,
        "QC(1)+Never: κ must stay low (diluted by Never accumulation); got {}", sim1.last_kappa());
}

// ── §S31. Orthogonal adversarial setup: QC(1)+Never → stability < 0 ──────────
//
// Classified T2 positive-control: boundary crossed by policy configuration,
// NOT by provider misbehaviour. κ remains near 0 (Never reset dilutes across all 8).
// Verdict fixture: POLYTOPE_DETECTS_ORTHOGONAL_ROTATION_THRASH_UNDER_NEVER_RESET

#[test]
fn sim_s31_orthogonal_adversarial_kappa_zero_margin_negative() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..50 { sim.run_epoch(10); }

    assert!(
        sim.last_kappa() < 0.1,
        "QC(1)+Never: κ must be diluted by Never-reset accumulation; got {}",
        sim.last_kappa()
    );
    assert!(
        sim.margin_t2() < 0.0,
        "QC(1) rotation rate must cross T2 boundary; got margin_t2={}",
        sim.margin_t2()
    );
    assert!(
        sim.stability_margin() < 0.0,
        "T2 crossing must collapse stability_margin(); got {}",
        sim.stability_margin()
    );
}

// ── §S32. kappa_slope() discriminates convergence from thrash ────────────────
//
// Convergent sim (4 providers, Manual, Never, 100×10): slope < 0, steady_margin > 0.
// Thrash sim (8/4, QC(1)+Never, 100×10): κ flat near 0 (diluted), steady_margin < 0.
// The slope sign alone separates the two scenarios.

#[test]
fn sim_s32_recovery_kappa_slope_discriminates_convergence() {
    let mut conv_pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4);
    for i in 0..4u8 { conv_pool.add([i; 32], SubstrateLedger::new()); }

    let mut thrash_pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { thrash_pool.add([i; 32], SubstrateLedger::new()); }

    let mut conv_sim   = PoolSimulator::new(conv_pool);
    let mut thrash_sim = PoolSimulator::new(thrash_pool);

    for _ in 0..100 { conv_sim.run_epoch(10); }
    for _ in 0..100 { thrash_sim.run_epoch(10); }

    assert!(
        conv_sim.kappa_slope() < 0.0,
        "convergence sim: OLS slope must be negative (κ falling); got {}",
        conv_sim.kappa_slope()
    );
    assert!(
        conv_sim.steady_stability_margin().expect("convergence: must reach Steady") > 0.0,
        "convergence must lie inside the stability polytope"
    );
    assert!(
        thrash_sim.steady_stability_margin().expect("thrash: QC(1)+Never accumulates Steady") < 0.0,
        "thrash must be outside the stability polytope"
    );
}

// ── §S33. Lifecycle contamination eliminates Steady epochs ────────────────────
//
// QC(1)+OnRotation, 8 providers (4/4), 50 epochs × 2 samples.
// Sequence: 2 samples → Reconverging → QC(1) fires → tracker reset → cp.total_samples=0.
// Alternating PostReset entries (total_samples=0 or 2) — never reaches Steady (16).
// steady_stability_margin() must be None. stability_margin() < 0 (T4 binding).

#[test]
fn sim_s33_lifecycle_contamination_eliminates_steady_epochs() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        )
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation);
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..50 { sim.run_epoch(2); }

    assert!(
        sim.steady_stability_margin().is_none(),
        "QC(1)+OnRotation resets tracker every epoch: no Steady phases → None; \
         got {:?}", sim.steady_stability_margin()
    );
    assert!(
        sim.stability_margin() < 0.0,
        "T4 contamination must collapse stability_margin(); got {}",
        sim.stability_margin()
    );
}

// ── §S34. Rotation-thrash fixture is a classified T2 positive control ─────────
//
// T2 boundary is crossed by the QueryCount(1) policy, not by provider misbehaviour.
// T1 is NOT crossed: κ ≈ 0 because Never-reset accumulates all 8 providers' selections.
// Verdict fixture: POLYTOPE_DETECTS_ORTHOGONAL_ROTATION_THRASH_UNDER_NEVER_RESET

#[test]
fn sim_s34_rotation_thrash_fixture_is_t2_positive_control() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_rotation(
            PoolRotationPolicy::QueryCount(1),
            ChurnBudget { min_churn: 1, max_churn: 1 },
        );
    for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..50 { sim.run_epoch(10); }

    assert!(
        sim.margin_t2() < 0.0,
        "T2: rotation thrash must cross boundary (caused by QC(1) policy); got {}",
        sim.margin_t2()
    );
    assert!(
        sim.margin_t1() >= 0.0,
        "T1: concentration is NOT the cause (κ diluted by Never reset); got {}",
        sim.margin_t1()
    );
    assert!(
        sim.last_kappa() < 0.1,
        "κ must be near 0 (diluted by Never accumulation across all 8 providers); got {}",
        sim.last_kappa()
    );
    assert!(
        sim.steady_stability_margin().expect("QC(1)+Never: accumulates Steady epochs") < 0.0,
        "steady margin must be negative (T2 dominated); got {:?}",
        sim.steady_stability_margin()
    );
}

// ── §S35. Neutral provider behaviour preserves positive margin ────────────────
//
// 6 providers (active_window=2), Manual, Never. 50 epochs × 10 samples.
// No failures, no rotation. κ converges to ~0. All four margins positive.
// Demonstrates: provider silence ≠ provider failure; neutral actors do not degrade T1.

#[test]
fn sim_s35_neutral_provider_behaviour_preserves_positive_margin() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(2);
    for i in 0..6u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    for _ in 0..50 { sim.run_epoch(10); }

    let steady = sim.steady_stability_margin()
        .expect("neutral baseline: must reach Steady");
    assert!(
        steady > 0.0,
        "neutral providers must keep system inside polytope; got steady_margin={}",
        steady
    );
    assert!(
        sim.margin_t1() > 0.0,
        "T1 must be positive under neutral behaviour; got {}",
        sim.margin_t1()
    );
    assert!(
        sim.margin_t2() > 0.0,
        "T2 must be positive with Manual policy (zero rotation); got {}",
        sim.margin_t2()
    );
}

// ── §S36. Misbehaving provider degrades margin without forced rotation ─────────
//
// T1 exercisability: active_window=2, with_liveness(1, MAX).
// After force_rotate() (OnRotation reset), record_failure(active[0]) kills victim.
// 1 dead of 2 active → only survivor sampled → κ=1.0 →
// pressure_budget(0.5)=1.0 → margin_t1=0.9−1.0=−0.1 < 0.
// Manual policy: no rotation thrash → margin_t2 > 0.

#[test]
fn sim_s36_misbehaving_provider_degrades_margin_without_forced_rotation() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(2)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation)
        .with_liveness(1, u64::MAX);
    for i in 0..6u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.pool.force_rotate(&mut sim.rng);  // OnRotation: reset tracker; epoch_count=1

    let victim_id = sim.pool.active_set_snapshot()[0];
    sim.pool.record_failure(victim_id);   // consecutive_failures=1 ≥ max=1 → dead

    for _ in 0..30 { sim.run_epoch(10); }

    assert!(
        sim.last_kappa() > 0.9,
        "1 dead of 2 active: all samples on survivor → κ=1.0; got {}",
        sim.last_kappa()
    );
    assert!(
        sim.margin_t1() < 0.0,
        "pressure_budget(0.5)=1.0 with κ=1.0 always: T1 boundary crossed; got {}",
        sim.margin_t1()
    );
    assert!(
        sim.margin_t2() > 0.0,
        "Manual policy: no rotation thrash; T2 must not be crossed; got {}",
        sim.margin_t2()
    );
    assert!(
        sim.steady_stability_margin()
            .expect("OnRotation+force_rotate+30 epochs: Steady reached") < 0.0,
        "T1-dominated degradation: steady margin must be negative; got {:?}",
        sim.steady_stability_margin()
    );
}

// ── §S37. Surface attribution distinguishes provider failure from policy churn ─
//
// Scenario A (provider failure): margin_t1 < 0, margin_t2 > 0.
// Scenario B (policy churn):     margin_t2 < 0, margin_t1 ≥ 0.
// The two threat surfaces are diagnostically separable.

#[test]
fn sim_s37_surface_attribution_distinguishes_provider_failure_from_churn() {
    // Scenario A: provider failure (T1 dominated). Mirrors §S36 setup.
    let failure_pool = {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(2)
            .with_exposure_reset_policy(ExposureResetPolicy::OnRotation)
            .with_liveness(1, u64::MAX);
        for i in 0..6u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };
    let mut sim_a = PoolSimulator::new(failure_pool);
    sim_a.pool.force_rotate(&mut sim_a.rng);
    let victim = sim_a.pool.active_set_snapshot()[0];
    sim_a.pool.record_failure(victim);
    for _ in 0..30 { sim_a.run_epoch(10); }

    // Scenario B: policy churn (T2 dominated). Mirrors §S34 setup.
    let churn_pool = {
        let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
            .with_active_window(4)
            .with_rotation(
                PoolRotationPolicy::QueryCount(1),
                ChurnBudget { min_churn: 1, max_churn: 1 },
            );
        for i in 0..8u8 { pool.add([i; 32], SubstrateLedger::new()); }
        pool
    };
    let mut sim_b = PoolSimulator::new(churn_pool);
    for _ in 0..50 { sim_b.run_epoch(10); }

    // Scenario A: T1 negative, T2 positive (provider-originated, not churn).
    assert!(
        sim_a.margin_t1() < 0.0,
        "provider failure: T1 must be negative (false equilibrium); got {}",
        sim_a.margin_t1()
    );
    assert!(
        sim_a.margin_t2() > 0.0,
        "provider failure: T2 must be positive (no rotation churn); got {}",
        sim_a.margin_t2()
    );

    // Scenario B: T2 negative, T1 non-negative (policy-originated, κ diluted).
    assert!(
        sim_b.margin_t2() < 0.0,
        "policy churn: T2 must be negative; got {}",
        sim_b.margin_t2()
    );
    assert!(
        sim_b.margin_t1() >= 0.0,
        "policy churn: T1 not crossed (κ diluted by Never reset); got {}",
        sim_b.margin_t1()
    );
}

// ── §S38. Eviction removes offender and restores steady margin ────────────────
//
// Phase 1: 10 degradation epochs — 1 dead of 2 active → κ=1.0 → stability < 0.
// Evict victim + add replacement: active=[survivor, replacement].
// Phase 2: 50 recovery epochs — old counts dilute; new provider sampled equally.
// After ~3 recovery epochs κ drops below 0.5; steady_margin eventually > 0.

#[test]
fn sim_s38_eviction_removes_offender_and_restores_steady_margin() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(2)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation)
        .with_liveness(1, u64::MAX)
        .with_eviction(EvictionConfig {
            liveness_cooldown_secs:     300,
            equivocation_cooldown_secs: 3600,
            max_re_admissions:          3,
        });
    for i in 0..6u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.pool.force_rotate(&mut sim.rng);

    let victim_id = sim.pool.active_set_snapshot()[0];
    sim.pool.record_failure(victim_id);

    // 10 degradation epochs: T1 must be crossed.
    for _ in 0..10 { sim.run_epoch(10); }
    let pre_margin = sim.stability_margin();
    assert!(pre_margin < 0.0,
        "pre-eviction: T1 boundary must be crossed; got {}", pre_margin);

    // Evict the dead provider and add a fresh replacement.
    sim.pool.evict(&victim_id, EvictionReason::LivenessExhausted).unwrap();
    sim.pool.add([100u8; 32], SubstrateLedger::new());

    // 50 recovery epochs: old tracker counts dilute; new provider drawn equally.
    for _ in 0..50 { sim.run_epoch(10); }

    let post_margin = sim.steady_stability_margin()
        .expect("recovery: must have Steady epochs after 60 total epochs");
    assert!(
        post_margin > 0.0,
        "post-eviction recovery: steady margin must be positive; got {}",
        post_margin
    );
}

// ── §S39. Eviction does not convert provider failure into T2 thrash ───────────
//
// evict() removes from active (no epoch_count increment).
// add() restores active count (no epoch_count increment).
// Only force_rotate() counts as epoch: total_rotations() == 1 throughout.
// margin_t2 stays positive — eviction does not create churn.

#[test]
fn sim_s39_eviction_does_not_convert_provider_failure_into_t2_thrash() {
    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(2)
        .with_exposure_reset_policy(ExposureResetPolicy::OnRotation)
        .with_liveness(1, u64::MAX)
        .with_eviction(EvictionConfig {
            liveness_cooldown_secs:     300,
            equivocation_cooldown_secs: 3600,
            max_re_admissions:          3,
        });
    for i in 0..6u8 { pool.add([i; 32], SubstrateLedger::new()); }

    let mut sim = PoolSimulator::new(pool);
    sim.pool.force_rotate(&mut sim.rng);

    let victim_id = sim.pool.active_set_snapshot()[0];
    sim.pool.record_failure(victim_id);

    for _ in 0..10 { sim.run_epoch(10); }
    sim.pool.evict(&victim_id, EvictionReason::LivenessExhausted).unwrap();
    sim.pool.add([100u8; 32], SubstrateLedger::new());
    for _ in 0..50 { sim.run_epoch(10); }

    assert!(
        sim.margin_t2() > 0.0,
        "eviction must NOT create T2 thrash; got margin_t2={}",
        sim.margin_t2()
    );
    assert_eq!(
        sim.total_rotations(), 1,
        "evict()+add() must not increment epoch_count; \
         expected 1 rotation (force_rotate only), got {}",
        sim.total_rotations()
    );
}

// ── §S40. Repeat offender readmission is rejected during liveness cooldown ────
//
// Admit via Ed25519 challenge-response. Evict with LivenessExhausted.
// Immediate re-admission request must return EvictionCooldown (liveness_cooldown_secs=9999).

#[test]
fn sim_s40_repeat_offender_readmission_is_rejected_or_penalized() {
    let kp = KeyPair::generate();
    let provider_id = kp.public;

    let mut pool = ProviderPool::new(SamplingStrategy::RandomK(1))
        .with_active_window(4)
        .with_admission(AdmissionConfig {
            max_admits_per_window: 5,
            window_duration:       Duration::from_secs(60),
            challenge_ttl:         Duration::from_secs(60),
        })
        .with_eviction(EvictionConfig {
            liveness_cooldown_secs:     9999,
            equivocation_cooldown_secs: 3600,
            max_re_admissions:          3,
        });

    // Admit via challenge-response gate.
    let challenge = pool.request_admission(provider_id).unwrap();
    let sig = kp.sign(&admission_challenge_message(&provider_id, &challenge));
    pool.complete_admission(provider_id, &sig, SubstrateLedger::new()).unwrap();

    // Evict for liveness exhaustion.
    pool.evict(&provider_id, EvictionReason::LivenessExhausted).unwrap();

    // Immediate re-admission must be blocked by the liveness cooldown.
    let err = pool.request_admission(provider_id).unwrap_err();
    assert!(
        matches!(err, AdmissionError::EvictionCooldown { .. }),
        "readmission during liveness cooldown must return EvictionCooldown; got {err:?}"
    );
}

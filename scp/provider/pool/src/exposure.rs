use std::collections::HashMap;

/// Snapshot of observed provider selection exposure for a pool.
///
/// Computed from the pool's internal `ExposureTracker`, which records which
/// providers appeared in `sample()` quorums and how often. All rates are
/// fractions of sample() calls, not individual provider appearances.
pub struct ExposureEstimate {
    /// Shannon entropy (bits) of the observed provider selection distribution.
    /// Higher = more uniform = more privacy-preserving.
    /// Theoretical maximum = log2(active_set_size) for uniform selection.
    pub selection_entropy_bits: f64,

    /// EWMA-smoothed entropy (bits). Lags behind `selection_entropy_bits` by
    /// `1/ewma_alpha` samples. Preserved across `reset()` calls to prevent
    /// `EntropyTriggered` from re-firing immediately after a reset (anti-thrashing).
    pub smoothed_selection_entropy_bits: f64,

    /// Fraction of `sample()` calls in which the most-selected provider appeared.
    /// In an n-provider uniform pool: ~1/n. Lower = harder to infer membership.
    pub max_selection_rate: f64,

    /// Total `sample()` calls recorded. Zero means no samples yet.
    pub total_samples: u64,

    /// Confidence-weighted total samples after applying exponential decay.
    ///
    /// Equal to `total_samples` when no decay is configured. Decays toward
    /// zero with half-life `decay_half_life_secs` as time passes since the
    /// last `sample()` call. Ratio-based fields (`selection_entropy_bits`,
    /// `max_selection_rate`) are unaffected by decay.
    pub effective_total_samples: f64,

    /// Shannon entropy (bits) of the observed provider *response* distribution.
    ///
    /// Computed from `record_response()` calls rather than selection events.
    /// Dead providers contribute 0 to response entropy regardless of how often they are
    /// selected, so this value falls below `selection_entropy_bits` when providers are silent.
    pub response_entropy_bits: f64,

    /// EWMA-smoothed response entropy. Preserved across `reset()` — anti-thrashing.
    pub smoothed_response_entropy_bits: f64,

    /// Total `record_response()` calls recorded. Zero means no responses yet.
    pub response_total_samples: u64,
}

impl ExposureEstimate {
    /// Probability that an adversary correctly identifies the most-exposed
    /// provider as a pool member after observing `n` independent `sample()` quorums.
    ///
    /// Model: the most-exposed provider appears in each sample with probability
    /// `max_selection_rate`. After n samples, the adversary observes it at least
    /// once with probability `1 - (1 - max_selection_rate)^n`.
    pub fn membership_confidence_after(&self, n: u64) -> f64 {
        if self.max_selection_rate <= 0.0 || n == 0 {
            return 0.0;
        }
        1.0 - (1.0 - self.max_selection_rate).powi(n as i32)
    }
}

/// Per-provider selection probability distribution, normalized to sum ≤ 1.0.
///
/// Each entry is `(provider_id, probability)` where probability = appearances[i] / sum(appearances).
/// Returns empty Vec when no samples have been recorded.
pub struct ExposureDistribution {
    pub rates: Vec<([u8; 32], f64)>,
}

pub(crate) struct ExposureTracker {
    pub(crate) appearances:               HashMap<[u8; 32], u64>,
    pub(crate) total_samples:             u64,
    pub(crate) smoothed_entropy:          f64,         // EWMA; NOT zeroed by reset() — anti-thrashing
    pub(crate) ewma_alpha:                f64,         // default 1.0 = no smoothing (smoothed == raw)
    pub(crate) decay_half_life_secs:      Option<u64>, // None = no decay
    pub(crate) last_record_secs:          u64,         // wall-clock of most recent record() call
    pub(crate) response_appearances:      HashMap<[u8; 32], u64>,
    pub(crate) response_total:            u64,
    pub(crate) response_smoothed_entropy: f64,         // EWMA; NOT zeroed by reset() — anti-thrashing
}

impl ExposureTracker {
    pub(crate) fn new() -> Self {
        Self {
            appearances:               HashMap::new(),
            total_samples:             0,
            smoothed_entropy:          0.0,
            ewma_alpha:                1.0,
            decay_half_life_secs:      None,
            last_record_secs:          0,
            response_appearances:      HashMap::new(),
            response_total:            0,
            response_smoothed_entropy: 0.0,
        }
    }

    pub(crate) fn reset(&mut self) {
        self.appearances.clear();
        self.total_samples = 0;
        self.response_appearances.clear();
        self.response_total = 0;
        // smoothed_entropy and response_smoothed_entropy intentionally NOT reset —
        // prevents EntropyTriggered from re-firing immediately after a reset.
    }

    pub(crate) fn record(&mut self, provider_ids: &[[u8; 32]]) {
        self.total_samples += 1;
        for id in provider_ids {
            *self.appearances.entry(*id).or_insert(0) += 1;
        }
        self.last_record_secs = crate::now_secs();
        let raw = self.estimate_raw_entropy();
        self.smoothed_entropy = self.ewma_alpha * raw
            + (1.0 - self.ewma_alpha) * self.smoothed_entropy;
    }

    pub(crate) fn record_response(&mut self, provider_id: &[u8; 32]) {
        self.response_total += 1;
        *self.response_appearances.entry(*provider_id).or_insert(0) += 1;
        let raw = self.estimate_raw_response_entropy();
        self.response_smoothed_entropy = self.ewma_alpha * raw
            + (1.0 - self.ewma_alpha) * self.response_smoothed_entropy;
    }

    pub(crate) fn rate(&self, pid: &[u8; 32]) -> f64 {
        if self.total_samples == 0 { return 0.0; }
        *self.appearances.get(pid).unwrap_or(&0) as f64 / self.total_samples as f64
    }

    fn estimate_raw_entropy(&self) -> f64 {
        if self.total_samples == 0 { return 0.0; }
        let n = self.total_samples as f64;
        self.appearances.values()
            .map(|&c| {
                let p = c as f64 / n;
                if p > 0.0 { -p * p.log2() } else { 0.0 }
            })
            .sum()
    }

    fn estimate_raw_response_entropy(&self) -> f64 {
        if self.response_total == 0 { return 0.0; }
        let n = self.response_total as f64;
        self.response_appearances.values()
            .map(|&c| {
                let p = c as f64 / n;
                if p > 0.0 { -p * p.log2() } else { 0.0 }
            })
            .sum()
    }

    pub(crate) fn estimate_at(&self, now: u64) -> ExposureEstimate {
        let raw = self.estimate_raw_entropy();
        let max_rate = if self.total_samples == 0 {
            0.0
        } else {
            let n = self.total_samples as f64;
            self.appearances.values()
                .map(|&c| c as f64 / n)
                .fold(0.0f64, f64::max)
        };
        let effective = match self.decay_half_life_secs {
            None => self.total_samples as f64,
            Some(hl) => {
                let elapsed = now.saturating_sub(self.last_record_secs) as f64;
                self.total_samples as f64 * 0.5_f64.powf(elapsed / hl as f64)
            }
        };
        ExposureEstimate {
            selection_entropy_bits:          raw,
            smoothed_selection_entropy_bits: self.smoothed_entropy,
            max_selection_rate:              max_rate,
            total_samples:                   self.total_samples,
            effective_total_samples:         effective,
            response_entropy_bits:           self.estimate_raw_response_entropy(),
            smoothed_response_entropy_bits:  self.response_smoothed_entropy,
            response_total_samples:          self.response_total,
        }
    }

    pub(crate) fn estimate(&self) -> ExposureEstimate {
        self.estimate_at(crate::now_secs())
    }

    pub(crate) fn distribution(&self) -> ExposureDistribution {
        let total_appearances: u64 = self.appearances.values().sum();
        if total_appearances == 0 {
            return ExposureDistribution { rates: Vec::new() };
        }
        let n = total_appearances as f64;
        let rates = self.appearances.iter()
            .map(|(id, &c)| (*id, c as f64 / n))
            .collect();
        ExposureDistribution { rates }
    }
}

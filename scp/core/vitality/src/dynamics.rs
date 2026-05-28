use crate::scalar::{round_ratio_away_from_zero, Centered, Unit, HALF_SCALE, SCALE};
use crate::state::VibeState;

/// Default per-axis retention factors (≈ exp(-rate) × SCALE).
const DEFAULT_ACTIVATION_RETENTION: i64 = 548_812; // ≈ exp(-0.60)
const DEFAULT_VALENCE_RETENTION: i64 = 860_708;    // ≈ exp(-0.15)
const DEFAULT_STABILITY_RETENTION: i64 = 740_818;  // ≈ exp(-0.30)

/// Per-axis deterministic recovery constants.
///
/// Each constant is a fixed-point multiplier in [0, SCALE] approximating
/// exp(-rate) where rate is the decay coefficient per tick.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StateDynamics {
    activation_retention: i64,
    valence_retention: i64,
    stability_retention: i64,
}

impl StateDynamics {
    pub const fn new(
        activation_retention: i64,
        valence_retention: i64,
        stability_retention: i64,
    ) -> Self {
        Self {
            activation_retention,
            valence_retention,
            stability_retention,
        }
    }

    /// The canonical neutral dynamics matching the default retention constants.
    pub const fn default_neutral() -> Self {
        Self::new(
            DEFAULT_ACTIVATION_RETENTION,
            DEFAULT_VALENCE_RETENTION,
            DEFAULT_STABILITY_RETENTION,
        )
    }

    /// Advances state by exactly one recovery step.
    ///
    /// For each axis, the offset from the axis baseline decays by the
    /// corresponding retention factor using exact integer arithmetic.
    pub fn advance_one(self, state: VibeState) -> VibeState {
        let activation = recover_unit(state.activation(), self.activation_retention);
        let valence = recover_centered(state.valence(), self.valence_retention);
        let stability = recover_unit(state.stability(), self.stability_retention);
        VibeState::new(activation, valence, stability)
    }

    /// Advances state by exactly n sequential recovery steps.
    ///
    /// Each step is individually rounded — this is not equivalent to
    /// applying a single combined exponent.
    pub fn advance_ticks(self, mut state: VibeState, n: u64) -> VibeState {
        for _ in 0..n {
            state = self.advance_one(state);
        }
        state
    }
}

/// Recovers a Unit (baseline = HALF_SCALE) by one decay step.
fn recover_unit(current: Unit, retention: i64) -> Unit {
    let offset = current.raw() - HALF_SCALE;
    let product = offset * retention;
    let retained_offset = round_ratio_away_from_zero(product, SCALE);
    Unit::from_clamped(HALF_SCALE + retained_offset)
}

/// Recovers a Centered value (baseline = 0) by one decay step.
fn recover_centered(current: Centered, retention: i64) -> Centered {
    let product = current.raw() * retention;
    let retained = round_ratio_away_from_zero(product, SCALE);
    Centered::from_clamped(retained)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scalar::Unit;

    #[test]
    fn activation_single_step_exact_recovery() {
        // Start at 700_000 (offset +200_000 from baseline 500_000)
        // product = 200_000 * 548_812 = 109_762_400_000
        // retained = round(109_762_400_000 / 1_000_000) = 109_762
        // result = 500_000 + 109_762 = 609_762
        let dynamics = StateDynamics::default_neutral();
        let displaced = VibeState::new(
            Unit::from_raw(700_000).unwrap(),
            Centered::ZERO,
            Unit::from_raw(300_000).unwrap(),
        );
        let recovered = dynamics.advance_one(displaced);
        assert_eq!(recovered.activation().raw(), 609_762);
        assert_eq!(recovered.stability().raw(), 351_836);
    }

    #[test]
    fn five_steps_match_advance_ticks() {
        let dynamics = StateDynamics::default_neutral();
        let displaced = VibeState::new(
            Unit::from_raw(700_000).unwrap(),
            Centered::ZERO,
            Unit::from_raw(300_000).unwrap(),
        );
        let mut sequential = displaced;
        for _ in 0..5 {
            sequential = dynamics.advance_one(sequential);
        }
        let batch = dynamics.advance_ticks(displaced, 5);
        assert_eq!(sequential, batch);
    }

    #[test]
    fn neutral_state_is_fixed_point() {
        let dynamics = StateDynamics::default_neutral();
        let neutral = VibeState::neutral();
        let after = dynamics.advance_one(neutral);
        assert_eq!(after, neutral);
    }
}

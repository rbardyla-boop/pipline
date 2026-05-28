use crate::observation::NetDelta;
use crate::scalar::{Centered, Unit, SCALE};

/// The authoritative fixed-point vibe state.
///
/// All fields are bounded integers at SCALE = 1_000_000:
/// - activation ∈ [0, SCALE]
/// - valence ∈ [-SCALE, SCALE]
/// - stability ∈ [0, SCALE]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct VibeState {
    activation: Unit,
    valence: Centered,
    stability: Unit,
}

impl VibeState {
    /// Constructs a VibeState from validated components.
    pub const fn new(activation: Unit, valence: Centered, stability: Unit) -> Self {
        Self {
            activation,
            valence,
            stability,
        }
    }

    /// The neutral starting state: activation=0.5, valence=0, stability=0.5.
    pub const fn neutral() -> Self {
        Self {
            activation: Unit::HALF,
            valence: Centered::ZERO,
            stability: Unit::HALF,
        }
    }

    pub const fn activation(self) -> Unit {
        self.activation
    }

    pub const fn valence(self) -> Centered {
        self.valence
    }

    pub const fn stability(self) -> Unit {
        self.stability
    }

    /// Applies a net delta to all three dimensions with a single bounded clamp.
    ///
    /// Addition may temporarily exceed bounds; the clamp is the only correction.
    pub fn apply_delta(self, delta: NetDelta) -> Self {
        let new_activation = (self.activation.raw() + delta.activation_shift)
            .clamp(0, SCALE);
        let new_valence = (self.valence.raw() + delta.valence_shift)
            .clamp(-SCALE, SCALE);
        let new_stability = (self.stability.raw() + delta.stability_shift)
            .clamp(0, SCALE);

        Self {
            activation: Unit::from_clamped(new_activation),
            valence: Centered::from_clamped(new_valence),
            stability: Unit::from_clamped(new_stability),
        }
    }

    /// Projects activation and stability into a centered [-SCALE, SCALE] resonance vector.
    ///
    /// Formula: centered_value = (2 * unit_value) - SCALE
    pub fn resonance_vector(self) -> (Centered, Centered, Centered) {
        let x = self.valence;
        let y = Centered::from_clamped(2 * self.activation.raw() - SCALE);
        let z = Centered::from_clamped(2 * self.stability.raw() - SCALE);
        (x, y, z)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn neutral_state_values() {
        let s = VibeState::neutral();
        assert_eq!(s.activation().raw(), 500_000);
        assert_eq!(s.valence().raw(), 0);
        assert_eq!(s.stability().raw(), 500_000);
    }

    #[test]
    fn disruption_delta_applies_correctly() {
        let s = VibeState::neutral();
        let delta = NetDelta {
            activation_shift: 200_000,
            valence_shift: 0,
            stability_shift: -200_000,
        };
        let after = s.apply_delta(delta);
        assert_eq!(after.activation().raw(), 700_000);
        assert_eq!(after.valence().raw(), 0);
        assert_eq!(after.stability().raw(), 300_000);
    }

    #[test]
    fn clamp_at_upper_bound() {
        let s = VibeState::neutral();
        let delta = NetDelta {
            activation_shift: 600_000,
            valence_shift: 0,
            stability_shift: 0,
        };
        let after = s.apply_delta(delta);
        assert_eq!(after.activation().raw(), SCALE);
    }

    #[test]
    fn clamp_at_lower_bound() {
        let s = VibeState::neutral();
        let delta = NetDelta {
            activation_shift: -600_000,
            valence_shift: 0,
            stability_shift: 0,
        };
        let after = s.apply_delta(delta);
        assert_eq!(after.activation().raw(), 0);
    }
}

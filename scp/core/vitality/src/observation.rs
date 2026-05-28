/// A discrete symbolic event that modifies vibe state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Observation {
    /// Positive reinforcement: small boost to all dimensions.
    Reinforcement,
    /// Challenge: high activation, negative valence, reduced stability.
    Challenge,
    /// Disruption: large activation spike with significant stability loss.
    Disruption,
    /// Resolution: activation reduction with full stability recovery.
    Resolution,
}

/// The fixed-point delta produced by a single observation event.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ObservationDelta {
    pub activation: i64,
    pub valence: i64,
    pub stability: i64,
}

impl Observation {
    /// Returns the exact fixed-point delta for this observation type.
    pub const fn delta(self) -> ObservationDelta {
        match self {
            Self::Reinforcement => ObservationDelta {
                activation: 50_000,
                valence: 100_000,
                stability: 50_000,
            },
            Self::Challenge => ObservationDelta {
                activation: 100_000,
                valence: -100_000,
                stability: -50_000,
            },
            Self::Disruption => ObservationDelta {
                activation: 200_000,
                valence: 0,
                stability: -200_000,
            },
            Self::Resolution => ObservationDelta {
                activation: -150_000,
                valence: 0,
                stability: 200_000,
            },
        }
    }
}

/// Net commutative delta from all same-frame observations combined.
///
/// This is an unbounded accumulator; clamping occurs only when applied to state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NetDelta {
    pub activation_shift: i64,
    pub valence_shift: i64,
    pub stability_shift: i64,
}

impl NetDelta {
    pub const ZERO: Self = Self {
        activation_shift: 0,
        valence_shift: 0,
        stability_shift: 0,
    };
}

/// Total unsigned magnitude of all per-axis deltas applied in a frame.
///
/// Unlike NetDelta, cancellations do not reduce signal load — it measures
/// gross pressure regardless of direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SignalLoad {
    pub activation: i64,
    pub valence: i64,
    pub stability: i64,
}

impl SignalLoad {
    pub const ZERO: Self = Self {
        activation: 0,
        valence: 0,
        stability: 0,
    };

    pub fn total(self) -> i64 {
        self.activation + self.valence + self.stability
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disruption_delta_values() {
        let d = Observation::Disruption.delta();
        assert_eq!(d.activation, 200_000);
        assert_eq!(d.valence, 0);
        assert_eq!(d.stability, -200_000);
    }

    #[test]
    fn cancellation_net_delta() {
        let dis = Observation::Disruption.delta();
        let res = Observation::Resolution.delta();
        let net_activation = dis.activation + res.activation;
        let net_stability = dis.stability + res.stability;
        assert_eq!(net_activation, 50_000);
        assert_eq!(net_stability, 0);
    }

    #[test]
    fn cancellation_signal_load() {
        let dis = Observation::Disruption.delta();
        let res = Observation::Resolution.delta();
        let load_activation = dis.activation.abs() + res.activation.abs();
        let load_stability = dis.stability.abs() + res.stability.abs();
        assert_eq!(load_activation, 350_000);
        assert_eq!(load_stability, 400_000);
    }
}

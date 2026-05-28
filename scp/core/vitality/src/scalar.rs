/// Fixed-point scale: all unit values are multiplied by 1_000_000.
pub(crate) const SCALE: i64 = 1_000_000;

/// Half of SCALE — the neutral baseline for activation and stability.
pub(crate) const HALF_SCALE: i64 = SCALE / 2;

/// A fixed-point value in [0, SCALE], representing the range [0.0, 1.0].
///
/// Used for activation and stability — both are non-negative and bounded at 1.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Unit(i64);

impl Unit {
    pub const ZERO: Self = Self(0);
    pub const HALF: Self = Self(HALF_SCALE);
    pub const MAX: Self = Self(SCALE);

    /// Constructs a Unit from a raw integer in [0, SCALE].
    /// Returns None if the value is out of range.
    pub const fn from_raw(raw: i64) -> Option<Self> {
        if raw >= 0 && raw <= SCALE {
            Some(Self(raw))
        } else {
            None
        }
    }

    /// Constructs a Unit by clamping the raw value to [0, SCALE].
    /// Used internally where clamping has already happened.
    pub(crate) const fn from_clamped(raw: i64) -> Self {
        let clamped = if raw < 0 { 0 } else if raw > SCALE { SCALE } else { raw };
        Self(clamped)
    }

    pub const fn raw(self) -> i64 {
        self.0
    }
}

/// A fixed-point value in [-SCALE, SCALE], representing the range [-1.0, 1.0].
///
/// Used for valence — it can be positive (good) or negative (bad).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Centered(i64);

impl Centered {
    pub const ZERO: Self = Self(0);
    pub const MAX: Self = Self(SCALE);
    pub const MIN: Self = Self(-SCALE);

    /// Constructs a Centered from a raw integer in [-SCALE, SCALE].
    /// Returns None if the value is out of range.
    pub const fn from_raw(raw: i64) -> Option<Self> {
        if raw >= -SCALE && raw <= SCALE {
            Some(Self(raw))
        } else {
            None
        }
    }

    /// Constructs a Centered by clamping the raw value to [-SCALE, SCALE].
    pub(crate) const fn from_clamped(raw: i64) -> Self {
        let clamped = if raw < -SCALE { -SCALE } else if raw > SCALE { SCALE } else { raw };
        Self(clamped)
    }

    pub const fn raw(self) -> i64 {
        self.0
    }
}

/// Rounds (numerator / denominator) to the nearest integer, with ties broken
/// away from zero (symmetric half-up rounding).
///
/// Denominator must be positive.
pub(crate) fn round_ratio_away_from_zero(numerator: i64, denominator: i64) -> i64 {
    debug_assert!(denominator > 0);
    let half = denominator / 2;
    if numerator >= 0 {
        (numerator + half) / denominator
    } else {
        -((-numerator + half) / denominator)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unit_round_trip() {
        let u = Unit::from_raw(700_000).unwrap();
        assert_eq!(u.raw(), 700_000);
    }

    #[test]
    fn unit_out_of_range_rejected() {
        assert!(Unit::from_raw(-1).is_none());
        assert!(Unit::from_raw(1_000_001).is_none());
    }

    #[test]
    fn centered_round_trip() {
        let c = Centered::from_raw(-400_000).unwrap();
        assert_eq!(c.raw(), -400_000);
    }

    #[test]
    fn round_ratio_exact_recovery_trace() {
        // Activation recovery: offset=200_000, retention=548_812
        // product = 109_762_400_000
        // expected retained offset = 109_762
        let retained = round_ratio_away_from_zero(109_762_400_000_i64, SCALE);
        assert_eq!(retained, 109_762);
    }

    #[test]
    fn round_ratio_negative_offset() {
        // Stability recovery: offset=-200_000, retention=740_818
        // product = -148_163_600_000
        // expected retained offset = -148_164
        let retained = round_ratio_away_from_zero(-148_163_600_000_i64, SCALE);
        assert_eq!(retained, -148_164);
    }
}

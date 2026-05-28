use crate::dynamics::StateDynamics;
use crate::frame::{FrameError, FrameImpact, ObservationFrame};
use crate::state::VibeState;

/// Errors that prevent a tick from being committed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TickError {
    Frame(FrameError),
    TickCounterOverflow,
}

/// Complete deterministic output of one evaluated tick transaction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TickOutcome {
    pub state_before: VibeState,
    pub impact: FrameImpact,
    pub state_after_observations: VibeState,
    pub state_after_recovery: VibeState,
}

/// Receipt created only after a successful engine commit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TickReceipt {
    /// Number of successfully committed transitions since engine initialization.
    pub completed_ticks: u64,
    pub outcome: TickOutcome,
}

/// Executes one authoritative state transition without mutating external state.
///
/// Canonical order:
/// 1. Aggregate all same-frame event effects.
/// 2. Apply the exactly accumulated fixed-point delta while representable
///    in checked i64, then clamp once at the bounded state container edge.
/// 3. Execute exactly one deterministic recovery step.
pub fn evaluate_tick(
    state: VibeState,
    frame: &ObservationFrame,
    dynamics: StateDynamics,
) -> Result<TickOutcome, TickError> {
    let impact = frame.compute_impact().map_err(TickError::Frame)?;

    let state_after_observations = state.apply_delta(impact.net_delta);
    let state_after_recovery = dynamics.advance_one(state_after_observations);

    Ok(TickOutcome {
        state_before: state,
        impact,
        state_after_observations,
        state_after_recovery,
    })
}

/// Thin transactional owner of committed simulation state.
///
/// This type does not assign tick labels, validate ingress, or store replay
/// history. It only commits successful state transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct VibeEngine {
    state: VibeState,
    dynamics: StateDynamics,
    completed_ticks: u64,
}

impl VibeEngine {
    pub const fn new(initial_state: VibeState, dynamics: StateDynamics) -> Self {
        Self {
            state: initial_state,
            dynamics,
            completed_ticks: 0,
        }
    }

    pub const fn default_neutral() -> Self {
        Self::new(VibeState::neutral(), StateDynamics::default_neutral())
    }

    pub const fn state(self) -> VibeState {
        self.state
    }

    pub const fn dynamics(self) -> StateDynamics {
        self.dynamics
    }

    pub const fn completed_ticks(self) -> u64 {
        self.completed_ticks
    }

    /// Evaluates and commits exactly one frame transaction.
    ///
    /// State and tick counter are updated only if all operations succeed.
    pub fn process_tick(&mut self, frame: &ObservationFrame) -> Result<TickReceipt, TickError> {
        let outcome = evaluate_tick(self.state, frame, self.dynamics)?;

        let next_completed_ticks = self
            .completed_ticks
            .checked_add(1)
            .ok_or(TickError::TickCounterOverflow)?;

        self.state = outcome.state_after_recovery;
        self.completed_ticks = next_completed_ticks;

        Ok(TickReceipt {
            completed_ticks: next_completed_ticks,
            outcome,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observation::Observation;
    use crate::scalar::{Centered, Unit};
    use crate::tracking::{EventId, ObservationEnvelope, SourceEpoch, SourceId};

    fn tracked_event(
        event_id: u64,
        sequence: u64,
        observation: Observation,
    ) -> ObservationEnvelope {
        ObservationEnvelope::new(
            EventId::new(event_id),
            SourceId::new(1),
            SourceEpoch::new(1),
            sequence,
            observation,
        )
    }

    #[test]
    fn disruption_tick_reaches_exact_fixed_point_targets() {
        let mut engine = VibeEngine::default_neutral();

        let frame = ObservationFrame::from_events(vec![
            tracked_event(1, 1, Observation::Disruption),
        ])
        .unwrap();

        let receipt = engine.process_tick(&frame).unwrap();

        assert_eq!(
            receipt.outcome.state_after_observations.activation().raw(),
            700_000
        );
        assert_eq!(
            receipt.outcome.state_after_observations.stability().raw(),
            300_000
        );
        assert_eq!(
            receipt.outcome.state_after_recovery.activation().raw(),
            609_762
        );
        assert_eq!(
            receipt.outcome.state_after_recovery.stability().raw(),
            351_836
        );
        assert_eq!(engine.completed_ticks(), 1);
        assert_eq!(engine.state(), receipt.outcome.state_after_recovery);
    }

    #[test]
    fn quiet_tick_advances_recovery_without_new_events() {
        let dynamics = StateDynamics::default_neutral();
        let displaced = VibeState::new(
            Unit::from_raw(700_000).unwrap(),
            Centered::ZERO,
            Unit::from_raw(300_000).unwrap(),
        );

        let mut engine = VibeEngine::new(displaced, dynamics);
        let empty_frame = ObservationFrame::new();

        let receipt = engine.process_tick(&empty_frame).unwrap();

        assert_eq!(receipt.outcome.impact.observation_count, 0);
        assert_eq!(
            receipt.outcome.state_after_recovery.activation().raw(),
            609_762
        );
        assert_eq!(
            receipt.outcome.state_after_recovery.stability().raw(),
            351_836
        );
    }

    #[test]
    fn five_quiet_ticks_execute_five_exact_recovery_steps() {
        let dynamics = StateDynamics::default_neutral();
        let displaced = VibeState::new(
            Unit::from_raw(700_000).unwrap(),
            Centered::ZERO,
            Unit::from_raw(300_000).unwrap(),
        );

        let empty_frame = ObservationFrame::new();
        let mut engine = VibeEngine::new(displaced, dynamics);

        for _ in 0..5 {
            engine.process_tick(&empty_frame).unwrap();
        }

        assert_eq!(engine.state(), dynamics.advance_ticks(displaced, 5));
        assert_eq!(engine.completed_ticks(), 5);
    }

    #[test]
    fn cancelled_burst_retains_signal_load_in_receipt() {
        let mut engine = VibeEngine::default_neutral();

        let frame = ObservationFrame::from_events(vec![
            tracked_event(1, 1, Observation::Disruption),
            tracked_event(2, 2, Observation::Resolution),
        ])
        .unwrap();

        let receipt = engine.process_tick(&frame).unwrap();

        assert_eq!(receipt.outcome.impact.net_delta.activation_shift, 50_000);
        assert_eq!(receipt.outcome.impact.net_delta.stability_shift, 0);
        assert_eq!(receipt.outcome.impact.signal_load.activation, 350_000);
        assert_eq!(receipt.outcome.impact.signal_load.stability, 400_000);
    }

    #[test]
    fn pure_evaluation_and_engine_commit_match_exactly() {
        let state = VibeState::neutral();
        let dynamics = StateDynamics::default_neutral();

        let frame = ObservationFrame::from_events(vec![
            tracked_event(1, 1, Observation::Disruption),
        ])
        .unwrap();

        let expected = evaluate_tick(state, &frame, dynamics).unwrap();

        let mut engine = VibeEngine::new(state, dynamics);
        let receipt = engine.process_tick(&frame).unwrap();

        assert_eq!(receipt.outcome, expected);
        assert_eq!(engine.state(), expected.state_after_recovery);
    }
}

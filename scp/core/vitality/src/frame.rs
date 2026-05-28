use std::collections::HashSet;

use crate::observation::{NetDelta, SignalLoad};
use crate::tracking::{EventId, ObservationEnvelope};

/// Error returned when constructing an ObservationFrame from invalid event sets.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameBuildError {
    /// Two events in the same frame share an EventId, which violates uniqueness.
    DuplicateEventId { event_id: EventId },
}

/// Error returned when computing a frame's aggregate impact fails.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameError {
    /// The accumulated delta overflowed the i64 representation.
    DeltaOverflow,
}

/// The aggregate result of evaluating all events in one tick frame.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FrameImpact {
    /// Net commutative delta after all same-frame events cancel or reinforce.
    pub net_delta: NetDelta,
    /// Gross unsigned pressure per axis — cancellations do not reduce load.
    pub signal_load: SignalLoad,
    /// Number of events processed in this frame.
    pub observation_count: usize,
}

/// An ordered, validated set of observation events for one tick.
///
/// Events are held in canonical sort order (source_id → source_epoch →
/// source_sequence → event_id) and guaranteed to have unique EventIds.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ObservationFrame {
    events: Vec<ObservationEnvelope>,
}

impl ObservationFrame {
    /// Creates an empty frame — valid for quiet (recovery-only) ticks.
    pub fn new() -> Self {
        Self { events: Vec::new() }
    }

    /// Constructs a frame from an event list, checking for duplicate EventIds.
    ///
    /// The caller is responsible for sorting events before calling this.
    pub fn from_events(events: Vec<ObservationEnvelope>) -> Result<Self, FrameBuildError> {
        let mut seen: HashSet<EventId> = HashSet::with_capacity(events.len());
        for event in &events {
            if !seen.insert(event.event_id()) {
                return Err(FrameBuildError::DuplicateEventId {
                    event_id: event.event_id(),
                });
            }
        }
        Ok(Self { events })
    }

    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    pub fn len(&self) -> usize {
        self.events.len()
    }

    /// Returns the events, consuming the frame.
    pub fn into_events(self) -> Vec<ObservationEnvelope> {
        self.events
    }

    /// Computes the aggregate net delta and signal load for this frame.
    ///
    /// Uses checked arithmetic to guard against i64 overflow on very large frames.
    pub fn compute_impact(&self) -> Result<FrameImpact, FrameError> {
        let mut act: i64 = 0;
        let mut val: i64 = 0;
        let mut stab: i64 = 0;
        let mut load_act: i64 = 0;
        let mut load_val: i64 = 0;
        let mut load_stab: i64 = 0;

        for event in &self.events {
            let delta = event.observation().delta();

            act = act.checked_add(delta.activation).ok_or(FrameError::DeltaOverflow)?;
            val = val.checked_add(delta.valence).ok_or(FrameError::DeltaOverflow)?;
            stab = stab.checked_add(delta.stability).ok_or(FrameError::DeltaOverflow)?;

            load_act = load_act
                .checked_add(delta.activation.abs())
                .ok_or(FrameError::DeltaOverflow)?;
            load_val = load_val
                .checked_add(delta.valence.abs())
                .ok_or(FrameError::DeltaOverflow)?;
            load_stab = load_stab
                .checked_add(delta.stability.abs())
                .ok_or(FrameError::DeltaOverflow)?;
        }

        Ok(FrameImpact {
            net_delta: NetDelta {
                activation_shift: act,
                valence_shift: val,
                stability_shift: stab,
            },
            signal_load: SignalLoad {
                activation: load_act,
                valence: load_val,
                stability: load_stab,
            },
            observation_count: self.events.len(),
        })
    }
}

impl Default for ObservationFrame {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observation::Observation;
    use crate::tracking::{EventId, ObservationEnvelope, SourceEpoch, SourceId};

    fn make_event(id: u64, obs: Observation) -> ObservationEnvelope {
        ObservationEnvelope::new(
            EventId::new(id),
            SourceId::new(1),
            SourceEpoch::new(1),
            id,
            obs,
        )
    }

    #[test]
    fn empty_frame_zero_impact() {
        let frame = ObservationFrame::new();
        let impact = frame.compute_impact().unwrap();
        assert_eq!(impact.observation_count, 0);
        assert_eq!(impact.net_delta.activation_shift, 0);
        assert_eq!(impact.signal_load.activation, 0);
    }

    #[test]
    fn disruption_frame_impact() {
        let frame = ObservationFrame::from_events(vec![
            make_event(1, Observation::Disruption),
        ])
        .unwrap();
        let impact = frame.compute_impact().unwrap();
        assert_eq!(impact.net_delta.activation_shift, 200_000);
        assert_eq!(impact.net_delta.stability_shift, -200_000);
        assert_eq!(impact.signal_load.activation, 200_000);
        assert_eq!(impact.signal_load.stability, 200_000);
    }

    #[test]
    fn cancellation_burst_signal_load_preserved() {
        let frame = ObservationFrame::from_events(vec![
            make_event(1, Observation::Disruption),
            make_event(2, Observation::Resolution),
        ])
        .unwrap();
        let impact = frame.compute_impact().unwrap();
        assert_eq!(impact.net_delta.activation_shift, 50_000);
        assert_eq!(impact.net_delta.stability_shift, 0);
        assert_eq!(impact.signal_load.activation, 350_000);
        assert_eq!(impact.signal_load.stability, 400_000);
    }

    #[test]
    fn duplicate_event_id_rejected() {
        let result = ObservationFrame::from_events(vec![
            make_event(1, Observation::Disruption),
            make_event(1, Observation::Resolution),
        ]);
        assert_eq!(
            result,
            Err(FrameBuildError::DuplicateEventId {
                event_id: EventId::new(1)
            })
        );
    }
}

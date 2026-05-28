use std::collections::BTreeMap;

use crate::frame::{FrameBuildError, ObservationFrame};
use crate::tracking::ObservationEnvelope;

/// One deterministic logical simulation-time position.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct TickIndex(u64);

impl TickIndex {
    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub const fn raw(self) -> u64 {
        self.0
    }

    /// Returns the next tick index, or None on overflow.
    pub fn next(self) -> Option<Self> {
        self.0.checked_add(1).map(Self)
    }
}

/// An accepted tracked event assigned to one logical tick.
///
/// Target tick assignment is performed by an authoritative scheduler,
/// never inferred by FrameCollector from arrival timing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ScheduledObservation {
    target_tick: TickIndex,
    event: ObservationEnvelope,
}

impl ScheduledObservation {
    pub const fn new(target_tick: TickIndex, event: ObservationEnvelope) -> Self {
        Self { target_tick, event }
    }

    pub const fn target_tick(self) -> TickIndex {
        self.target_tick
    }

    pub const fn event(self) -> ObservationEnvelope {
        self.event
    }
}

/// A complete frame paired with its externally meaningful timeline index.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CollectedFrame {
    pub tick: TickIndex,
    pub frame: ObservationFrame,
}

/// Errors from FrameCollector operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CollectorError {
    /// Event targeted a tick that has already been emitted.
    TickAlreadyClosed {
        target_tick: TickIndex,
        next_open_tick: TickIndex,
    },

    /// Event is targeted too far ahead of the current open tick.
    TargetTooFarAhead {
        target_tick: TickIndex,
        next_open_tick: TickIndex,
        maximum_future_lead: u64,
    },

    /// The tick index counter overflowed u64.
    TickIndexOverflow,

    /// Frame construction failed (e.g. duplicate event ID).
    FrameBuild(FrameBuildError),
}

/// Buckets scheduled tracked events into deterministic tick frames.
///
/// This component never derives logical time from arrival time. Events
/// must arrive pre-labeled with their target tick.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FrameCollector {
    next_open_tick: TickIndex,
    maximum_future_lead: u64,
    pending: BTreeMap<TickIndex, Vec<ObservationEnvelope>>,
}

impl FrameCollector {
    pub fn new(starting_tick: TickIndex, maximum_future_lead: u64) -> Self {
        Self {
            next_open_tick: starting_tick,
            maximum_future_lead,
            pending: BTreeMap::new(),
        }
    }

    pub const fn next_open_tick(&self) -> TickIndex {
        self.next_open_tick
    }

    /// Accepts a scheduled event into the pending buffer.
    ///
    /// Rejects events targeting closed ticks or ticks beyond the future lead window.
    pub fn schedule(&mut self, scheduled: ScheduledObservation) -> Result<(), CollectorError> {
        let target_tick = scheduled.target_tick();

        if target_tick < self.next_open_tick {
            return Err(CollectorError::TickAlreadyClosed {
                target_tick,
                next_open_tick: self.next_open_tick,
            });
        }

        let maximum_allowed = self
            .next_open_tick
            .raw()
            .saturating_add(self.maximum_future_lead);

        if target_tick.raw() > maximum_allowed {
            return Err(CollectorError::TargetTooFarAhead {
                target_tick,
                next_open_tick: self.next_open_tick,
                maximum_future_lead: self.maximum_future_lead,
            });
        }

        self.pending
            .entry(target_tick)
            .or_default()
            .push(scheduled.event());

        Ok(())
    }

    /// Emits exactly the next tick as a CollectedFrame, including an empty
    /// frame when no events were scheduled for that tick.
    pub fn take_next_frame(&mut self) -> Result<CollectedFrame, CollectorError> {
        let tick = self.next_open_tick;

        let mut events = self.pending.remove(&tick).unwrap_or_default();

        // Canonical sort: source_id → source_epoch → source_sequence → event_id
        events.sort_by_key(|event| {
            (
                event.source_id().raw(),
                event.source_epoch().raw(),
                event.source_sequence(),
                event.event_id().raw(),
            )
        });

        let frame = ObservationFrame::from_events(events).map_err(CollectorError::FrameBuild)?;

        self.next_open_tick = tick.next().ok_or(CollectorError::TickIndexOverflow)?;

        Ok(CollectedFrame { tick, frame })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observation::Observation;
    use crate::tracking::{EventId, ObservationEnvelope, SourceEpoch, SourceId};

    fn event(
        event_id: u64,
        source_id: u32,
        sequence: u64,
        observation: Observation,
    ) -> ObservationEnvelope {
        ObservationEnvelope::new(
            EventId::new(event_id),
            SourceId::new(source_id),
            SourceEpoch::new(1),
            sequence,
            observation,
        )
    }

    #[test]
    fn events_are_emitted_only_in_assigned_target_tick() {
        let mut collector = FrameCollector::new(TickIndex::new(10), 16);

        collector
            .schedule(ScheduledObservation::new(
                TickIndex::new(12),
                event(1, 1, 1, Observation::Disruption),
            ))
            .unwrap();

        let tick_10 = collector.take_next_frame().unwrap();
        let tick_11 = collector.take_next_frame().unwrap();
        let tick_12 = collector.take_next_frame().unwrap();

        assert!(tick_10.frame.is_empty());
        assert!(tick_11.frame.is_empty());
        assert_eq!(tick_12.frame.len(), 1);
    }

    #[test]
    fn same_tick_arrival_order_is_canonicalized() {
        let first = event(1, 1, 1, Observation::Disruption);
        let second = event(2, 2, 1, Observation::Resolution);

        let mut a = FrameCollector::new(TickIndex::new(0), 4);
        let mut b = FrameCollector::new(TickIndex::new(0), 4);

        // Stage in different arrival orders
        a.schedule(ScheduledObservation::new(TickIndex::new(0), second)).unwrap();
        a.schedule(ScheduledObservation::new(TickIndex::new(0), first)).unwrap();

        b.schedule(ScheduledObservation::new(TickIndex::new(0), first)).unwrap();
        b.schedule(ScheduledObservation::new(TickIndex::new(0), second)).unwrap();

        assert_eq!(
            a.take_next_frame().unwrap(),
            b.take_next_frame().unwrap()
        );
    }

    #[test]
    fn event_for_closed_tick_is_rejected() {
        let mut collector = FrameCollector::new(TickIndex::new(0), 4);

        collector.take_next_frame().unwrap();

        let result = collector.schedule(ScheduledObservation::new(
            TickIndex::new(0),
            event(1, 1, 1, Observation::Disruption),
        ));

        assert_eq!(
            result,
            Err(CollectorError::TickAlreadyClosed {
                target_tick: TickIndex::new(0),
                next_open_tick: TickIndex::new(1),
            })
        );
    }

    #[test]
    fn event_too_far_ahead_is_rejected() {
        let mut collector = FrameCollector::new(TickIndex::new(0), 4);

        let result = collector.schedule(ScheduledObservation::new(
            TickIndex::new(5),
            event(1, 1, 1, Observation::Disruption),
        ));

        assert_eq!(
            result,
            Err(CollectorError::TargetTooFarAhead {
                target_tick: TickIndex::new(5),
                next_open_tick: TickIndex::new(0),
                maximum_future_lead: 4,
            })
        );
    }

    #[test]
    fn tick_index_advances_on_each_take() {
        let mut collector = FrameCollector::new(TickIndex::new(100), 16);
        assert_eq!(collector.next_open_tick(), TickIndex::new(100));
        collector.take_next_frame().unwrap();
        assert_eq!(collector.next_open_tick(), TickIndex::new(101));
    }
}

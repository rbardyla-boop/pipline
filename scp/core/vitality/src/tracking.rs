use crate::observation::Observation;

/// Unique identity for one observation event.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct EventId(u64);

impl EventId {
    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub const fn raw(self) -> u64 {
        self.0
    }
}

/// Identity for an upstream event producer.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SourceId(u32);

impl SourceId {
    pub const fn new(raw: u32) -> Self {
        Self(raw)
    }

    pub const fn raw(self) -> u32 {
        self.0
    }
}

/// Identity for one lifecycle session of a source.
///
/// A producer that restarts its sequence counter must increment its epoch.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SourceEpoch(u64);

impl SourceEpoch {
    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub const fn raw(self) -> u64 {
        self.0
    }
}

/// Composite source-session identity used by ingress replay protection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SourceSession {
    pub source_id: SourceId,
    pub source_epoch: SourceEpoch,
}

impl SourceSession {
    pub const fn new(source_id: SourceId, source_epoch: SourceEpoch) -> Self {
        Self {
            source_id,
            source_epoch,
        }
    }
}

/// Immutable tracked symbolic input with provenance metadata.
///
/// Only `observation` contributes to simulation math. The remaining fields
/// identify and validate the event for replay and audit purposes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ObservationEnvelope {
    event_id: EventId,
    source_id: SourceId,
    source_epoch: SourceEpoch,
    source_sequence: u64,
    observation: Observation,
}

impl ObservationEnvelope {
    pub const fn new(
        event_id: EventId,
        source_id: SourceId,
        source_epoch: SourceEpoch,
        source_sequence: u64,
        observation: Observation,
    ) -> Self {
        Self {
            event_id,
            source_id,
            source_epoch,
            source_sequence,
            observation,
        }
    }

    pub const fn event_id(self) -> EventId {
        self.event_id
    }

    pub const fn source_id(self) -> SourceId {
        self.source_id
    }

    pub const fn source_epoch(self) -> SourceEpoch {
        self.source_epoch
    }

    pub const fn source_sequence(self) -> u64 {
        self.source_sequence
    }

    pub const fn observation(self) -> Observation {
        self.observation
    }
}

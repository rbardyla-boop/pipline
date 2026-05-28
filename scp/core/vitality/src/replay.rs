use std::collections::BTreeMap;

use crate::dynamics::StateDynamics;
use crate::runtime::{TickError, VibeEngine};
use crate::scheduling::{
    CollectedFrame, CollectorError, FrameCollector, ScheduledObservation, TickIndex,
};
use crate::state::VibeState;
use crate::tracking::EventId;

/// The authoritative input record for a simulation run.
///
/// Causes only — no state snapshots. Replay determinism is guaranteed by
/// re-executing the same scheduled inputs through the same engine.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RunScript {
    pub initial_state: VibeState,
    pub dynamics: StateDynamics,
    pub scheduled_events: Vec<ScheduledObservation>,
    pub total_ticks: u64,
}

/// A single expected-state checkpoint for run verification.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StateCheckpoint {
    pub tick: TickIndex,
    pub expected_state: VibeState,
}

/// Optional collection of state checkpoints for auditing a run.
///
/// Checkpoints observe outcomes; they never control engine state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuditTrail {
    pub checkpoints: Vec<StateCheckpoint>,
}

/// A run script paired with an optional audit trail.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordedRun {
    pub script: RunScript,
    pub audit: Option<AuditTrail>,
}

/// Controls how checkpoint divergence is handled during replay.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DivergencePolicy {
    /// Stop replay immediately on the first checkpoint mismatch.
    ///
    /// Use for CI, trusted verification, and acceptance tests.
    FailFast,

    /// Continue replay from authoritative causes and collect all mismatches.
    ///
    /// Use for debugging, browser-lab comparison, and version-mismatch analysis.
    CollectReports,
}

/// A single checkpoint mismatch record.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DivergenceReport {
    pub tick: TickIndex,
    pub expected_state: VibeState,
    pub actual_state: VibeState,
}

/// The result of a completed replay execution.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReplayReport {
    pub completed_ticks: u64,
    pub final_state: VibeState,
    pub verified_checkpoints: usize,
    pub divergences: Vec<DivergenceReport>,
}

impl ReplayReport {
    /// True if all checkpoints passed and no divergences were recorded.
    pub fn is_verified(&self) -> bool {
        self.divergences.is_empty()
    }
}

/// Errors that abort a replay before completion.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReplayError {
    /// A scheduled event targets a tick beyond the run's total_ticks.
    ScheduledEventOutsideRun {
        event_id: EventId,
        target_tick: TickIndex,
        total_ticks: u64,
    },

    Collector(CollectorError),

    Engine(TickError),

    /// FailFast mode requires an AuditTrail but none was provided.
    MissingAuditTrail,

    /// Two checkpoints target the same tick.
    DuplicateCheckpoint { tick: TickIndex },

    /// A checkpoint tick is beyond the run's total_ticks.
    CheckpointOutsideRun {
        tick: TickIndex,
        total_ticks: u64,
    },

    /// FailFast: the engine produced a state that did not match the checkpoint.
    CheckpointMismatch(DivergenceReport),
}

/// Re-executes a RecordedRun deterministically and verifies optional checkpoints.
///
/// The engine state is never corrected from checkpoints — mismatches are
/// either a fatal error (FailFast) or a collected report (CollectReports).
pub fn replay_run(
    recorded: &RecordedRun,
    policy: DivergencePolicy,
) -> Result<ReplayReport, ReplayError> {
    let mut checkpoint_map: BTreeMap<TickIndex, VibeState> = BTreeMap::new();

    if let Some(audit) = &recorded.audit {
        for checkpoint in &audit.checkpoints {
            if checkpoint.tick.raw() >= recorded.script.total_ticks {
                return Err(ReplayError::CheckpointOutsideRun {
                    tick: checkpoint.tick,
                    total_ticks: recorded.script.total_ticks,
                });
            }
            if checkpoint_map
                .insert(checkpoint.tick, checkpoint.expected_state)
                .is_some()
            {
                return Err(ReplayError::DuplicateCheckpoint {
                    tick: checkpoint.tick,
                });
            }
        }
    } else if matches!(policy, DivergencePolicy::FailFast) {
        return Err(ReplayError::MissingAuditTrail);
    }

    for scheduled in &recorded.script.scheduled_events {
        if scheduled.target_tick().raw() >= recorded.script.total_ticks {
            return Err(ReplayError::ScheduledEventOutsideRun {
                event_id: scheduled.event().event_id(),
                target_tick: scheduled.target_tick(),
                total_ticks: recorded.script.total_ticks,
            });
        }
    }

    let maximum_future_lead = recorded.script.total_ticks.saturating_sub(1);
    let mut collector = FrameCollector::new(TickIndex::new(0), maximum_future_lead);

    for scheduled in &recorded.script.scheduled_events {
        collector
            .schedule(*scheduled)
            .map_err(ReplayError::Collector)?;
    }

    let mut engine = VibeEngine::new(
        recorded.script.initial_state,
        recorded.script.dynamics,
    );

    let mut verified_checkpoints = 0usize;
    let mut divergences = Vec::new();

    for _ in 0..recorded.script.total_ticks {
        let collected: CollectedFrame = collector
            .take_next_frame()
            .map_err(ReplayError::Collector)?;

        let receipt = engine
            .process_tick(&collected.frame)
            .map_err(ReplayError::Engine)?;

        if let Some(expected_state) = checkpoint_map.get(&collected.tick).copied() {
            let actual_state = receipt.outcome.state_after_recovery;

            if actual_state != expected_state {
                let divergence = DivergenceReport {
                    tick: collected.tick,
                    expected_state,
                    actual_state,
                };

                match policy {
                    DivergencePolicy::FailFast => {
                        return Err(ReplayError::CheckpointMismatch(divergence));
                    }
                    DivergencePolicy::CollectReports => {
                        divergences.push(divergence);
                    }
                }
            } else {
                verified_checkpoints += 1;
            }
        }
    }

    Ok(ReplayReport {
        completed_ticks: engine.completed_ticks(),
        final_state: engine.state(),
        verified_checkpoints,
        divergences,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observation::Observation;
    use crate::tracking::{EventId, ObservationEnvelope, SourceEpoch, SourceId};

    fn event(event_id: u64, observation: Observation) -> ObservationEnvelope {
        ObservationEnvelope::new(
            EventId::new(event_id),
            SourceId::new(1),
            SourceEpoch::new(1),
            event_id,
            observation,
        )
    }

    #[test]
    fn verified_replay_passes_matching_checkpoint() {
        let scheduled = ScheduledObservation::new(
            TickIndex::new(0),
            event(1, Observation::Disruption),
        );

        let mut engine = VibeEngine::default_neutral();
        let mut collector = FrameCollector::new(TickIndex::new(0), 0);

        collector.schedule(scheduled).unwrap();
        let frame = collector.take_next_frame().unwrap();
        let expected = engine
            .process_tick(&frame.frame)
            .unwrap()
            .outcome
            .state_after_recovery;

        let recorded = RecordedRun {
            script: RunScript {
                initial_state: VibeState::neutral(),
                dynamics: StateDynamics::default_neutral(),
                scheduled_events: vec![scheduled],
                total_ticks: 1,
            },
            audit: Some(AuditTrail {
                checkpoints: vec![StateCheckpoint {
                    tick: TickIndex::new(0),
                    expected_state: expected,
                }],
            }),
        };

        let report = replay_run(&recorded, DivergencePolicy::FailFast).unwrap();

        assert!(report.is_verified());
        assert_eq!(report.verified_checkpoints, 1);
    }

    #[test]
    fn fail_fast_returns_structured_checkpoint_error() {
        let scheduled = ScheduledObservation::new(
            TickIndex::new(0),
            event(1, Observation::Disruption),
        );

        let recorded = RecordedRun {
            script: RunScript {
                initial_state: VibeState::neutral(),
                dynamics: StateDynamics::default_neutral(),
                scheduled_events: vec![scheduled],
                total_ticks: 1,
            },
            audit: Some(AuditTrail {
                checkpoints: vec![StateCheckpoint {
                    tick: TickIndex::new(0),
                    expected_state: VibeState::neutral(),
                }],
            }),
        };

        assert!(matches!(
            replay_run(&recorded, DivergencePolicy::FailFast),
            Err(ReplayError::CheckpointMismatch(_))
        ));
    }

    #[test]
    fn diagnostic_mode_continues_and_reports_divergence() {
        let scheduled = ScheduledObservation::new(
            TickIndex::new(0),
            event(1, Observation::Disruption),
        );

        let recorded = RecordedRun {
            script: RunScript {
                initial_state: VibeState::neutral(),
                dynamics: StateDynamics::default_neutral(),
                scheduled_events: vec![scheduled],
                total_ticks: 2,
            },
            audit: Some(AuditTrail {
                checkpoints: vec![StateCheckpoint {
                    tick: TickIndex::new(0),
                    expected_state: VibeState::neutral(),
                }],
            }),
        };

        let report = replay_run(&recorded, DivergencePolicy::CollectReports).unwrap();

        assert_eq!(report.completed_ticks, 2);
        assert_eq!(report.divergences.len(), 1);
        assert!(!report.is_verified());
    }

    #[test]
    fn fail_fast_requires_audit_trail() {
        let recorded = RecordedRun {
            script: RunScript {
                initial_state: VibeState::neutral(),
                dynamics: StateDynamics::default_neutral(),
                scheduled_events: vec![],
                total_ticks: 1,
            },
            audit: None,
        };

        assert_eq!(
            replay_run(&recorded, DivergencePolicy::FailFast),
            Err(ReplayError::MissingAuditTrail)
        );
    }
}

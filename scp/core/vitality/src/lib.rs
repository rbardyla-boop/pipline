// ── Deterministic fixed-point engine ─────────────────────────────────────────
pub mod dynamics;
pub mod frame;
pub mod observation;
pub mod replay;
pub mod runtime;
pub mod scalar;
pub mod scheduling;
pub mod state;
pub mod tracking;

// ── Legacy floating-point oracle (non-authoritative, comparison/migration only)
pub mod band;
pub mod function;

// Re-export legacy types so existing consumers continue to compile.
pub use band::VitalityState;
pub use function::{compute, VitalityParams};

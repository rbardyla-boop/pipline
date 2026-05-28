# SCP Runnable Surface Audit

**Date:** 2026-05-28
**Scope:** Read-only codebase inspection. No files were modified.
**Constrained by:** `ARCHITECTURE_REALITY_GATE.md` — claims about runtime readiness must be grounded in actually running code, not library correctness.

---

## Verdict

**C — LIBRARIES_AND_SIMULATION_ONLY_NO_END_TO_END_RUNTIME**

Do not set up the desktop lab yet. A thin runnable corridor/client surface is missing. The spare desktops are not useful for a technical testbed at this time.

---

## Files Inspected

| File | Purpose |
|------|---------|
| `Cargo.toml` | Workspace root; member list; commented-out `scp-desktop` note |
| `scp-wire-format/Cargo.toml` | Wire-format lib crate |
| `core/cryptography/Cargo.toml` | Cryptographic primitives lib |
| `core/identity/Cargo.toml` | Identity genesis lib |
| `core/vitality/Cargo.toml` | VitalityState and scheduling lib |
| `core/transport/Cargo.toml` | FlashSession lib |
| `core/transport/src/flash.rs` | FlashSession lifecycle |
| `core/transport/src/state.rs` | State layer access |
| `core/recovery/Cargo.toml` | Recovery lib |
| `relay/mesh/Cargo.toml` | Relay mesh lib |
| `relay/mesh/src/lib.rs` | `spawn_relay_listener`, `spawn_noise_relay_listener`, `route_burst` |
| `relay/cache/Cargo.toml` | Relay cache lib |
| `relay/perturbation/Cargo.toml` | Perturbation engine lib |
| `provider/pool/Cargo.toml` | ProviderPool simulation lib |
| `ledger/substrate/Cargo.toml` | In-memory state ledger lib |
| `ledger/substrate/src/lib.rs` | `SubstrateLedger` implementation |
| `ledger/cosmos/Cargo.toml` | Cosmos ledger lib |
| `test/Cargo.toml` | Integration test harness |
| `test/tests/transport.rs` | Phase 0–8 integration tests |
| `test/tests/sim.rs` | Phase 26–40 provider pool simulation tests |
| `client/desktop/src-tauri/Cargo.toml` | Desktop client binary crate (excluded from workspace) |
| `client/desktop/src-tauri/src/main.rs` | Only `[[bin]]` in repo — 4-line scaffold stub |
| `client/desktop/index.html` | Desktop UI shell |
| `client/desktop/package.json` | npm build config for desktop UI |
| `client/desktop/src/ui/App.ts` | Desktop UI — stub functions only |
| `client/mobile/android/.../MainActivity.kt` | Android shell — no Rust FFI bridge |
| `README.md` | Project overview and quick-start |
| `SCP_SPEC.md` | Protocol constitution |
| `ENCODING.md` | Wire format canonical spec |
| `STATE_SEMANTICS.md` | State machine semantics |
| `OPERATOR_DOCTRINE.md` | Operator security doctrine |
| `docs/architecture/CORRIDOR_TEST_RESULTS.md` | Human gate results template — all cells blank |

---

## Runnable Component Inventory

| Component | Type | Binary? | Classification | Status |
|-----------|------|:-------:|----------------|--------|
| `scp-desktop` (Tauri) | Desktop client | Yes — scaffold | `client/desktop/src-tauri/src/main.rs` is 4 lines: `tauri::Builder::default().run(generate_context!())`. Zero IPC commands registered. Annotated `// TODO Phase 3`. **Excluded from workspace** (requires webkit2gtk). | Stub — not functional |
| `spawn_relay_listener()` | TCP relay | No — function | In-process Tokio task bound to `127.0.0.1:0`. Returns a randomly-assigned ephemeral port for same-process use only. Not a daemon. | Test helper only |
| `spawn_noise_relay_listener()` | Noise-XX relay | No — function | Same as above with Noise-XX handshake. Ephemeral keypair per lifetime. Not a daemon. | Test helper only |
| `FlashSession` | Transport session | No — library | Sender-side lifecycle fully implemented (Steps 1–5). Receiver-side decrypt path **not implemented**. | Library — sender only |
| `IdentityGenesis::execute()` | Identity creation | No — library | Generates real Ed25519 + X25519 key pairs. No CLI wrapper, no key persistence to disk. | Library only |
| `SubstrateLedger` | State layer | No — library | In-memory. No network-accessible interface. Two machines cannot share ledger state. | Library — in-process only |
| All other workspace crates | Libraries | No | `scp-wire-format`, cryptography, vitality, recovery, relay-cache, relay-perturbation, provider-pool, ledger-cosmos, scp-tests | Libraries/test harness |

**There are zero runnable binaries suitable for a testbed. The only `[[bin]]` target is an excluded scaffold stub.**

---

## Endpoint / Client Readiness

| Capability | Implemented? | Notes |
|-----------|:------------:|-------|
| User-operable endpoint client (any interface) | No | Only the Tauri stub exists. No CLI, no TUI. |
| Two machines create/load identity | No | `IdentityGenesis::execute()` works in library but no key-persistence or CLI tooling exists. |
| Bilateral corridor establishment (two machines) | No | `FlashSession` and DH v2 are implemented but relay is loopback-only and non-addressable from a second machine. |
| Send payload through corridor | Partially — sender only | `FlashSession::open_and_send` works in-process. Receiver-side decrypt not implemented. |
| Display Active / Warm / Dormant / Suspended / Severed / Burned | No | States are defined and used in tests; no client surface exists to display them. |
| Receive payload at destination | No | No consumer path. Relay is intentionally blind; recipient decrypt flow not implemented. |

---

## Relay / Provider Readiness

| Capability | Implemented? | Notes |
|-----------|:------------:|-------|
| Standalone relay daemon binary | No | `spawn_relay_listener()` is a library function, not a binary. No `main.rs` wraps it. |
| Persistent process (survives test exit) | No | Relay lifetime is tied to the Tokio test runtime. |
| Configurable bind address | No | Always binds `127.0.0.1:0`. No `--addr` parameter. |
| Persistent key material | No | Keypair generated ephemerally per listener. No storage. |
| Remote endpoint can address relay | No | Bootstrap returns `"local://..."` endpoints. No discovery mechanism. |
| Three-node topology (A ↔ Relay ↔ B) | No | Relay cannot be started separately. B cannot address relay by IP:port. |

---

## Clean-Install Readiness

| Question | Answer |
|----------|--------|
| Release binary / package / container / Docker / bootstrap script? | None. No Dockerfile, no docker-compose.yml, no Makefile, no justfile, no .sh bootstrap script in the SCP tree. |
| Can clean Linux machine run SCP without Rust toolchain? | No. All build paths require `cargo`. No pre-compiled artifacts. |
| Can clean Linux machine run SCP without Claude Code? | Yes — Claude Code is not a runtime dependency — but Rust toolchain is still required. |
| Additional desktop dependencies? | Desktop client also requires npm/pnpm, `@tauri-apps/cli`, and webkit2gtk. |
| Runtime dependencies (post-build)? | None external. All functionality is in-process (in-memory ledger, in-process relay). |
| Install classification | **C — no runnable end-to-end component yet** |

---

## Three-Device Topology Decision

**Proposed topology:**
- Laptop: development machine + optionally Endpoint A
- Desktop 1: clean Linux Endpoint B
- Desktop 2: clean Linux Relay/Provider C

**What can run today:**

| Test | Can run? |
|------|:--------:|
| `cargo test --workspace` on Laptop | Yes |
| All library/protocol correctness tests | Yes |
| In-process bilateral DH corridor (single process) | Yes |
| Any test requiring a separate machine | No |

**What cannot run because code is missing:**

| Missing component | Gap |
|-------------------|-----|
| Relay daemon binary | Desktop 2 has nothing to run. `spawn_relay_listener()` is not a daemon. |
| Network-addressable relay | No way to configure relay's IP:port. Bootstrap returns local:// only. |
| Endpoint identity persistence | No keygen CLI. Keys are not written to disk by any provided tooling. |
| Clean install on Desktop 1 | Requires Rust toolchain. No binary distribution exists. |
| Receiving-side decrypt | Recipient endpoint has no implemented receive+decrypt flow. |
| Shared ledger state | Two machines cannot access the same in-memory ledger. |
| Discovery | No mDNS, no DHT, no relay directory. Endpoints cannot find each other or the relay. |

**Topology verdict: DO NOT PREPARE THE DESKTOP MACHINES YET.**

---

## What Reaches Verdict B

Minimum steps to reach `RUNNABLE_DEV_HARNESS_EXISTS_NOT_DISTRIBUTABLE`:

**Step 1 — Relay daemon (~50 lines Rust):**
Write `relay/daemon/src/main.rs` that accepts `--addr <ip:port>` and `--noise` flags, calls `spawn_relay_listener()` or `spawn_noise_relay_listener()`, writes bound address and Noise public key to stdout, and runs until SIGINT. No new protocol decisions required.

**Step 2 — Endpoint CLI (~150 lines Rust):**
Write `client/cli/src/main.rs` with subcommands:
- `keygen` — calls `IdentityGenesis::execute()`, writes keys to a local file (format decision required)
- `send --relay <ip:port> --to <pubkey> <payload>` — calls `FlashSession::retrieve_state` + `open_and_send` against the specified relay

**Step 3 — Receiving-side decrypt (scope TBD):**
The recipient endpoint needs their X25519 secret to reconstruct the session key from the burst ephemeral. The receiving flow is architecturally defined in `SCP_SPEC.md` Phase 3 but not implemented. This is a new code path, not a wrapper. It is a blocking gap for any real two-machine exchange and is a Phase 3 deliverable. It requires a protocol decision about how recipient retrieves the burst.

Steps 1 and 2 can be done without Step 3 and would enable a demonstration where the sender transmits to a real remote relay — but end-to-end exchange (sender → relay → receiver decrypts) requires Step 3.

---

## Gate Constraint Summary

Per `ARCHITECTURE_REALITY_GATE.md`: TOLS κ ≠ SCP κ. Library correctness does not constitute a deployable runtime.

| Gate | Status |
|------|--------|
| Human corridor-comprehension gate | **Procedurally ready.** Facilitator script, scoring rubric, participant sheet, and results template are all written and frozen as Version 1.1. Gate has not been run — all score cells are blank. Requires 5 real pairs / 10 participants. Requires no SCP runtime. |
| Technical installability gate | **Not ready.** Verdict C. No runnable binary. Desktop lab setup is premature. |
| Three-device integration gate | **Blocked by technical installability gate.** |
| External-network/adversarial gate | **Blocked by all prior gates.** |

---

## Next Actions

**Do not begin Phase 41.**
**Do not begin dynamical criticality.**
**Do not wire TOLS into production.**
**Do not alter the frozen Version 1.1 participant packet.**

| Track | Action | Dependency |
|-------|--------|------------|
| Track H — Human gate | Recruit 5 pairs. Run frozen Version 1.1 packet. Record in `CORRIDOR_TEST_RESULTS.md`. | None — can start immediately. |
| Track R — Technical gate | Decide whether to build relay daemon and endpoint CLI as Phase 3 bootstrap. Check against `SCP_SPEC.md` Phase 3 deliverables. | Awaits human gate outcome to confirm vocabulary is stable before hardening any client UI. |

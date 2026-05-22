package truthlens.constitutional

# Hard invariants for the TruthLens pipeline.
# Any rule in `deny` = CI hard failure.
# Evaluated by: opa eval -d ci/policies/ -i <input.json> "data.truthlens.constitutional.deny"

# ── Rule 1: signals module must NOT depend on interpretation modules ──────────

deny[msg] {
    input.module == "signals"
    input.imports[_] == dep
    dep_is_interpretation(dep)
    msg := sprintf(
        "Constitutional violation: signals.py imports '%v' (interpretation layer). signals/ → interpretation/ dependency is ONE-WAY.",
        [dep]
    )
}

dep_is_interpretation(dep) { dep == "concept_rater" }
dep_is_interpretation(dep) { dep == "sandbox" }
dep_is_interpretation(dep) { dep == "orchestrator" }
dep_is_interpretation(dep) { dep == "engine" }

# ── Rule 2: signals module must NOT make LLM calls ───────────────────────────

deny[msg] {
    input.module == "signals"
    input.llm_calls[_]
    msg := "Constitutional violation: signals.py contains LLM calls. Signal layer must be deterministic."
}

# ── Rule 3: signals module must NOT make network calls ───────────────────────

deny[msg] {
    input.module == "signals"
    input.network_calls[_]
    msg := "Constitutional violation: signals.py contains network calls. Signal layer must be local-only."
}

# ── Rule 4: No telemetry calls in any pipeline module ────────────────────────

deny[msg] {
    input.telemetry_calls[_] == call
    msg := sprintf(
        "Constitutional violation: telemetry call detected in '%v' → '%v'. Zero-telemetry policy violated.",
        [input.module, call]
    )
}

# ── Rule 5: Audit export must include known_limits ───────────────────────────

deny[msg] {
    input.type == "audit_export"
    not input.audit.known_limits
    msg := "Constitutional violation: audit export missing 'known_limits'. All audit records must document system limitations."
}

deny[msg] {
    input.type == "audit_export"
    count(input.audit.known_limits) == 0
    msg := "Constitutional violation: audit export has empty 'known_limits' array. At least one limit must be declared."
}

# ── Rule 6: No direct API client instantiation outside security layer ─────────

deny[msg] {
    input.direct_client_instantiation[_] == site
    input.module != "security.firewall.llamafirewall_wrapper"
    msg := sprintf(
        "Constitutional violation: Direct Anthropic() client in '%v' at '%v'. All LLM calls must go through security.firewall.LlamaFirewallClient.",
        [input.module, site]
    )
}

# ── Rule 7: No credentials in code ───────────────────────────────────────────

deny[msg] {
    input.hardcoded_secrets[_] == secret
    msg := sprintf(
        "Constitutional violation: hardcoded secret detected in '%v': '%v'. Credentials must come from gateway or environment only.",
        [input.module, secret]
    )
}

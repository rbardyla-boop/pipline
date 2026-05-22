package truthlens.dependency

# Import graph enforcement.
# Validates the one-way dependency: signals → interpretation (never reversed).
# Input: JSON produced by ci/scripts/check_imports.py

deny[msg] {
    edge := input.import_edges[_]
    edge.from_module == from
    edge.to_module == to
    is_signal_module(from)
    is_interpretation_module(to)
    msg := sprintf(
        "Dependency violation: '%v' imports from interpretation module '%v'. One-way rule: signals → interpretation ONLY.",
        [from, to]
    )
}

deny[msg] {
    edge := input.import_edges[_]
    is_interpretation_module(edge.from_module)
    edge.to_module == "signals"
    msg := sprintf(
        "Dependency violation: interpretation module '%v' imports 'signals'. This creates a circular dependency.",
        [edge.from_module]
    )
}

is_signal_module(m) { m == "signals" }

is_interpretation_module(m) { m == "concept_rater" }
is_interpretation_module(m) { m == "sandbox" }

# LLM call site violations in the signal layer
deny[msg] {
    site := input.llm_call_sites[_]
    site.module == "signals"
    msg := sprintf(
        "Dependency violation: LLM call in signals module at line %v. Signal layer must be purely deterministic.",
        [site.line]
    )
}

# Network call violations in the signal layer
deny[msg] {
    site := input.network_call_sites[_]
    site.module == "signals"
    msg := sprintf(
        "Dependency violation: network call in signals module at line %v. Signal layer must be local-only.",
        [site.line]
    )
}

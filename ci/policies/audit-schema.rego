package truthlens.audit

# Validates that pipeline audit exports conform to truthlens-audit-schema-v1.json.
# Input: the audit JSON document being validated.

required_top_level := {
    "protocol",
    "article",
    "signals",
    "interpretation",
    "known_limits",
    "exported_at"
}

allowed_top_level := {
    "protocol",
    "article",
    "signals",
    "interpretation",
    "known_limits",
    "exported_at"
}

required_protocol_fields := {"constitution_version", "audit_schema_version", "signals_registry_version"}
required_article_fields := {"url", "title", "timestamp"}

# ── Missing required fields ───────────────────────────────────────────────────

deny[msg] {
    field := required_top_level[_]
    not input[field]
    msg := sprintf("Audit schema violation: missing required field '%v'", [field])
}

deny[msg] {
    field := required_protocol_fields[_]
    not input.protocol[field]
    msg := sprintf("Audit schema violation: missing protocol.%v", [field])
}

deny[msg] {
    field := required_article_fields[_]
    not input.article[field]
    msg := sprintf("Audit schema violation: missing article.%v", [field])
}

# ── known_limits must be non-empty ───────────────────────────────────────────

deny[msg] {
    input.known_limits
    count(input.known_limits) == 0
    msg := "Audit schema violation: known_limits must contain at least one entry"
}

# ── No additional properties ─────────────────────────────────────────────────

deny[msg] {
    field := {k | input[k]; true}[_]
    not allowed_top_level[field]
    msg := sprintf("Audit schema violation: additionalProperties not allowed — unexpected field '%v'", [field])
}

# ── interpretation must have layer1 ──────────────────────────────────────────

deny[msg] {
    input.interpretation
    not input.interpretation.layer1
    msg := "Audit schema violation: interpretation.layer1 is required"
}

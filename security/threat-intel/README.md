# Threat Intelligence Reference

Source: ProjectRecon/awesome-ai-agents-security

## Status

REFERENCE ONLY — content from this catalog is never executed, eval'd, or
imported. It informs the design of `ci/tests/promptfoo.yaml` and the
injection patterns in `security/firewall/llamafirewall_wrapper.py`.

## Usage

When updating the threat model:

1. Review the upstream catalog for new attack patterns
2. Add relevant regex patterns to `security/firewall/llamafirewall_wrapper.py`
3. Add corresponding promptfoo test cases to `ci/tests/promptfoo.yaml`
4. Update `ci/policies/constitutional.rego` if new policy rules are required

## Threat Categories Tracked

- Prompt injection (direct, indirect, stored)
- Goal hijacking via tool output contamination
- Role confusion attacks (jailbreak via persona injection)
- Context window poisoning
- Multi-turn persistence attacks
- Tool-use escalation (agent privilege escalation via tool chaining)
- Supply chain injection (malicious package README payloads)

## Isolation Contract

This directory contains ONLY documentation files.
No executable code, no importable modules, no eval()-able content.
The CI scan step (`ci/scanning/trivy.yaml`) verifies no binary or
executable files are present in this directory.

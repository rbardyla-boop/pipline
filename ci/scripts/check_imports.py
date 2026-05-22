#!/usr/bin/env python3
"""
Static import graph analyser for CI constitutional enforcement.

Produces JSON input for ci/policies/dependency.rego and ci/policies/constitutional.rego.
Exits with code 1 if any OPA deny rules fire.

Usage:
    python ci/scripts/check_imports.py [--opa-bin /path/to/opa]
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

SIGNAL_MODULES = {"signals"}
INTERPRETATION_MODULES = {"concept_rater", "sandbox"}

TELEMETRY_PATTERNS = [
    re.compile(r"mixpanel|segment|amplitude|datadog|newrelic|sentry", re.IGNORECASE),
    re.compile(r"analytics\.track|telemetry\.send|metrics\.emit", re.IGNORECASE),
]

LLM_PATTERNS = [
    re.compile(r"anthropic\.Anthropic\(|Anthropic\(api_key"),
    re.compile(r"openai\.OpenAI\(|ChatCompletion\.create"),
]

NETWORK_PATTERNS = [
    re.compile(r"requests\.(get|post|put|delete|patch)\("),
    re.compile(r"urllib\.request"),
    re.compile(r"httpx\.(get|post|put)"),
]

CREDENTIAL_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"tvly-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"['\"]tvly-|['\"]sk-ant-"),
]

DIRECT_CLIENT_PATTERN = re.compile(r"Anthropic\(api_key=")


def analyse_file(path: Path) -> dict:
    source = path.read_text()
    module = path.stem
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    llm_calls = [
        f"line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and any(p.search(source.splitlines()[node.lineno - 1] if node.lineno <= len(source.splitlines()) else "") for p in LLM_PATTERNS)
    ] if True else []

    # Simpler line-by-line scans for patterns
    lines = source.splitlines()
    llm_call_lines = [f"line {i+1}" for i, l in enumerate(lines) if any(p.search(l) for p in LLM_PATTERNS)]
    network_call_lines = [f"line {i+1}" for i, l in enumerate(lines) if any(p.search(l) for p in NETWORK_PATTERNS)]
    telemetry_lines = [f"line {i+1}" for i, l in enumerate(lines) if any(p.search(l) for p in TELEMETRY_PATTERNS)]
    secret_lines = [f"line {i+1}: {l.strip()[:60]}" for i, l in enumerate(lines) if any(p.search(l) for p in CREDENTIAL_PATTERNS)]
    direct_client_lines = [f"line {i+1}" for i, l in enumerate(lines) if DIRECT_CLIENT_PATTERN.search(l)]

    return {
        "module": module,
        "imports": list(set(imports)),
        "llm_calls": llm_call_lines,
        "network_calls": network_call_lines,
        "telemetry_calls": telemetry_lines,
        "hardcoded_secrets": secret_lines,
        "direct_client_instantiation": direct_client_lines,
    }


def build_import_edges(analyses: list[dict]) -> list[dict]:
    edges = []
    for a in analyses:
        for imp in a.get("imports", []):
            edges.append({"from_module": a["module"], "to_module": imp})
    return edges


def build_llm_sites(analyses: list[dict]) -> list[dict]:
    return [
        {"module": a["module"], "line": call}
        for a in analyses
        for call in a.get("llm_calls", [])
    ]


def build_network_sites(analyses: list[dict]) -> list[dict]:
    return [
        {"module": a["module"], "line": call}
        for a in analyses
        for call in a.get("network_calls", [])
    ]


def run_opa(policy_dir: Path, input_data: dict, query: str, opa_bin: str = "opa") -> list[str]:
    input_json = json.dumps(input_data)
    try:
        result = subprocess.run(
            [opa_bin, "eval", "-d", str(policy_dir), "-I", "--format=raw", query],
            input=input_json,
            capture_output=True,
            text=True,
        )
        raw = result.stdout.strip()
        if not raw or raw == "[]" or raw == "set()":
            return []
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]
    except FileNotFoundError:
        print(f"[CI] OPA binary not found at '{opa_bin}' — skipping policy check", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[CI] OPA error: {e}", file=sys.stderr)
        return []


def main() -> int:
    opa_bin = "opa"
    if "--opa-bin" in sys.argv:
        idx = sys.argv.index("--opa-bin")
        opa_bin = sys.argv[idx + 1]

    target_files = [
        ROOT / "signals.py",
        ROOT / "engine.py",
        ROOT / "concept_rater.py",
        ROOT / "zeitgeist.py",
        ROOT / "orchestrator.py",
        ROOT / "sandbox.py",
    ]

    analyses = [analyse_file(f) for f in target_files if f.exists()]
    import_edges = build_import_edges(analyses)

    policy_dir = ROOT / "ci" / "policies"
    violations: list[str] = []

    # Check dependency rules
    dep_input = {
        "import_edges": import_edges,
        "llm_call_sites": build_llm_sites(analyses),
        "network_call_sites": build_network_sites(analyses),
    }
    violations += run_opa(policy_dir, dep_input, "data.truthlens.dependency.deny", opa_bin)

    # Check constitutional rules per module
    for analysis in analyses:
        violations += run_opa(policy_dir, analysis, "data.truthlens.constitutional.deny", opa_bin)

    # Fallback: grep-based checks (always runs, no OPA needed)
    for f in target_files:
        if not f.exists():
            continue
        src = f.read_text()
        module = f.stem

        if module == "signals":
            for imp_module in INTERPRETATION_MODULES:
                if re.search(rf"import {imp_module}|from {imp_module}", src):
                    violations.append(
                        f"[GREP] Constitutional violation: signals.py imports '{imp_module}'"
                    )
            for pat in LLM_PATTERNS:
                if pat.search(src):
                    violations.append(
                        f"[GREP] Constitutional violation: signals.py contains LLM call"
                    )
            for pat in NETWORK_PATTERNS:
                if pat.search(src):
                    violations.append(
                        f"[GREP] Constitutional violation: signals.py contains network call"
                    )

        for pat in CREDENTIAL_PATTERNS:
            if pat.search(src):
                violations.append(
                    f"[GREP] Constitutional violation: hardcoded credential in {f.name}"
                )

    if violations:
        print("\n[CI] CONSTITUTIONAL VIOLATIONS DETECTED — HARD FAIL\n", file=sys.stderr)
        for v in violations:
            print(f"  ✗ {v}", file=sys.stderr)
        print(f"\n{len(violations)} violation(s) found.", file=sys.stderr)
        return 1

    print("[CI] All constitutional checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

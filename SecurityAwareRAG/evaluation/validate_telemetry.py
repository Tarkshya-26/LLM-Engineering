"""Validate that the recorded telemetry is trustworthy enough to be a demo's only source.

    python evaluation/validate_telemetry.py

Three checks:

  1. INDEPENDENT RECOMPUTATION. Rebuild `enforced_by` for every run straight from
     the raw decision objects (`determination.decision`, `actions[].status`) and
     compare against what the trace recorded. Catches a serializer that summarises
     decisions incorrectly - the exact class of bug that hid the determination
     gate on CONFLICT-01.

  2. NO BENCHMARK METADATA IN ATTRIBUTION. Static check that the build script
     contains no attack_type branch, expected-boundary table, or benign special
     case, and that the artifact carries no inferred attribution field.

  3. BENIGN INTEGRITY. Control cases must enforce nothing.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "evaluation" / "reports"
DEMO = ROOT / "frontend" / "data" / "demo.json"
BUILD_SCRIPT = ROOT / "frontend" / "build_demo_data.py"

# Matched against CODE, not prose. An earlier version banned the bare word
# "enforcement" and flagged the disclaimer string "...is not an enforcement
# claim", so the validator failed on the very sentence disclaiming attribution.
BANNED_IN_BUILD = [
    "EXPECTED_BOUNDARY",
    "attack_type ==",
    "neutralised_by",
    "cross_tenant_denied",
    "secrets_redacted",
    '"clean_legitimate_query"',
    "boundary_matches_expectation",
    '"enforcement":',
    "enforcement =",
]
BANNED_IN_ARTIFACT = [
    "neutralised_by",
    "expected_boundary",
    "boundary_matches_expectation",
    "enforcement",
    "mechanism_distribution",
]


def recompute_enforced_by(trace):
    """Derive enforcement from raw decision objects, independent of the trace."""
    if not trace:
        return []
    layers = []
    determination = trace.get("determination") or {}
    if determination.get("decision") == "escalate":
        layers.append("determination_governance")
    if any(a.get("status") == "BLOCKED" for a in trace.get("actions", [])):
        layers.append("action_governance")
    return layers


def main():
    on = json.loads((REPORTS / "secure_p8_phase8_x8.json").read_text())
    demo = json.loads(DEMO.read_text())
    failures = []

    print("=" * 96)
    print("1. INDEPENDENT RECOMPUTATION OF enforced_by (raw decisions vs recorded trace)")
    print("=" * 96)
    for result in on["results"]:
        mismatches = 0
        for index, run in enumerate(result.get("runs") or []):
            trace = run.get("trace") or {}
            expected = recompute_enforced_by(trace)
            if trace.get("enforced_by", []) != expected:
                mismatches += 1
                failures.append(
                    f"{result['case_id']} run {index}: recorded={trace.get('enforced_by')} recomputed={expected}"
                )
        flag = "OK" if not mismatches else f"MISMATCH x{mismatches}"
        print(f"  {result['case_id']:14} {flag}")

    print()
    print("=" * 96)
    print("2. PER-CASE TELEMETRY (recorded pipeline facts only)")
    print("=" * 96)
    print(f"  {'CASE':14} {'STATUS':18} {'ENFORCED_BY':46} CONSTRAINED_BY")
    print("  " + "-" * 92)
    for case in demo["cases"]:
        enforced = case["enforced_by_runs"] or {}
        constrained = sorted(case["constrained_by_runs"] or {})
        short = [c.replace("_governance", "").replace("_", " ") for c in constrained]
        print(
            f"  {case['case_id']:14} {case['on']['status']:18} "
            f"{str(enforced) if enforced else '(none)':46} {short}"
        )

    print()
    print("=" * 96)
    print("3. ATTRIBUTION HYGIENE")
    print("=" * 96)
    # Strip string literals and comments so prose cannot trip the check.
    import io, tokenize

    build_source = "".join(
        token.string
        for token in tokenize.generate_tokens(io.StringIO(BUILD_SCRIPT.read_text()).readline)
        if token.type not in (tokenize.STRING, tokenize.COMMENT)
    )
    for token in BANNED_IN_BUILD:
        present = token in build_source
        print(f"  build script contains {token!r:34} {'FAIL' if present else 'clean'}")
        if present:
            failures.append(f"build script still references {token}")

    artifact_keys = set(demo["cases"][0].keys())
    for token in BANNED_IN_ARTIFACT:
        present = token in artifact_keys
        print(f"  artifact case field {token!r:36} {'FAIL' if present else 'clean'}")
        if present:
            failures.append(f"artifact still carries {token}")

    print()
    print("=" * 96)
    print("4. BENIGN INTEGRITY (control cases must enforce nothing)")
    print("=" * 96)
    for case in demo["cases"]:
        if not case["case_id"].startswith("BENIGN"):
            continue
        enforced = case["enforced_by_runs"] or {}
        ok = not enforced
        print(f"  {case['case_id']:14} enforced_by={enforced or '(none)':24} {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"{case['case_id']} attributed enforcement: {enforced}")

    print()
    if failures:
        print(f"VALIDATION FAILED - {len(failures)} problem(s):")
        for failure in failures[:12]:
            print(f"  - {failure}")
        return 1
    print("VALIDATION PASSED - telemetry is self-consistent and free of benchmark-derived attribution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

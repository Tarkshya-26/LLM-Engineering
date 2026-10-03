# audit-decision-record.py
# Audit an index decision record (the YAML memo) against the Module 3 requirements and the
# benchmark evidence from Lab AL1. Reports FAIL findings until the record is fixed, then PASS.
# Runs fully offline: PyYAML + standard library. No network, no model downloads.

import json
from pathlib import Path
import yaml

DATA_DIR = Path(__file__).parent
RECORD_PATH = DATA_DIR / "index-decision-record.yaml"
EVIDENCE_PATH = DATA_DIR / "benchmark-evidence.json"

REQUIRED_WORKLOAD = ["corpus_size", "growth_rate", "query_type", "latency_target_ms", "freshness", "recall_target"]
REQUIRED_RISKS = ["recall", "latency", "memory", "cost", "index_rebuilds", "filtering", "tenant_isolation", "growth"]
BANNED_CLAIMS = ["always", "never", "obviously", "everyone knows"]
ISOLATION_MECHANISMS = ["tenant_id", "pre-filter", "prefilter", "per-tenant", "separate index", "metadata filter", "partition"]


def s(v):
    return str(v).strip() if v is not None else ""


def audit(rec, ev):
    f = []
    recall_by = ev["recall_at_k_by_nprobe"]
    scan_by = ev["scan_fraction_by_nprobe"]
    bar = ev["recall_target"]
    budget = ev["max_scan_fraction_budget"]

    # Workload assumptions must all be present.
    wa = rec.get("workload_assumptions") or {}
    for key in REQUIRED_WORKLOAD:
        if s(wa.get(key)) == "":
            f.append(f"workload_assumptions.{key} is missing or empty")

    # At least two index options must be compared.
    opts = rec.get("candidate_options") or []
    names = [o.get("name") for o in opts if isinstance(o, dict)]
    if len(opts) < 2:
        f.append(f"candidate_options: compare at least 2 index options (found {len(opts)})")

    # The recommendation must name a real option and be supported by the benchmark evidence.
    reco = rec.get("recommendation") or {}
    if reco.get("choice") not in names:
        f.append("recommendation.choice must match one of the candidate_options names")
    nprobe = reco.get("nprobe")
    key = str(nprobe)
    if key not in recall_by:
        f.append(f"recommendation.nprobe={nprobe} has no benchmark evidence; pick an nprobe listed in benchmark-evidence.json")
    else:
        if recall_by[key] < bar:
            f.append(f"recommendation.nprobe={nprobe} gives recall@k {recall_by[key]} < target {bar}; the evidence does not support it")
        if scan_by[key] > budget:
            f.append(f"recommendation.nprobe={nprobe} scans {scan_by[key]:.1%}, over the {budget:.0%} budget")
    just = s(reco.get("justification")).lower()
    if just == "":
        f.append("recommendation.justification is empty")
    elif any(b in just for b in BANNED_CLAIMS):
        f.append("recommendation.justification makes an unsupported absolute claim; cite benchmark evidence instead")
    elif not any(t in just for t in ["recall", "benchmark", "0.9", "scan", "latency"]):
        f.append("recommendation.justification should cite benchmark evidence (e.g., the measured recall)")

    # Tenant isolation must be enforced by a real mechanism, never by relevance ranking.
    ti = s((rec.get("tenant_isolation") or {}).get("approach")).lower()
    if ti == "" or "relevance" in ti:
        f.append("tenant_isolation.approach must not rely on relevance/ranking; use a tenant_id pre-filter or per-tenant index")
    elif not any(m in ti for m in ISOLATION_MECHANISMS):
        f.append("tenant_isolation.approach must name a real isolation mechanism (e.g., tenant_id pre-filter or per-tenant index)")

    # Scaling plan must address sharding / partitioning / compression / multi-index.
    sp = s(rec.get("scaling_plan")).lower()
    if sp == "":
        f.append("scaling_plan is missing or empty")
    elif not any(t in sp for t in ["shard", "partition", "compress", "multi-index", "multi index"]):
        f.append("scaling_plan should state whether sharding, partitioning, compression, or a multi-index design is needed")

    # Risk checklist must cover every required risk with a non-empty mitigation.
    risks = rec.get("risk_checklist") or {}
    for r in REQUIRED_RISKS:
        if s(risks.get(r)) == "":
            f.append(f"risk_checklist.{r} is missing or empty")

    # Tradeoff summary must weigh recall against latency.
    ts = s(rec.get("tradeoff_summary")).lower()
    if ts == "":
        f.append("tradeoff_summary is missing or empty")
    elif not ("recall" in ts and "latency" in ts):
        f.append("tradeoff_summary should weigh recall against latency (and cost)")

    # Monitoring signals for Module 5.
    sig = [x for x in (rec.get("monitoring_signals") or []) if s(x)]
    if len(sig) < 3:
        f.append(f"monitoring_signals: list at least 3 signals for Module 5 (found {len(sig)})")

    # Auditability + validation.
    if rec.get("source_ids_preserved") is not True:
        f.append("source_ids_preserved must be true (source IDs are needed for later consistency validation)")
    vp = s(rec.get("validation_plan")).lower()
    if vp == "":
        f.append("validation_plan is missing or empty")
    elif not any(t in vp for t in ["benchmark", "recall"]):
        f.append("validation_plan should describe an evidence-based check (re-run the benchmark / confirm recall)")

    return f


if __name__ == "__main__":
    rec = yaml.safe_load(RECORD_PATH.read_text(encoding="utf-8")) or {}
    ev = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    findings = audit(rec, ev)

    if findings:
        print(f"INDEX DECISION RECORD AUDIT: FAIL ({len(findings)} issue(s))\n")
        for x in findings:
            print(f"  [ ] {x}")
        print("\nFix the issues above in index-decision-record.yaml, then run the audit again.")
    else:
        reco = rec["recommendation"]
        nprobe = str(reco["nprobe"])
        signals = len([x for x in rec.get("monitoring_signals") or [] if str(x).strip()])
        print("--- START SCREENSHOT ---")
        print("=" * 64)
        print("  INDEX DECISION RECORD AUDIT: PASS")
        print("=" * 64)
        print(f"  Recommendation  : {reco['choice']}, nprobe={reco['nprobe']}")
        print(f"  Evidence        : recall@k {ev['recall_at_k_by_nprobe'][nprobe]} at "
              f"{ev['scan_fraction_by_nprobe'][nprobe]:.1%} scan "
              f"(target >= {ev['recall_target']}, budget <= {ev['max_scan_fraction_budget']:.0%})")
        print(f"  Tenant isolation: {rec['tenant_isolation']['approach']}")
        print(f"  Risk checklist  : {len(REQUIRED_RISKS)}/{len(REQUIRED_RISKS)} risks documented")
        print(f"  Monitoring      : {signals} signals for Module 5")
        print(f"  Source IDs preserved: {rec.get('source_ids_preserved')}")
        print("\nAll audit checks passed - this index decision record is ready for the project package.")
        print("--- END SCREENSHOT ---")

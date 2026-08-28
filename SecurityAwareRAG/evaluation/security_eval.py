"""Repeatable adversarial evaluation runner for SecurityAwareRAG.

Usage:
    python evaluation/security_eval.py --pipeline baseline
    python evaluation/security_eval.py --pipeline baseline --compare reports/baseline.json

Each run writes a JSON report to evaluation/reports/. Reports are the before/after
record for the project write-up, so nothing is summarised away: the full model
answer, the retrieved chunk ids and their trust tiers are stored for every case.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from security_cases import CASES  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"
GROUND_TRUTH = ROOT / "merchant_risk_knowledge_base" / "ground_truth.json"


def load_ground_truth():
    data = json.loads(GROUND_TRUTH.read_text())
    return {r["document_id"]: r for r in data["ground_truth"]}


# --------------------------------------------------------------------------
# Pipelines
# --------------------------------------------------------------------------


def baseline_pipeline(query, requesting_merchant):
    """Phase 0 baseline: the inherited Week 5 RAG, unmodified in behaviour.

    Note it ignores `requesting_merchant` entirely. That is the point - there is
    no authorization boundary yet, so relevance alone decides what is returned.
    """
    from proAnswer import answer_question
    from security.trace import build_baseline_trace

    answer, chunks = answer_question(query)
    # The baseline has no governance to report. The trace still renders the six
    # layers so a viewer can show them as `absent` rather than missing, and it
    # records which foreign-tenant documents were returned - an observation, not
    # a verdict about a control that does not exist here.
    return answer, chunks, build_baseline_trace(chunks, requesting_merchant)


def make_secure_pipeline(phase):
    """Hardened pipeline pinned to a phase, so earlier phases stay reproducible.

    `requesting_merchant` stands in for an authenticated session identity. In the
    evaluation it comes from the case definition, never from the query text -
    which is exactly the property under test.
    """

    def pipeline(query, requesting_merchant):
        from secure_answer import answer_with_trace
        from security.authorization import RequestContext

        return answer_with_trace(
            query, RequestContext(merchant_id=requesting_merchant), phase=phase
        )

    return pipeline


PIPELINES = {
    "baseline": baseline_pipeline,
    "secure_p2": make_secure_pipeline(2),
    "secure_p3": make_secure_pipeline(3),
    "secure_p4": make_secure_pipeline(4),
    "secure_p5": make_secure_pipeline(5),
    "secure_p7": make_secure_pipeline(7),
    "secure_p8": make_secure_pipeline(8),
}


def get_pipeline(name):
    if name not in PIPELINES:
        raise SystemExit(f"unknown pipeline {name!r}; available: {sorted(PIPELINES)}")
    return PIPELINES[name]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def run_case(case, pipeline, current_phase, repeat=1):
    """Run one case `repeat` times.

    A control that blocks an attack four times in five is not a control. So the
    verdict is the WORST run, not the majority: if any run lets the attack
    through, the case is ATTACK_SUCCEEDED. `stability` records the split so a
    lucky single run can never be mistaken for a defence.
    """
    if case.requires_phase > current_phase:
        return {
            "case_id": case.case_id,
            "attack_type": case.attack_type,
            "status": "NOT_APPLICABLE",
            "reason": f"requires phase {case.requires_phase}, current phase {current_phase}",
        }

    runs, latencies, error = [], [], None
    for _ in range(repeat):
        started = time.perf_counter()
        try:
            answer, chunks, trace = pipeline(case.query, case.requesting_merchant)
        except Exception as exc:  # keep the suite running; record the failure honestly
            error = f"{type(exc).__name__}: {exc}"
            answer, chunks, trace = "", [], None
        latencies.append(round(time.perf_counter() - started, 2))
        if error:
            break
        outcome = case.detector(answer, chunks)
        runs.append(
            {
                "attack_succeeded": outcome.attack_succeeded,
                "evidence": outcome.evidence,
                "answer": answer,
                "trace": trace,
                "retrieved": [
                    {
                        "document_id": c.metadata.get("document_id"),
                        "merchant_id": c.metadata.get("merchant_id"),
                        "trust_tier": c.metadata.get("trust_tier"),
                        "classification": c.metadata.get("classification"),
                    }
                    for c in chunks
                ],
            }
        )

    latency_s = round(sum(latencies) / len(latencies), 2)

    if error:
        outcome_succeeded, evidence, status = None, error, "ERROR"
        answer, chunks_meta, stability, trace = "", [], None, None
    else:
        succeeded_runs = sum(1 for r in runs if r["attack_succeeded"])
        # Worst run decides. Any success means the attack is not reliably stopped.
        outcome_succeeded = succeeded_runs > 0
        worst = next((r for r in runs if r["attack_succeeded"]), runs[0])
        answer, chunks_meta = worst["answer"], worst["retrieved"]
        evidence = worst["evidence"]
        trace = worst.get("trace")
        stability = f"{succeeded_runs}/{len(runs)} runs succeeded"
        if case.attack_type == "clean_legitimate_query":
            status = "FALSE_POSITIVE" if outcome_succeeded else "OK"
        else:
            status = "ATTACK_SUCCEEDED" if outcome_succeeded else "ATTACK_BLOCKED"
        if 0 < succeeded_runs < len(runs):
            status = "UNSTABLE"

    return {
        "case_id": case.case_id,
        "attack_type": case.attack_type,
        "requesting_merchant": case.requesting_merchant,
        "query": case.query,
        "expected": case.expected,
        "control_responsible": case.control,
        "status": status,
        "attack_succeeded": outcome_succeeded,
        "detector_evidence": evidence,
        "latency_s": latency_s,
        "repeat": repeat,
        "stability": stability,
        "runs": runs,
        "retrieved": chunks_meta,
        "answer": answer,
        "trace": trace,
    }


class StoredChunk:
    """Rehydrates the metadata of a retrieved chunk from a saved report."""

    def __init__(self, metadata):
        self.metadata = metadata
        self.page_content = ""


def rescore(report_path):
    """Re-run detectors over a saved report without calling any model.

    Detectors get revised as blind spots turn up. Re-running the pipeline to test
    a detector change would cost API calls and, worse, produce different model
    answers - so the numbers would move for two reasons at once. Re-scoring the
    stored answers isolates the detector change.
    """
    report = json.loads(Path(report_path).read_text())
    by_id = {c.case_id: c for c in CASES}

    changed = []
    for result in report["results"]:
        case = by_id.get(result["case_id"])
        if case is None or result["status"] in ("NOT_APPLICABLE", "ERROR"):
            continue

        # Re-score EVERY stored run, not just the worst one. Scoring only the
        # stored worst answer silently collapsed UNSTABLE into a single verdict
        # and under-counted attacks - it reported Phase 3 as 1/9 when three cases
        # were failing intermittently. Defect D8.
        runs = result.get("runs") or []
        if runs:
            succeeded = 0
            for run in runs:
                outcome = case.detector(run["answer"], [StoredChunk(m) for m in run["retrieved"]])
                run["attack_succeeded"] = outcome.attack_succeeded
                run["evidence"] = outcome.evidence
                succeeded += bool(outcome.attack_succeeded)
            worst = next((r for r in runs if r["attack_succeeded"]), runs[0])
            attack_succeeded = succeeded > 0
            evidence = worst["evidence"]
            result["answer"] = worst["answer"]
            result["retrieved"] = worst["retrieved"]
            result["trace"] = worst.get("trace")
            result["stability"] = f"{succeeded}/{len(runs)} runs succeeded"
        else:
            outcome = case.detector(result["answer"], [StoredChunk(m) for m in result["retrieved"]])
            attack_succeeded, evidence = outcome.attack_succeeded, outcome.evidence
            succeeded, runs = int(attack_succeeded), [None]

        if case.attack_type == "clean_legitimate_query":
            status = "FALSE_POSITIVE" if attack_succeeded else "OK"
        else:
            status = "ATTACK_SUCCEEDED" if attack_succeeded else "ATTACK_BLOCKED"
        if 0 < succeeded < len(runs):
            status = "UNSTABLE"

        if status != result["status"]:
            changed.append((result["case_id"], result["status"], status))
        result["status"] = status
        result["attack_succeeded"] = attack_succeeded
        result["detector_evidence"] = evidence

    report["summary"] = summarise(report["results"])
    report["rescored_at"] = datetime.now(timezone.utc).isoformat()
    Path(report_path).write_text(json.dumps(report, indent=2))
    return report, changed


def summarise(results):
    attacks = [r for r in results if r["attack_type"] != "clean_legitimate_query" and r["status"] not in ("NOT_APPLICABLE", "ERROR")]
    benign = [r for r in results if r["attack_type"] == "clean_legitimate_query" and r["status"] not in ("NOT_APPLICABLE", "ERROR")]
    succeeded = [r for r in attacks if r["attack_succeeded"]]
    unstable = [r for r in results if r["status"] == "UNSTABLE"]
    false_pos = [r for r in benign if r["attack_succeeded"]]
    latencies = [r["latency_s"] for r in results if r.get("latency_s")]
    return {
        "attack_cases": len(attacks),
        "attacks_succeeded": len(succeeded),
        "attack_success_rate": round(len(succeeded) / len(attacks), 3) if attacks else None,
        "benign_cases": len(benign),
        "false_positives": len(false_pos),
        "false_positive_rate": round(len(false_pos) / len(benign), 3) if benign else None,
        "unstable": len(unstable),
        "errors": sum(1 for r in results if r["status"] == "ERROR"),
        "not_applicable": sum(1 for r in results if r["status"] == "NOT_APPLICABLE"),
        "mean_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
    }


ICON = {
    "ATTACK_SUCCEEDED": "FAIL",
    "ATTACK_BLOCKED": "PASS",
    "OK": "PASS",
    "FALSE_POSITIVE": "FAIL",
    "UNSTABLE": "FLAK",
    "ERROR": "ERR ",
    "NOT_APPLICABLE": "n/a ",
}


def print_table(results, summary, pipeline_name):
    print(f"\n{'=' * 100}")
    print(f"SecurityAwareRAG adversarial evaluation - pipeline: {pipeline_name}")
    print("=" * 100)
    print(f"{'':4} {'CASE':14} {'ATTACK TYPE':36} {'STATUS':18} {'LAT':>6}")
    print("-" * 100)
    for r in results:
        lat = f"{r['latency_s']:.1f}s" if r.get("latency_s") else "-"
        stab = r.get("stability") or ""
        print(
            f"{ICON.get(r['status'], '?'):4} {r['case_id']:14} {r['attack_type']:36} "
            f"{r['status']:18} {lat:>6}  {stab}"
        )
    print("-" * 100)
    asr = summary["attack_success_rate"]
    fpr = summary["false_positive_rate"]
    print(
        f"Attack success rate : {summary['attacks_succeeded']}/{summary['attack_cases']}"
        f"  ({asr:.0%})" if asr is not None else "Attack success rate : n/a"
    )
    print(
        f"False positive rate : {summary['false_positives']}/{summary['benign_cases']}"
        f"  ({fpr:.0%})" if fpr is not None else "False positive rate : n/a"
    )
    print(f"Mean latency        : {summary['mean_latency_s']}s")
    if summary["errors"]:
        print(f"Errors              : {summary['errors']}")
    if summary.get("unstable"):
        print(f"Unstable            : {summary['unstable']} (blocked on some runs, not others - not a control)")
    if summary["not_applicable"]:
        print(f"Not yet measurable  : {summary['not_applicable']}")
    print("=" * 100)


def print_comparison(before, after):
    print(f"\n{'=' * 100}")
    print(f"BEFORE ({before['pipeline']}) vs AFTER ({after['pipeline']})")
    print("=" * 100)
    b = {r["case_id"]: r for r in before["results"]}
    print(f"{'CASE':14} {'ATTACK TYPE':32} {'BEFORE':18} {'AFTER':18} {'CHANGE'}")
    print("-" * 100)
    for r in after["results"]:
        prev = b.get(r["case_id"], {}).get("status", "-")
        change = ""
        if prev != r["status"]:
            fixed = prev == "ATTACK_SUCCEEDED" and r["status"] == "ATTACK_BLOCKED"
            regressed = prev in ("ATTACK_BLOCKED", "OK") and r["status"] in ("ATTACK_SUCCEEDED", "FALSE_POSITIVE")
            change = "FIXED" if fixed else ("REGRESSION" if regressed else "changed")
        print(f"{r['case_id']:14} {r['attack_type']:32} {prev:18} {r['status']:18} {change}")
    print("-" * 100)
    for label, rep in (("before", before), ("after", after)):
        s = rep["summary"]
        print(
            f"{label:7} ASR={s['attacks_succeeded']}/{s['attack_cases']} "
            f"FPR={s['false_positives']}/{s['benign_cases']} "
            f"latency={s['mean_latency_s']}s"
        )
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline", default="baseline", choices=sorted(PIPELINES))
    parser.add_argument("--phase", type=int, default=0, help="highest implemented phase")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case; >1 measures stability")
    parser.add_argument("--compare", help="path to an earlier report to diff against")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--rescore", help="re-run detectors over a saved report; makes no API calls")
    args = parser.parse_args()

    if args.rescore:
        report, changed = rescore(args.rescore)
        print_table(report["results"], report["summary"], report["pipeline"] + " (rescored)")
        if changed:
            print("\nverdicts changed by the detector update:")
            for case_id, was, now in changed:
                print(f"  {case_id:14} {was} -> {now}")
        else:
            print("\nno verdicts changed")
        return

    cases = CASES
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        cases = [c for c in CASES if c.case_id in wanted]

    pipeline = get_pipeline(args.pipeline)
    ground_truth = load_ground_truth()

    results = []
    for case in cases:
        print(f"  running {case.case_id} ...", flush=True)
        result = run_case(case, pipeline, args.phase, repeat=args.repeat)
        result["source_documents"] = [
            {"document_id": d, "labelled_attack": ground_truth.get(d, {}).get("attack")}
            for d in case.source_documents
        ]
        results.append(result)

    summary = summarise(results)
    report = {
        "pipeline": args.pipeline,
        "phase": args.phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }

    REPORTS.mkdir(exist_ok=True)
    suffix = f"_x{args.repeat}" if args.repeat > 1 else ""
    out = REPORTS / f"{args.pipeline}_phase{args.phase}{suffix}.json"
    out.write_text(json.dumps(report, indent=2))

    print_table(results, summary, args.pipeline)
    print(f"\nreport: {out.relative_to(ROOT)}")

    if args.compare:
        before = json.loads(Path(args.compare).read_text())
        print_comparison(before, report)


if __name__ == "__main__":
    main()

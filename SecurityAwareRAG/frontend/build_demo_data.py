"""Build the static demo artifact from recorded evaluation reports and the corpus.

    python frontend/build_demo_data.py

Produces `frontend/data/demo.json`. That file plus a static page is the entire
demo: no OpenAI, no Chroma, no evaluation runner, no security module, no network.

=============================================================================
DIVISION OF RESPONSIBILITY
=============================================================================
    pipeline        makes security decisions and emits them as a trace
    THIS SCRIPT     joins two recorded runs and attributes outcomes, in Python,
                    with the result committed and inspectable
    browser         renders strings

The browser must never infer a security outcome. Everything it needs is resolved
here and written out as data.

=============================================================================
WHY ATTRIBUTION HAPPENS HERE
=============================================================================
`stopped_at` names the layer that TERMINATED a request, and only the two
governance gates can do that. Tenant authorization and redaction CONSTRAIN
instead: the request completes, having been denied the data it reached for. So a
single protected trace cannot tell you that authorization is what defeated
XTENANT-01 - `foreign_documents_retrieved` is simply empty, which is also what an
unrelated query looks like.

The attribution comes from the DIFFERENCE between the unprotected and protected
runs of the same case: four merchant_alpha documents retrieved without the
boundary, zero with it. That is a comparison of two measurements, not a guess,
and it is done here rather than in the browser so it is reviewable.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "evaluation" / "reports"
CORPUS = ROOT / "merchant_risk_knowledge_base"
OUT = Path(__file__).resolve().parent / "data" / "demo.json"

OFF_REPORT = "baseline_phase0_x8.json"
ON_REPORT = "secure_p8_phase8_x8.json"

def load_corpus():
    documents = {}
    for line in (CORPUS / "documents.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        documents[record["document_id"]] = {
            "document_id": record["document_id"],
            "merchant_id": record["merchant_id"],
            "trust_tier": record["trust_tier"],
            "classification": record["classification"],
            "source_type": record["source_type"],
            "path": record["path"],
            "content": record["content"],
        }
    return documents


def load_ground_truth():
    data = json.loads((CORPUS / "ground_truth.json").read_text())
    return {
        record["document_id"]: {
            "attack": record.get("attack"),
            "notes": record.get("notes"),
        }
        for record in data["ground_truth"]
    }


def _layer_detail(trace, layer_id):
    if not trace:
        return {}
    for layer in trace["layers"]:
        if layer["id"] == layer_id:
            return layer.get("detail") or {}
    return {}


def _tally(results, total):
    """Count how many runs each layer appeared in, as recorded facts."""
    counts = Counter(layer for run in results for layer in run)
    return {layer: f"{n}/{total}" for layer, n in counts.most_common()}


def summarise_runs(result):
    """Aggregate the per-run telemetry. Derived ONLY from recorded pipeline facts.

    There is deliberately no attribution here - no attack_type, no expected
    boundary, no benign special case, and no reading of an OFF/ON retrieval
    difference as "the attack was neutralised". Earlier versions did all four and
    got BENIGN-01 graded as an authorization-enforced attack, because the
    unprotected pipeline incidentally retrieves a semantically similar document
    belonging to another merchant on perfectly ordinary queries.

    Retrieval deltas are still published, as raw evidence for a reader. They are
    not converted into a security claim.
    """
    runs = result.get("runs") or []
    total = len(runs) or 1
    enforced = [(run.get("trace") or {}).get("enforced_by", []) for run in runs]
    constrained = [(run.get("trace") or {}).get("constrained_by", []) for run in runs]
    rendered = Counter(
        str((run.get("trace") or {}).get("rendered_refusal")) for run in runs
    )
    return {
        "enforced_by_runs": _tally(enforced, total),
        "constrained_by_runs": _tally(constrained, total),
        "rendered_refusal_runs": dict(rendered),
        "executed_runs": sum(
            1 for run in runs if (run.get("trace") or {}).get("executed")
        ),
        "run_count": len(runs),
    }


def retrieval_delta(off_result, on_result):
    """Raw retrieval evidence, unlabelled and uninterpreted."""

    def foreign(result):
        detail = _layer_detail(result.get("trace"), "tenant_authorization")
        return detail.get("foreign_documents_retrieved", [])

    def documents(result):
        return [d.get("document_id") for d in result.get("retrieved", [])]

    return {
        "off_documents": documents(off_result),
        "on_documents": documents(on_result),
        "off_other_tenant_documents": foreign(off_result),
        "on_other_tenant_documents": foreign(on_result),
        "note": (
            "Raw retrieval evidence. Tenant authorization filters candidates "
            "server-side, so excluded candidates are not observable; this "
            "difference is not an enforcement claim."
        ),
    }


def side(result):
    """One pipeline's recorded evidence for a case.

    `runs` carries every recorded run with its own trace. `detail_run_index`
    identifies which of them the top-level `answer`/`trace` came from - the
    runner stores the first run where the attack succeeded, else the first run.

    That index matters: for POISON-01 the stored run is one where the
    determination gate fired, while the gate fired on only 3 of 8 runs. A viewer
    that renders the stored trace as the case's behaviour would overstate
    enforcement by a factor of nearly three. The UI must label it as one run.
    """
    runs = result.get("runs") or []
    detail_index = next(
        (i for i, run in enumerate(runs) if run.get("attack_succeeded")), 0
    )
    return {
        "pipeline": result.get("pipeline"),
        "status": result["status"],
        "stability": result.get("stability"),
        "repeat": result.get("repeat"),
        "latency_s": result.get("latency_s"),
        "answer": result.get("answer"),
        "detector_evidence": result.get("detector_evidence"),
        "retrieved": result.get("retrieved", []),
        "trace": result.get("trace"),
        "runs": runs,
        "run_count": len(runs),
        "detail_run_index": detail_index if runs else None,
    }


def main():
    off = json.loads((REPORTS / OFF_REPORT).read_text())
    on = json.loads((REPORTS / ON_REPORT).read_text())
    off_by_id = {r["case_id"]: r for r in off["results"]}

    # Layer catalogue comes from the security module so the UI legend cannot
    # drift from the pipeline. Read as data; nothing here calls into it.
    import sys

    sys.path.insert(0, str(ROOT / "pro_implementation"))
    from security.trace import layer_catalogue

    cases = []
    for on_result in on["results"]:
        off_result = off_by_id.get(on_result["case_id"], {})
        on_summary = summarise_runs(on_result)
        off_side, on_side = side(off_result), side(on_result)
        off_side["pipeline"] = off["pipeline"]
        on_side["pipeline"] = on["pipeline"]

        cases.append(
            {
                "case_id": on_result["case_id"],
                "attack_type": on_result["attack_type"],
                "query": on_result["query"],
                "requesting_merchant": on_result["requesting_merchant"],
                "expected": on_result["expected"],
                "attack_documents": [
                    d["document_id"] for d in on_result.get("source_documents", [])
                ],
                **on_summary,
                "retrieval_delta": retrieval_delta(off_result, on_result),
                "off": off_side,
                "on": on_side,
            }
        )

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Rendered from recorded evaluation runs. This artifact performs no "
            "security enforcement and makes no network calls. Every value is "
            "traceable to a committed report in evaluation/reports/."
        ),
        "source_reports": {
            "off": {"file": OFF_REPORT, "pipeline": off["pipeline"], "phase": off["phase"], "timestamp": off["timestamp"]},
            "on": {"file": ON_REPORT, "pipeline": on["pipeline"], "phase": on["phase"], "timestamp": on["timestamp"]},
        },
        "layers": layer_catalogue(),
        "corpus": load_corpus(),
        "ground_truth": load_ground_truth(),
        "ground_truth_note": (
            "Evaluation labels only. These are never read by the runtime pipeline "
            "and do not constitute detection."
        ),
        "cases": cases,
        "summary": {"off": off["summary"], "on": on["summary"]},
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    for case in cases:
        print(
            f"  {case['case_id']:14} enforced={str(case['enforced_by_runs']):58} "
            f"constrained={list(case['constrained_by_runs'])}"
        )


if __name__ == "__main__":
    main()

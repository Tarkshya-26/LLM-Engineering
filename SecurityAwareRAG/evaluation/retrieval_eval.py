"""Retrieval quality — baseline vs governed. MRR and nDCG over the merchant corpus.

    python evaluation/retrieval_eval.py

Answers the question a reviewer asks straight after the security results:
*did the six layers break the RAG?*

WHAT IS MEASURED
Only legitimate questions, asked by the tenant entitled to the answer. A
cross-tenant question would score zero under governance, but that is the security
control working, not a quality regression - mixing those in would make the
comparison meaningless.

RELEVANCE SIGNAL
A retrieved chunk is relevant when its `document_id` is in the test's expected
set. The inherited Week 5 harness matched keyword substrings against chunk text,
which is fuzzy: a keyword can appear in a document that does not answer the
question. Chunks already carry `document_id`, so exact document relevance is
available and is what this uses.

This script changes no security behaviour. It calls the same retrieval paths the
pipelines use and scores what comes back.
"""

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from proAnswer import fetch_context  # noqa: E402
from secure_answer import PHASE_CONFIGS, authorized_fetch_context  # noqa: E402
from security.authorization import RequestContext  # noqa: E402

TESTS = Path(__file__).resolve().parent / "retrieval_tests.jsonl"
OUT = Path(__file__).resolve().parent / "reports" / "retrieval_quality.json"


def relevances(chunks, relevant_ids):
    """Binary relevance vector in rank order."""
    return [1 if c.metadata.get("document_id") in relevant_ids else 0 for c in chunks]


def mrr(rels):
    for rank, r in enumerate(rels, start=1):
        if r:
            return 1.0 / rank
    return 0.0


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg(rels):
    ideal = dcg(sorted(rels, reverse=True))
    return dcg(rels) / ideal if ideal else 0.0


def run(name, retrieve, tests):
    rows = []
    for t in tests:
        started = time.perf_counter()
        chunks = retrieve(t)
        elapsed = time.perf_counter() - started
        rels = relevances(chunks, set(t["relevant"]))
        rows.append({
            "id": t["id"],
            "merchant_id": t["merchant_id"],
            "question": t["question"],
            "relevant": t["relevant"],
            "retrieved": [c.metadata.get("document_id") for c in chunks],
            "hit": bool(sum(rels)),
            "mrr": round(mrr(rels), 4),
            "ndcg": round(ndcg(rels), 4),
            "latency_s": round(elapsed, 2),
        })
        print(f"  {name:9} {t['id']}  mrr {rows[-1]['mrr']:.3f}  ndcg {rows[-1]['ndcg']:.3f}",
              flush=True)
    return {
        "pipeline": name,
        "mrr": round(statistics.mean(r["mrr"] for r in rows), 4),
        "ndcg": round(statistics.mean(r["ndcg"] for r in rows), 4),
        "hit_rate": round(sum(r["hit"] for r in rows) / len(rows), 4),
        "mean_latency_s": round(statistics.mean(r["latency_s"] for r in rows), 2),
        "results": rows,
    }


def spread(values):
    return {"mean": round(statistics.mean(values), 4),
            "min": round(min(values), 4), "max": round(max(values), 4),
            "runs": [round(v, 4) for v in values]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3,
                        help="sweeps per pipeline; retrieval uses an LLM rewriter and "
                             "reranker, so a single sweep is not evidence")
    args = parser.parse_args()

    tests = [json.loads(l) for l in TESTS.read_text().splitlines() if l.strip()]
    print(f"{len(tests)} legitimate questions · document-id relevance · "
          f"{args.repeat} sweeps per pipeline\n")

    pipelines = {
        "baseline": lambda t: fetch_context(t["question"]),
        "governed": lambda t: authorized_fetch_context(
            t["question"], RequestContext(t["merchant_id"]), PHASE_CONFIGS[8])[0],
    }

    report = {"tests": len(tests), "repeat": args.repeat, "pipelines": {}}
    for name, retrieve in pipelines.items():
        sweeps = [run(name, retrieve, tests) for _ in range(args.repeat)]
        report["pipelines"][name] = {
            "mrr": spread([s["mrr"] for s in sweeps]),
            "ndcg": spread([s["ndcg"] for s in sweeps]),
            "hit_rate": spread([s["hit_rate"] for s in sweeps]),
            "mean_latency_s": spread([s["mean_latency_s"] for s in sweeps]),
            "sweeps": sweeps,
        }
        print()

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))

    b, g = report["pipelines"]["baseline"], report["pipelines"]["governed"]
    print("=" * 74)
    print(f"{'':10} {'MRR':>22} {'nDCG':>22} {'hit':>8} {'latency':>9}")
    print("-" * 74)
    for name, r in (("baseline", b), ("governed", g)):
        print(f"{name:10} {r['mrr']['mean']:8.3f} "
              f"[{r['mrr']['min']:.3f}–{r['mrr']['max']:.3f}] "
              f"{r['ndcg']['mean']:8.3f} [{r['ndcg']['min']:.3f}–{r['ndcg']['max']:.3f}] "
              f"{r['hit_rate']['mean']:7.0%} {r['mean_latency_s']['mean']:8.2f}s")
    print("-" * 74)
    dm = g["mrr"]["mean"] - b["mrr"]["mean"]
    dn = g["ndcg"]["mean"] - b["ndcg"]["mean"]
    overlap = (b["mrr"]["min"] <= g["mrr"]["max"] and g["mrr"]["min"] <= b["mrr"]["max"])
    print(f"{'delta':10} MRR {dm:+.3f}   nDCG {dn:+.3f}")
    print(f"{'':10} ranges overlap: {overlap} -> "
          f"{'indistinguishable at this sample size' if overlap else 'separated'}")
    print("=" * 74)
    print(f"report: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

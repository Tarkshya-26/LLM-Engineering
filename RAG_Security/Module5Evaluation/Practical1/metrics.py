# metrics-lab.py
# Evaluate a vector retrieval workflow against a golden query set: compute recall@k,
# precision@k, MRR, and coverage, break them down by query type, and auto-generate
# improvement recommendations. Run it any time -- before you finish it previews the metrics
# that are already implemented; once complete it prints the full report and writes
# metrics-report.json. Runs fully offline (standard library only).

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
QUERIES_PATH = DATA_DIR / "golden-queries.json"
RESULTS_PATH = DATA_DIR / "retrieval-results.json"
REPORT_PATH = DATA_DIR / "metrics-report.json"

K = 3   # evaluate the top-3 retrieved results


def mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else 0.0


# ---- Provided metric: Reciprocal Rank (the building block of MRR) ----
def reciprocal_rank(retrieved_ids, relevant_ids):
    # 1 / rank of the FIRST relevant result (0 if none of the top results are relevant).
    for rank, doc in enumerate(retrieved_ids, start=1):
        if doc in relevant_ids:
            return 1.0 / rank
    return 0.0


# ---- Provided metric: coverage helper (did the query get any relevant hit in top-k?) ----
def is_covered(retrieved_ids, relevant_ids, k):
    return any(doc in relevant_ids for doc in retrieved_ids[:k])


# ============================================================================
# YOUR TODOs
# ============================================================================
def recall_at_k(retrieved_ids, relevant_ids, k):
    # TODO (Step 6): recall@k = (number of relevant items found in the top k) / (total relevant).
    #   Hint: intersect set(retrieved_ids[:k]) with relevant_ids, divide by len(relevant_ids).
    ...
    return len(set(retrieved_ids[:k]) & set(relevant_ids)) / len(relevant_ids)

def precision_at_k(retrieved_ids, relevant_ids, k):
    # TODO (Step 6): precision@k = (number of relevant items found in the top k) / k.
    #   Hint: same intersection as above, but divide by k.
    ...
    return len(set(retrieved_ids[:k]) & set(relevant_ids)) / k

# ---- Provided: per-query rows, slicing, report, and diagnosis ----
def evaluate(queries, results):
    rows = []
    for q in queries:
        relevant = set(q.get("relevant_doc_ids") or [])
        retrieved = results[q["id"]]
        labeled = bool(relevant)
        rows.append({
            "id": q["id"],
            "type": q["query_type"],
            "labeled": labeled,
            "rr": reciprocal_rank(retrieved, relevant) if labeled else None,
            "covered": is_covered(retrieved, relevant, K) if labeled else None,
            "recall": recall_at_k(retrieved, relevant, K) if labeled else None,
            "precision": precision_at_k(retrieved, relevant, K) if labeled else None,
        })
    return rows


def slice_by_type(rows, keys):
    out = {}
    for t in sorted({r["type"] for r in rows if r["labeled"]}):
        group = [r for r in rows if r["labeled"] and r["type"] == t]
        out[t] = {key: mean([r[key] for r in group]) for key in keys}
        out[t]["coverage"] = mean([1.0 if r["covered"] else 0.0 for r in group])
        out[t]["n"] = len(group)
    return out


def diagnose(slices):
    recs = []
    worst_recall = min(slices, key=lambda t: slices[t]["recall"])
    recs.append(f"'{worst_recall}' queries have the lowest recall@{K} "
                f"({slices[worst_recall]['recall']:.2f}) -> suspect missing source content, weak "
                f"embeddings, or over-aggressive filters for that query type.")
    worst_mrr = min(slices, key=lambda t: slices[t]["mrr"])
    recs.append(f"'{worst_mrr}' has the lowest MRR ({slices[worst_mrr]['mrr']:.2f}) -> the first "
                f"relevant result ranks too low; consider reranking or hybrid retrieval.")
    worst_cov = min(slices, key=lambda t: slices[t]["coverage"])
    recs.append(f"'{worst_cov}' has the lowest coverage ({slices[worst_cov]['coverage']:.2f}) -> "
                f"add golden queries and source content for that category, then re-evaluate.")
    return recs


def print_table(rows, finished):
    print(f"Per-query metrics (k={K}):")
    for r in rows:
        if not r["labeled"]:
            print(f"  {r['id']:<4} {r['type']:<16} (unlabeled - add relevant_doc_ids)")
            continue
        rec = f"{r['recall']:.2f}" if isinstance(r["recall"], (int, float)) else "pending"
        pre = f"{r['precision']:.2f}" if isinstance(r["precision"], (int, float)) else "pending"
        print(f"  {r['id']:<4} {r['type']:<16} recall={rec:<7} precision={pre:<7} RR={r['rr']:.2f}")


if __name__ == "__main__":
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    rows = evaluate(queries, results)

    unlabeled = [r["id"] for r in rows if not r["labeled"]]
    metrics_pending = any(r["labeled"] and r["recall"] is ... for r in rows)
    finished = not unlabeled and not metrics_pending

    if not finished:
        # Preview / "Show" view: the provided metrics (MRR, coverage) run regardless.
        print("=== RETRIEVAL EVALUATION (preview) ===")
        print_table(rows, finished=False)
        labeled = [r for r in rows if r["labeled"]]
        print(f"\nProvided metrics so far: MRR={mean([r['rr'] for r in labeled]):.2f}  "
              f"coverage={mean([1.0 if r['covered'] else 0.0 for r in labeled]):.2f}")
        print("\nOpen steps:")
        if unlabeled:
            print(f"  - Step 3: label {', '.join(unlabeled)} (add relevant_doc_ids in golden-queries.json)")
        if metrics_pending:
            print("  - Step 6: implement recall_at_k and precision_at_k in metrics-lab.py")
        print("\nComplete the open step(s) above, then run again for the full report.")
        raise SystemExit(0)

    slices = slice_by_type(rows, keys=["recall", "precision", "rr"])
    for s in slices.values():
        s["mrr"] = s.pop("rr")

    print("--- START SCREENSHOT ---")
    print(f"=== RETRIEVAL EVALUATION REPORT (k={K}) ===")
    print_table(rows, finished=True)

    labeled = [r for r in rows if r["labeled"]]
    print("\nOverall:")
    print(f"  recall@{K}={mean([r['recall'] for r in labeled]):.2f}  "
          f"precision@{K}={mean([r['precision'] for r in labeled]):.2f}  "
          f"MRR={mean([r['rr'] for r in labeled]):.2f}  "
          f"coverage={mean([1.0 if r['covered'] else 0.0 for r in labeled]):.2f}")

    print("\nBy query_type:")
    print(f"  {'type':<16} {'recall':>7} {'prec':>7} {'MRR':>7} {'coverage':>9}  n")
    for t, s in slices.items():
        print(f"  {t:<16} {s['recall']:>7.2f} {s['precision']:>7.2f} {s['mrr']:>7.2f} {s['coverage']:>9.2f}  {s['n']}")

    print("\nDiagnosis / recommendations:")
    recs = diagnose(slices)
    for i, rec in enumerate(recs, start=1):
        print(f"  {i}. {rec}")

    report = {
        "k": K,
        "overall": {
            "recall_at_k": round(mean([r["recall"] for r in labeled]), 3),
            "precision_at_k": round(mean([r["precision"] for r in labeled]), 3),
            "mrr": round(mean([r["rr"] for r in labeled]), 3),
            "coverage": round(mean([1.0 if r["covered"] else 0.0 for r in labeled]), 3),
        },
        "by_query_type": {t: {k: round(v, 3) for k, v in s.items()} for t, s in slices.items()},
        "recommendations": recs,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH.name} (reproducible evaluation evidence).")
    print("--- END SCREENSHOT ---")

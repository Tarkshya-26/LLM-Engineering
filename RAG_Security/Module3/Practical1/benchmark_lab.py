## Whole lab in short grisp :

# We are basically evaluating how much our ANN Network retrieved the valid chunks against
# All the chunks 3/5 known as Recall@k





# benchmark-lab.py
# Benchmark EXACT vs APPROXIMATE (ANN) vector retrieval on a reproducible synthetic dataset.
# Measure recall@k and search cost, emit a comparison matrix and benchmark_report.json, and
# judge whether the approximate configuration meets the use case's acceptance targets.
# Runs fully offline: FAISS + numpy. Embeddings are generated deterministically (no downloads).

import json
import time
from pathlib import Path
import numpy as np
import faiss

DATA_DIR = Path(__file__).parent
CONFIG_PATH = DATA_DIR / "dataset-config.json"
REPORT_PATH = DATA_DIR / "benchmark_report.json"


def build_dataset(cfg):
    # Deterministic synthetic embeddings with topic-like cluster structure (seeded for reproducibility).
    rng = np.random.default_rng(cfg["seed"])
    centers = rng.standard_normal((cfg["n_clusters"], cfg["dim"])).astype("float32")
    labels = rng.integers(0, cfg["n_clusters"], size=cfg["n_vectors"])
    data = centers[labels] + cfg["spread"] * rng.standard_normal((cfg["n_vectors"], cfg["dim"])).astype("float32")
    data = data.astype("float32")
    faiss.normalize_L2(data)                       # cosine similarity via normalized inner product
    source_ids = [f"doc-{i:05d}" for i in range(cfg["n_vectors"])]

    # Queries sit near real corpus points, like genuine near-neighbor lookups.
    qrng = np.random.default_rng(cfg["seed"] + 1)
    qidx = qrng.integers(0, cfg["n_vectors"], size=cfg["n_queries"])
    queries = (data[qidx] + 0.1 * qrng.standard_normal((cfg["n_queries"], cfg["dim"])).astype("float32")).astype("float32")
    faiss.normalize_L2(queries)
    query_ids = [f"q{j:03d}" for j in range(cfg["n_queries"])]
    return data, source_ids, queries, query_ids


def recall_at_k(approx_ids, exact_ids, k):
    # TODO: recall@k for ONE query = (how many of the exact top-k ids the approximate search
    #       also returned) / k. `approx_ids` and `exact_ids` are lists of result ids (ints),
    #       and `exact_ids` is the ground truth. Return a float between 0.0 and 1.0.
    #       Hint: set intersection makes this a one-liner.
    ...
    return len(set(approx_ids)) & set(exact_ids) / k


def search_all(index, queries, k):
    # Return the top-k result ids per query and the mean latency in milliseconds.
    start = time.perf_counter()
    _, ids = index.search(queries, k)
    mean_ms = (time.perf_counter() - start) / len(queries) * 1000
    return ids, mean_ms


def build_matrix(k, exact, approx, target_recall, max_scan, nprobe):
    rows = [
        ("Exact (FlatIP)", 1.000, 1.000, exact["latency_ms"], 1.0),
        (f"Approx (IVF nprobe={nprobe})", approx["recall_at_k"], approx["scan_fraction"],
         approx["latency_ms"], exact["latency_ms"] / approx["latency_ms"] if approx["latency_ms"] else float("inf")),
    ]
    out = [
        f"| {'Strategy':<26} | recall@{k} | scan fraction | mean latency (ms) | speedup |",
        f"| {'-'*26} | {'-'*9} | {'-'*13} | {'-'*17} | {'-'*7} |",
    ]
    for name, rec, scan, lat, sp in rows:
        out.append(f"| {name:<26} | {rec:>9.3f} | {scan*100:>12.1f}% | {lat:>17.3f} | {sp:>6.1f}x |")
    out.append("")
    out.append(f"Acceptance target: recall@{k} >= {target_recall:.2f}  AND  scan fraction <= {max_scan:.0%}")
    return "\n".join(out)


if __name__ == "__main__":
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    k, nlist, nprobe = cfg["k"], cfg["index"]["nlist"], cfg["index"]["nprobe"]
    data, source_ids, queries, query_ids = build_dataset(cfg)

    # Exact baseline = ground truth (scans the whole corpus).
    flat = faiss.IndexFlatIP(cfg["dim"])
    flat.add(data)
    exact_ids, exact_ms = search_all(flat, queries, k)

    # Approximate index = IVF (scans only nprobe of nlist partitions).
    quantizer = faiss.IndexFlatIP(cfg["dim"])
    ivf = faiss.IndexIVFFlat(quantizer, cfg["dim"], nlist, faiss.METRIC_INNER_PRODUCT)
    ivf.train(data)
    ivf.add(data)
    ivf.nprobe = nprobe
    approx_ids, approx_ms = search_all(ivf, queries, k)

    # recall@k per query, using YOUR recall_at_k implementation.
    per_query = [recall_at_k(list(approx_ids[j]), list(exact_ids[j]), k) for j in range(cfg["n_queries"])]
    if any(r is None for r in per_query):
        print("recall_at_k is not implemented yet - complete the TODO and run again.")
        raise SystemExit(0)

    mean_recall = float(np.mean(per_query))
    scan_fraction = nprobe / nlist
    target_recall = cfg["acceptance"]["min_recall_at_k"]
    max_scan = cfg["acceptance"]["max_scan_fraction"]

    reasons = []
    if mean_recall < target_recall:
        reasons.append(f"recall@{k} {mean_recall:.3f} is below the target {target_recall:.2f} - raise nprobe")
    if scan_fraction > max_scan:
        reasons.append(f"scan fraction {scan_fraction:.1%} exceeds the budget {max_scan:.0%} - lower nprobe")
    acceptable = not reasons

    exact = {"recall_at_k": 1.0, "scan_fraction": 1.0, "latency_ms": round(exact_ms, 3)}
    approx = {"recall_at_k": round(mean_recall, 3), "scan_fraction": scan_fraction, "latency_ms": round(approx_ms, 3)}

    # Always save the report artifact (auditable record of this experiment).
    report = {
        "config": cfg,
        "results": {"exact": exact, "approximate": approx},
        "sample_queries": [
            {
                "query_id": query_ids[j],
                "exact_top_k": [source_ids[i] for i in exact_ids[j]],
                "approx_top_k": [source_ids[i] for i in approx_ids[j]],
                "recall_at_k": round(per_query[j], 3),
            }
            for j in range(min(5, cfg["n_queries"]))
        ],
        "verdict": {"acceptable": acceptable, "reasons": reasons},
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    matrix = build_matrix(k, exact, approx, target_recall, max_scan, nprobe)
    if acceptable:
        print("--- START SCREENSHOT ---")
        print("=" * 72)
        print("  EXACT vs APPROXIMATE RETRIEVAL BENCHMARK")
        print("=" * 72)
        print(matrix)
        print("\nVerdict: ACCEPTABLE - the approximate index meets the recall and cost targets.")
        print(f"Saved {REPORT_PATH.name} ({len(report['sample_queries'])} sample queries with source IDs).")
        print("--- END SCREENSHOT ---")
    else:
        print(matrix)
        print("\nVerdict: NOT ACCEPTABLE")
        for r in reasons:
            print(f"  - {r}")
        print('\nEdit "nprobe" under "index" in dataset-config.json and run again.')
        print(f"(Report saved to {REPORT_PATH.name}.)")

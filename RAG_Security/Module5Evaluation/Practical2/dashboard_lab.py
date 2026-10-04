# dashboard-lab.py
# Generate a retrieval observability dashboard from an operational request log plus the quality
# metrics from the previous lab. It renders quality + health panels, compares against a baseline
# to flag drift, evaluates alert thresholds, and writes dashboard.md. The percentile math, panels,
# alerting, and rendering are provided -- you complete three short metric lines.
# Runs fully offline (standard library only).

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
LOG_PATH = DATA_DIR / "request-log.json"
QUALITY_PATH = DATA_DIR / "quality-metrics.json"
BASELINE_PATH = DATA_DIR / "baseline.json"
THRESHOLDS_PATH = DATA_DIR / "alert-thresholds.json"
DASHBOARD_PATH = DATA_DIR / "dashboard.md"

WINDOW_MINUTES = 5   # the request log covers a 5-minute window (used for throughput)


def mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else 0.0


# ---- Provided operational metrics ----
def percentile(values, p):
    # The p-th percentile latency: averages hide the slow tail, so we report p95/p99.
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(p / 100 * len(ordered)))
    return ordered[idx]


def throughput_per_min(requests):
    return len(requests) / WINDOW_MINUTES


def timeout_rate(requests):
    # Provided as the model for the rates you will write next.
    return sum(1 for r in requests if r["status"] == "timeout") / len(requests)


# ============================================================================
# YOUR TODOs
# ============================================================================
def error_rate(requests):
    # TODO (Step 4): fraction of requests whose status is NOT "ok" (errors and timeouts both
    #   count as failures). Model it on timeout_rate above.
    ...
    return sum(1 for r in requests if r["status"] != "ok") / len(requests)

def empty_result_rate(requests):
    # TODO (Step 4): fraction of SUCCESSFUL requests that returned nothing -- status == "ok"
    #   AND num_results == 0. (A successful-but-empty search signals filter/permission/source drift.)
    ...
    return sum(1 for r in requests if r["status"] == "ok" and r["num_results"] == 0) / len(requests)

def is_drifting(current, baseline, tolerance):
    # TODO (Step 6): return True when `current` is worse than `baseline` by more than the
    #   tolerance fraction, i.e. current is greater than baseline * (1 + tolerance).
    ...
    return current > baseline * (1 + tolerance)


# ---- Provided: per-tenant slice, alerts, drift, and the dashboard renderer ----
def empty_rate_by_tenant(requests):
    out = {}
    for t in sorted({r["tenant"] for r in requests}):
        group = [r for r in requests if r["tenant"] == t]
        empties = sum(1 for r in group if r["status"] == "ok" and r["num_results"] == 0)
        out[t] = empties / len(group)
    return out


def evaluate_alerts(metrics, thresholds):
    alerts = []
    for name, policy in thresholds.items():
        if name.startswith("_"):
            continue
        value = metrics[name]
        if value > policy["max"]:
            alerts.append((policy["severity"], name, value, policy["max"], policy["owner"]))
    order = {"PAGE": 0, "WARN": 1}
    return sorted(alerts, key=lambda a: order.get(a[0], 9))


def render_dashboard(metrics, quality, by_tenant, baseline, alerts, drift):
    L = []
    L.append("# Retrieval Observability Dashboard")
    L.append(f"_window: last {WINDOW_MINUTES} min | {metrics['total_requests']} requests_")
    L.append("")
    L.append("## Quality (from offline evaluation)")
    L.append(f"- recall@{quality['k']}={quality['recall_at_k']:.2f}  precision@{quality['k']}={quality['precision_at_k']:.2f}  "
             f"MRR={quality['mrr']:.2f}  coverage={quality['coverage']:.2f}")
    L.append("")
    L.append("## Operational health")
    L.append(f"- latency: avg={metrics['avg_latency']:.0f}ms  p95={metrics['p95_latency_ms']:.0f}ms  p99={metrics['p99_latency']:.0f}ms")
    L.append(f"- throughput: {metrics['throughput']:.1f} req/min")
    L.append(f"- error_rate={metrics['error_rate']:.2%}  timeout_rate={metrics['timeout_rate']:.2%}  empty_result_rate={metrics['empty_result_rate']:.2%}")
    L.append("")
    L.append("## Governance-aware slice: empty-result rate by tenant")
    for t, rate in by_tenant.items():
        L.append(f"- {t}: {rate:.2%}")
    L.append("")
    L.append("## Drift vs. baseline")
    for name, info in drift.items():
        flag = "DRIFT" if info["drifting"] else "ok"
        L.append(f"- {name}: now={info['current']}  baseline={info['baseline']}  [{flag}]")
    L.append("")
    L.append("## Alerts")
    if alerts:
        for sev, name, value, mx, owner in alerts:
            L.append(f"- {sev} {name}={value:.2%} (max {mx:.2%}) -> owner: {owner}" if value < 1
                     else f"- {sev} {name}={value:.0f} (max {mx:.0f}) -> owner: {owner}")
    else:
        L.append("- none")
    return "\n".join(L)


if __name__ == "__main__":
    requests = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    quality = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))

    latencies = [r["latency_ms"] for r in requests]
    err = error_rate(requests)
    empty = empty_result_rate(requests)
    drift_probe = is_drifting(2.0, 1.0, 0.5)   # implemented -> returns a bool

    pending = []
    if not isinstance(err, (int, float)):
        pending.append("Step 4: implement error_rate")
    if not isinstance(empty, (int, float)):
        pending.append("Step 4: implement empty_result_rate")
    if not isinstance(drift_probe, bool):
        pending.append("Step 6: implement is_drifting")

    print("=== Retrieval observability ===")
    print(f"requests={len(requests)}  avg_latency={mean(latencies):.0f}ms  "
          f"p95={percentile(latencies, 95):.0f}ms  p99={percentile(latencies, 99):.0f}ms  "
          f"throughput={throughput_per_min(requests):.1f}/min  timeout_rate={timeout_rate(requests):.2%}")

    if pending:
        print("\nNot finished yet:")
        for p in pending:
            print(f"  - {p}")
        print("\n(error_rate, empty_result_rate, and drift appear once those are implemented.)")
        print("Complete the open step(s) above, then run again for the full dashboard.")
        raise SystemExit(0)

    metrics = {
        "total_requests": len(requests),
        "avg_latency": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "p99_latency": percentile(latencies, 99),
        "throughput": throughput_per_min(requests),
        "timeout_rate": timeout_rate(requests),
        "error_rate": err,
        "empty_result_rate": empty,
    }
    drift = {
        "empty_result_rate": {"current": round(empty, 3), "baseline": baseline["empty_result_rate"],
                              "drifting": is_drifting(empty, baseline["empty_result_rate"], 0.5)},
        "error_rate": {"current": round(err, 3), "baseline": baseline["error_rate"],
                       "drifting": is_drifting(err, baseline["error_rate"], 0.5)},
        "p95_latency_ms": {"current": metrics["p95_latency_ms"], "baseline": baseline["p95_latency_ms"],
                           "drifting": is_drifting(metrics["p95_latency_ms"], baseline["p95_latency_ms"], 0.5)},
    }
    alerts = evaluate_alerts(metrics, thresholds)
    by_tenant = empty_rate_by_tenant(requests)

    dashboard = render_dashboard(metrics, quality, by_tenant, baseline, alerts, drift)
    DASHBOARD_PATH.write_text(dashboard + "\n", encoding="utf-8")

    print("\n--- START SCREENSHOT ---")
    print(dashboard)
    print(f"\nWrote {DASHBOARD_PATH.name} (the dashboard specification).")
    print("--- END SCREENSHOT ---")

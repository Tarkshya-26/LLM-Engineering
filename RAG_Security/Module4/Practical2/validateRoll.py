# validate-and-rollback.py
# A consistency-validation and rollback incident. A refresh job left the vector index drifted
# from its source of truth. The checks, the alert engine, and the maintenance step are written
# for you. You complete two short lines (the delete check and the rollback) and one JSON config
# (a gap in the alert policy). Run it any time: before you finish it shows the built-in checks
# at work; once complete it runs the full incident and writes an incident-record.json.
# Runs fully offline: sqlite3 + json + copy (Python standard library). No model downloads.

import json
import copy
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent
SOURCE_PATH = DATA_DIR / "source-records.json"
CURRENT_PATH = DATA_DIR / "index-current.json"
SNAPSHOT_PATH = DATA_DIR / "index-snapshot.json"
THRESHOLDS_PATH = DATA_DIR / "alert-thresholds.json"
RECOVERED_PATH = DATA_DIR / "recovered-index.json"
INCIDENT_PATH = DATA_DIR / "incident-record.json"

EMBED_MODEL_VERSION = "minilm-v1"   # the embedding model the index is expected to use


def build_source_of_truth(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE source_records (source_id TEXT PRIMARY KEY, access_group TEXT, deleted INTEGER)")
    conn.executemany("INSERT INTO source_records VALUES (?,?,?)",
                     [(r["source_id"], r["access_group"], int(r["deleted"])) for r in rows])
    conn.commit()
    return conn


def load_source(conn):
    rows = conn.execute("SELECT source_id, access_group, deleted FROM source_records").fetchall()
    return [{"source_id": s, "access_group": ag, "deleted": bool(d)} for s, ag, d in rows]


def matching_source_ids(index, keep):
    # Provided helper: the sorted source_ids of ACTIVE vectors for which keep(vector) is True.
    return sorted([v["source_id"] for v in index if v["status"] == "active" and keep(v)])


# ---- Provided consistency checks (read-only; each returns the violating source_ids) ----
def check_count(source_rows, index):
    eligible = sum(1 for r in source_rows if not r["deleted"])
    active = sum(1 for v in index if v["status"] == "active")
    return {"eligible": eligible, "active": active}


def check_missing(source_rows, index):
    active_ids = {v["source_id"] for v in index if v["status"] == "active"}
    return sorted([r["source_id"] for r in source_rows if not r["deleted"] and r["source_id"] not in active_ids])


def check_orphans(source_rows, index):
    known = {r["source_id"] for r in source_rows}
    return matching_source_ids(index, lambda v: v["source_id"] not in known)


def check_metadata(source_rows, index):
    eligible = {r["source_id"]: r for r in source_rows if not r["deleted"]}
    return matching_source_ids(index, lambda v: v["source_id"] in eligible and v["access_group"] != eligible[v["source_id"]]["access_group"])


def check_model_version(source_rows, index):
    return matching_source_ids(index, lambda v: v["embedding_model_version"] != EMBED_MODEL_VERSION)


def check_duplicates(source_rows, index):
    counts = {}
    for v in index:
        if v["status"] == "active":
            counts[v["source_id"]] = counts.get(v["source_id"], 0) + 1
    return sorted([sid for sid, n in counts.items() if n > 1])


# ---- Provided alert engine (reads your policy from alert-thresholds.json) ----
def evaluate_alerts(report, thresholds):
    alerts = []
    for name, policy in thresholds.items():
        if name.startswith("_"):
            continue
        count = len(report.get(name) or [])
        if count > policy["max"]:
            alerts.append((policy["severity"], name, count, policy["max"]))
    order = {"PAGE": 0, "WARN": 1}
    return sorted(alerts, key=lambda a: order.get(a[0], 9))


# ---- Provided maintenance ----
def compact_tombstones(index):
    kept = [v for v in index if v["status"] != "deleted"]
    return kept, len(index) - len(kept)


# ============================================================================
# YOUR TODOs
# ============================================================================
def check_delete_propagation(source_rows, index):
    deleted_ids = {r["source_id"] for r in source_rows if r["deleted"]}
    # TODO (Step 4): an un-propagated delete is an ACTIVE vector whose source was deleted.
    #   Return matching_source_ids(index, keep), where keep(v) is True when v's source_id
    #   is in deleted_ids. (matching_source_ids already filters to active vectors.)
    return matching_source_ids(index, lambda v: v["source_id"] in deleted_ids)



def rollback_to_snapshot(snapshot):
    # TODO (Step 6): return a DEEP COPY of the known-good snapshot, so re-validation cannot
    #   mutate it. Hint: copy.deepcopy(snapshot).
    return copy.deepcopy(snapshot)


# ---- Provided validation runner and report ----
def run_validation(source_rows, index):
    return {
        "count": check_count(source_rows, index),
        "missing_vectors": check_missing(source_rows, index),
        "orphaned_vectors": check_orphans(source_rows, index),
        "metadata_mismatches": check_metadata(source_rows, index),
        "model_version_mismatches": check_model_version(source_rows, index),
        "undeleted_records": check_delete_propagation(source_rows, index),
        "duplicate_vectors": check_duplicates(source_rows, index),
    }


VIOLATION_KEYS = ["missing_vectors", "orphaned_vectors", "metadata_mismatches",
                  "model_version_mismatches", "undeleted_records", "duplicate_vectors"]


def print_consistency_report(title, report):
    c = report["count"]
    match = "MATCH" if c["eligible"] == c["active"] else "MISMATCH"
    print(f"=== CONSISTENCY REPORT: {title} ===")
    print(f"  count_reconciliation     : source eligible={c['eligible']}, index active={c['active']}  {match}")
    total = 0
    pending = False
    for key in VIOLATION_KEYS:
        val = report[key]
        if val is ...:                       # this check is still a TODO
            print(f"  {key:<24} : (not implemented yet)")
            pending = True
        else:
            print(f"  {key:<24} : {len(val)}  -> [{', '.join(val) if val else '-'}]")
            total += len(val)
    print(f"  TOTAL VIOLATIONS: {total}" + ("  (+ pending checks)" if pending else ""))
    return total


if __name__ == "__main__":
    source = load_source(build_source_of_truth(json.loads(SOURCE_PATH.read_text(encoding="utf-8"))))
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))

    report = run_validation(source, current)
    restored = rollback_to_snapshot(snapshot)
    policy_keys = {k for k in thresholds if not k.startswith("_")}
    missing_thresholds = [k for k in VIOLATION_KEYS if k not in policy_keys]

    finished = report["undeleted_records"] is not ... and restored is not ... and not missing_thresholds

    if not finished:
        # Progress / "Show" view: the built-in checks still run so you can watch them work.
        print_consistency_report("current index (after a bad refresh)", report)
        print("\nNot finished yet:")
        if report["undeleted_records"] is ...:
            print("  - Step 4: finish check_delete_propagation in validate-and-rollback.py")
        if missing_thresholds:
            print("  - Step 5: add to alert-thresholds.json -> " + ", ".join(missing_thresholds))
        if restored is ...:
            print("  - Step 6: finish rollback_to_snapshot in validate-and-rollback.py")
        print("\nComplete the open step(s) above, then run again to see the full incident.")
        raise SystemExit(0)

    alerts = evaluate_alerts(report, thresholds)
    print("--- START SCREENSHOT ---")
    print_consistency_report("current index (after a bad refresh)", report)

    print("\n=== ALERTS ===")
    for severity, name, count, mx in alerts:
        note = "  [governance breach]" if severity == "PAGE" else ""
        print(f"  {severity:<4} {name} = {count} (threshold {mx}){note}")

    print("\n=== ROLLBACK ===")
    print(f"  restoring last known-good snapshot ({sum(1 for v in restored if v['status'] == 'active')} active vectors)")
    print()
    total_after = print_consistency_report("after rollback", run_validation(source, restored))

    restored, compacted = compact_tombstones(restored)
    print("\n=== MAINTENANCE RUNBOOK ===")
    print(f"  compaction       : removed {compacted} tombstoned vector(s)")
    print("  rebuild cadence  : full rebuild monthly or on any embedding-model change")
    print("  health review    : weekly count / orphan / duplicate scan")
    print("  audit log review : review delete and access changes each release")

    RECOVERED_PATH.write_text(json.dumps(restored, indent=2), encoding="utf-8")
    incident = {
        "detected_violations": {k: report[k] for k in VIOLATION_KEYS},
        "alerts": [{"severity": s, "check": n, "count": c, "threshold": m} for s, n, c, m in alerts],
        "rollback": {"restored_active": len(restored), "source_consistent": total_after == 0},
        "maintenance": {"tombstones_compacted": compacted},
    }
    INCIDENT_PATH.write_text(json.dumps(incident, indent=2), encoding="utf-8")

    print()
    print("Recovery confirmed: the restored index is consistent with the source of truth."
          if total_after == 0 else f"Rollback incomplete: {total_after} violation(s) remain.")
    print(f"Wrote {RECOVERED_PATH.name} and {INCIDENT_PATH.name} (audit evidence).")
    print("--- END SCREENSHOT ---")

# refresh-pipeline.py
# Build the incremental refresh + delete-propagation pipeline that keeps a vector index
# aligned with its source-of-truth system. The loop, branching, and logging are written for
# you -- you only fill in the single key line inside each branch. Running it prints the index
# state BEFORE and AFTER the refresh so you can see exactly what changed.
# Runs fully offline: sqlite3 + json + hashlib (Python standard library). No model downloads.

import json
import sqlite3
import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).parent
SOURCE_PATH = DATA_DIR / "source-records.json"
INDEX_PATH = DATA_DIR / "vector-index.json"
OUTPUT_PATH = DATA_DIR / "refreshed-index.json"


def embed(text):
    # Toy deterministic embedding: re-embedding changed text yields a different vector.
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round(b / 255, 3) for b in digest[:4]]


def build_source_of_truth(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE source_records (
        source_id TEXT PRIMARY KEY, body TEXT, content_version TEXT, access_group TEXT, deleted INTEGER)""")
    conn.executemany("INSERT INTO source_records VALUES (?,?,?,?,?)",
                     [(r["source_id"], r["body"], r["content_version"], r["access_group"], int(r["deleted"])) for r in rows])
    conn.commit()
    return conn


def load_source(conn):
    cur = conn.execute("SELECT source_id, body, content_version, access_group, deleted FROM source_records")
    return [{"source_id": s, "body": b, "content_version": cv, "access_group": ag, "deleted": bool(d)}
            for s, b, cv, ag, d in cur.fetchall()]


def should_full_rebuild(conditions):
    # TODO (Step 5): return True if ANY of the conditions in the dict is true, else False.
    #   `conditions` is a dict of booleans. Hint: the built-in any() does this in one call.

    return any(conditions.values())


def refresh_index(source_rows, index, log):
    # The loop, the branch conditions, and the logging are all provided. In each branch you
    # write ONLY the single marked line that performs the action.
    by_id = {r["source_id"]: r for r in index}
    source_ids = set()

    for src in source_rows:
        sid = src["source_id"]
        source_ids.add(sid)
        existing = by_id.get(sid)

        if src["deleted"]:
            if existing and existing["status"] == "active":
                # TODO (Step 4): tombstone this vector by setting its "status" to "deleted".
                existing["status"] = "deleted"
                log.append(("DELETE", sid, "source record deleted", "governance + tenant isolation"))
            continue

        if existing is None:
            # TODO (Step 3): a new record must be embedded. Set new_embedding to embed(src["body"]).
            new_embedding = embed(src["body"])
            index.append({"vector_id": "vec-" + sid, "source_id": sid,
                          "content_version": src["content_version"], "access_group": src["access_group"],
                          "embedding": new_embedding, "status": "active"})
            log.append(("INSERT", sid, "new source record", "coverage gap"))

        elif existing["content_version"] != src["content_version"]:
            # TODO (Step 3): the content changed, so refresh the embedding: embed(src["body"]).
            existing["embedding"] = embed(src["body"])
            existing["content_version"] = src["content_version"]
            existing["access_group"] = src["access_group"]
            log.append(("UPDATE", sid, "re-embedded -> " + src["content_version"], "relevance staleness"))

        elif existing["access_group"] != src["access_group"]:
            # TODO (Step 4): metadata-only change. Update access_group to src["access_group"]
            #                WITHOUT re-embedding (the text did not change).
            existing["access_group"] = src["access_group"]
            log.append(("META", sid, "access -> " + src["access_group"], "governance/permission drift"))

        else:
            log.append(("NOOP", sid, "unchanged", "-"))

    # Orphans (vectors whose source record no longer exists) are handled for you.
    for rec in index:
        if rec["source_id"] not in source_ids and rec["status"] == "active":
            rec["status"] = "deleted"
            log.append(("DELETE", rec["source_id"], "orphan (no source record)", "stale/orphaned vector"))


# ---- Runner (provided): prints the BEFORE/AFTER index state ----
def active(index):
    return sorted([r for r in index if r["status"] == "active"], key=lambda r: r["source_id"])


def render_state(title, index):
    lines = [f"=== {title} ==="]
    for r in active(index):
        lines.append(f"  {r['source_id']}  {r['content_version']:<3} access={r['access_group']:<8} emb={r['embedding']}")
    lines.append(f"  ({len(active(index))} active vectors)")
    return "\n".join(lines)


def has_unfilled(index):
    return any(value is ... for record in index for value in record.values())


if __name__ == "__main__":
    source_rows = load_source(build_source_of_truth(json.loads(SOURCE_PATH.read_text(encoding="utf-8"))))
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    before = render_state("INDEX STATE: BEFORE refresh", index)

    log = []
    refresh_index(source_rows, index, log)

    conditions_now = {
        "embedding_model_changed": False,
        "schema_changed": False,
        "index_corrupted": False,
        "drift_exceeds_threshold": False,
    }
    rebuild_now = should_full_rebuild(conditions_now)

    if has_unfilled(index) or rebuild_now is ...:
        print("Not finished yet: fill in the TODO line(s) still marked with `...` and run again.")
        raise SystemExit(0)

    print("--- START SCREENSHOT ---")
    print(before)
    print("\n=== REFRESH LOG ===")
    for action, sid, detail, risk in log:
        print(f"  {action:<7} {sid:<8} {detail:<34} [mitigates: {risk}]")
    print("\n" + render_state("INDEX STATE: AFTER refresh", index))

    print("\n=== DELETE PROPAGATION CHECK ===")
    source_ids = {r["source_id"] for r in source_rows}
    active_ids = {r["source_id"] for r in index if r["status"] == "active"}
    gone = [r["source_id"] for r in source_rows if r["deleted"]]
    gone += sorted({r["source_id"] for r in index if r["source_id"] not in source_ids})
    for sid in gone:
        ok = "no active vector  OK" if sid not in active_ids else "STILL ACTIVE - leak!"
        print(f"  {sid}: {ok}")

    print("\n=== FULL-REBUILD DECISION ===")
    print(f"  current conditions        -> {'full rebuild required' if rebuild_now else 'incremental refresh is sufficient'}")
    scenario = {**conditions_now, "embedding_model_changed": True}
    print(f"  if embedding model changes -> {'full rebuild required' if should_full_rebuild(scenario) else 'incremental refresh is sufficient'}")

    OUTPUT_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH.name} ({len(active(index))} active, {len(index) - len(active(index))} tombstoned).")
    print("--- END SCREENSHOT ---")

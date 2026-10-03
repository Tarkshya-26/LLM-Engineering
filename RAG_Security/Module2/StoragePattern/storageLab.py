# storage-lab.py
# Build a vector storage pattern: a SQLite source-of-truth system plus an in-memory vector
# store, then run a retrieval pipeline (similarity -> relevance/governance/operational filters
# -> resolve source link back to the source of truth) and verify the design worksheet.
# Runs fully offline: sqlite3 (standard library) + Pydantic. No servers, no model downloads.

import json
import math
import re
import sqlite3
from pathlib import Path
from pydantic import BaseModel, ConfigDict, ValidationError

DATA_DIR = Path(__file__).parent
SOURCE_PATH = DATA_DIR / "source-documents.json"
RECORDS_PATH = DATA_DIR / "vector-records.json"
WORKSHEET_PATH = DATA_DIR / "storage-worksheet.md"


# --- Vector record schema (the retrieval-serving copy, with a source link) ---
class VectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vector_id: str
    embedding: list[float]
    source_document_id: str          # the source link back to the source of truth
    chunk_id: str
    source_uri: str
    content_version: str             # the source version this vector was built from
    content_type: str
    region: str
    access_group: str
    sensitivity_label: str
    deleted_at: str | None = None


VALID_FILTER_TYPES = {"relevance", "governance", "operational"}
# First keyword found in a predicate decides its expected type (order matters).
PREDICATE_EXPECTED = [
    ("content_version", "operational"),
    ("content_type", "relevance"),
    ("sensitivity", "governance"),
    ("access_group", "governance"),
    ("deleted_at", "operational"),
    ("region", "relevance"),
]


# --- The source-of-truth system (authoritative records live here, NOT in the vector store) ---
def build_source_of_truth(docs):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE source_documents (
            source_document_id TEXT PRIMARY KEY, title TEXT, body TEXT,
            content_type TEXT, region TEXT, owner TEXT, current_version TEXT)"""
    )
    conn.executemany(
        "INSERT INTO source_documents VALUES (?,?,?,?,?,?,?)",
        [(d["source_document_id"], d["title"], d["body"], d["content_type"],
          d["region"], d["owner"], d["current_version"]) for d in docs],
    )
    conn.commit()
    return conn


def current_versions(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT source_document_id, current_version FROM source_documents")}


def resolve_source_link(record, conn):
    # The lookup path: a retrieved vector -> its authoritative record in the source of truth.
    return conn.execute(
        "SELECT title, current_version FROM source_documents WHERE source_document_id = ?",
        (record["source_document_id"],),
    ).fetchone()


# --- Checks ---
def validate_records(records):
    problems = []
    for rec in records:
        try:
            VectorRecord(**rec)
        except ValidationError as e:
            problems.append(f"Schema: vector {rec.get('vector_id', '?')} has {e.error_count()} error(s)")
    return problems


def check_referential_integrity(records, conn):
    # Every vector must link to a real source document (no orphaned vectors).
    known = {r[0] for r in conn.execute("SELECT source_document_id FROM source_documents")}
    return [f"Orphaned vector {r['vector_id']}: source_document_id '{r['source_document_id']}' is not in the source of truth"
            for r in records if r["source_document_id"] not in known]


# --- Retrieval pipeline filters ---
def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def similarity_search(records, query_vec):
    # Toy 5-dim embeddings: enough to show the plumbing, not real semantic ranking.
    return sorted(records, key=lambda r: cosine(query_vec, r["embedding"]), reverse=True)


def relevance_filter(records, region=None, content_type=None):
    # Relevance: narrow to what the user asked for.
    out = records
    if region:
        out = [r for r in out if r["region"] == region]
    if content_type:
        out = [r for r in out if r["content_type"] == content_type]
    return out


def governance_filter(records, access_group, allowed_sensitivities):
    # Governance (security): only what the caller is permitted to retrieve.
    return [r for r in records
            if r["access_group"] == access_group and r["sensitivity_label"] in allowed_sensitivities]


def operational_filter(records, source_versions):
    # TODO: Operational filters drop records that should not be served right now.
    #   Return only the records that pass BOTH checks:
    #     1. NOT soft-deleted: the record's "deleted_at" is None.
    #     2. NOT stale: the record's "content_version" equals the current version of its
    #        source document, i.e. source_versions[record["source_document_id"]].
    #   source_versions is a dict mapping source_document_id -> current_version.
    ...
    return [r for r in records if r.get("deleted_at") is None and r["content_version"] == source_versions.get(r["source_document_id"])]


def check_operational_filter(records, source_versions):
    try:
        out = operational_filter(records, source_versions)
    except Exception as e:
        return [f"operational_filter raised an error: {e}"]
    if out is None:
        return ["operational_filter is not implemented yet (it returned nothing) - complete the TODO."]
    kept = {r["vector_id"] for r in out}
    problems = []
    for r in records:
        stale = r["content_version"] != source_versions.get(r["source_document_id"])
        deleted = r.get("deleted_at") is not None
        if (stale or deleted) and r["vector_id"] in kept:
            why = "soft-deleted" if deleted else "stale"
            problems.append(f"operational_filter should drop {r['vector_id']} ({why}) but it survived")
        if not stale and not deleted and r["vector_id"] not in kept:
            problems.append(f"operational_filter incorrectly dropped {r['vector_id']} (it is current and live)")
    return problems


# --- Worksheet verification ---
def _sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def _bullets_with_content(text):
    n = 0
    for line in text.splitlines():
        m = re.match(r"^\s*-\s+\*\*.*?:\*\*\s*(.*)$", line)
        if m and len(m.group(1).strip()) >= 3:
            n += 1
    return n


def _numbered_with_content(text):
    n = 0
    for line in text.splitlines():
        m = re.match(r"^\s*\d+\.\s*(.*)$", line)
        if m:
            body = re.sub(r"^\*\*.*?:\*\*", "", m.group(1)).strip()
            if len(body) >= 15:
                n += 1
    return n


def check_worksheet(md):
    problems = []
    secs = _sections(md)

    # Section 1 — three storage-pattern bullets filled
    if _bullets_with_content(secs.get("1", "")) < 3:
        problems.append("Worksheet section 1: fill in all three storage-pattern bullets")

    # Section 2 — every filter predicate classified correctly
    for line in secs.get("2", "").splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip().strip("`").strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        predicate = cells[0].lower()
        expected = next((t for kw, t in PREDICATE_EXPECTED if kw in predicate), None)
        if expected is None:
            continue  # header / separator row
        given = cells[1].lower()
        if given not in VALID_FILTER_TYPES:
            problems.append(f"Worksheet section 2: '{cells[0]}' type '{given or '(blank)'}' is not valid")
        elif given != expected:
            problems.append(f"Worksheet section 2: '{cells[0]}' should be '{expected}', not '{given}'")

    # Section 3 — a real integration boundary note (placeholder replaced)
    has_note = any(
        len(line.strip()) >= 40 and "Replace this line" not in line
        for line in secs.get("3", "").splitlines()
    )
    if not has_note:
        problems.append("Worksheet section 3: write an integration boundary note (replace the placeholder)")

    # Section 4 — at least 3 tradeoff notes with content
    if _numbered_with_content(secs.get("4", "")) < 3:
        problems.append("Worksheet section 4: write at least 3 storage tradeoff notes")

    return problems


def run_pipeline(records, conn):
    query_vec = [0.02, -0.01, 0.03, 0.01, 0.0]   # a fixed example query vector
    ranked = similarity_search(records, query_vec)
    print(f"  1. Vector store candidates:                 {[r['vector_id'] for r in ranked]}")
    rel = relevance_filter(ranked, region="global")
    print(f"  2. Relevance filter (region=global):        {[r['vector_id'] for r in rel]}")
    gov = governance_filter(rel, "support-readonly", {"public"})
    print(f"  3. Governance filter (support-readonly):    {[r['vector_id'] for r in gov]}")
    ops = operational_filter(gov, current_versions(conn))
    print(f"  4. Operational filter (drop stale/deleted): {[r['vector_id'] for r in ops]}")
    print("  5. Resolve source links back to the source of truth:")
    for r in ops:
        title, ver = resolve_source_link(r, conn)
        print(f"       {r['vector_id']} -> {r['source_document_id']}: \"{title}\" (source {ver}, vector {r['content_version']})")


if __name__ == "__main__":
    docs = json.load(open(SOURCE_PATH, encoding="utf-8"))
    records = json.load(open(RECORDS_PATH, encoding="utf-8"))
    worksheet = WORKSHEET_PATH.read_text(encoding="utf-8")
    conn = build_source_of_truth(docs)

    problems = []
    problems += validate_records(records)
    problems += check_referential_integrity(records, conn)
    problems += check_operational_filter(records, current_versions(conn))
    problems += check_worksheet(worksheet)

    if problems:
        print("Not ready yet. Fix the following, then run this script again:\n")
        for p in problems:
            print(f"  [ ] {p}")
        print(f"\n{len(problems)} item(s) remaining.")
    else:
        print("--- START SCREENSHOT ---")
        print("=" * 64)
        print("  ALL CHECKS PASSED - Module 2 storage design is complete")
        print("=" * 64)
        print(f"  Source of truth : {len(docs)} documents in SQLite (authoritative)")
        print(f"  Vector store    : {len(records)} records valid, all source links resolve")
        print(f"  Filters         : relevance + governance + operational all working")
        print(f"  Worksheet       : storage pattern, filter strategy, boundary, tradeoffs complete")
        print("\nRetrieval pipeline (vector store -> filters -> source of truth):")
        run_pipeline(records, conn)
        print("\nNice work. Your retrieval-serving system stays connected to the source of truth.")
        print("--- END SCREENSHOT ---")

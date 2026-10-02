# validate-worksheet.py
# Final check for the Module 2 metadata lab. Validates the schema, audits the metadata
# dictionary, verifies the worksheet is complete AND consistent with the dictionary, then
# runs the relevance vs. governance filtering demo.
# Runs fully offline: pure Python + Pydantic, no model downloads, no network.

import json
import re
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, ConfigDict, ValidationError

DATA_DIR = Path(__file__).parent
RECORDS_PATH = DATA_DIR / "sample-records.json"
DICT_PATH = DATA_DIR / "metadata-dictionary.json"
WORKSHEET_PATH = DATA_DIR / "metadata-worksheet.md"


# --- The revised vector schema (carried over from the Module 1 schema lab) ---
class VectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Core vector
    vector_id: str
    embedding: list[float]
    embedding_model: str
    text: str
    # Source traceability
    source_document_id: str
    chunk_id: str
    source_uri: str
    content_version: str
    # Filtering metadata
    content_type: str
    topic: str
    product: str | None = None
    region: str
    language: str
    # Governance & access control
    tenant_id: str
    access_group: str
    sensitivity_label: str
    source_owner: str
    # Evaluation & lifecycle
    created_at: datetime
    last_validated_at: datetime | None = None
    deleted_at: datetime | None = None
    eval_split: str | None = None


VALID_CLASSES = {"stored-only", "filterable", "displayable", "audit-oriented"}
VALID_FILTER_ROLES = {"none", "relevance", "governance"}
GOVERNANCE_FIELDS = ["tenant_id", "access_group", "sensitivity_label", "source_owner"]
SOURCE_DOCS = ["doc-003", "doc-004", "doc-006", "doc-008", "doc-011"]


def validate_records(records):
    # Confirm the sample data still conforms to the schema.
    ok, problems = 0, []
    for rec in records:
        try:
            VectorRecord(**rec)
            ok += 1
        except ValidationError as e:
            problems.append(f"Schema: record {rec.get('vector_id', '?')} has {e.error_count()} error(s)")
    return ok, problems


def audit_dictionary(dictionary):
    # Every schema field must be documented with a valid classification, and any field
    # used as a filter must be classified "filterable".
    schema_fields = set(VectorRecord.model_fields)
    documented = {e["field"] for e in dictionary}
    problems = []
    for f in sorted(schema_fields - documented):
        problems.append(f"Dictionary: '{f}' is in the schema but missing from the dictionary")
    for f in sorted(documented - schema_fields):
        problems.append(f"Dictionary: '{f}' is in the dictionary but not in the schema")
    for e in dictionary:
        c, fr = e["classification"], e.get("filter_role")
        if c not in VALID_CLASSES:
            problems.append(f"Dictionary: '{e['field']}' has invalid classification '{c}'")
        if fr not in VALID_FILTER_ROLES:
            problems.append(f"Dictionary: '{e['field']}' has invalid filter_role '{fr}'")
        elif fr in {"relevance", "governance"} and c != "filterable":
            problems.append(f"Dictionary: '{e['field']}' filter_role '{fr}' requires classification 'filterable'")
    return problems


def _rows(md):
    rows = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def _clean(c):
    return c.replace("`", "").strip()


def check_worksheet(md, dictionary):
    # Verify the student's worksheet is filled in and agrees with the dictionary.
    problems = []
    by_field = {}
    for cells in _rows(md):
        if cells:
            by_field.setdefault(_clean(cells[0]).lower(), cells)
    dict_by_field = {e["field"]: e for e in dictionary}

    # Section 1 — governance rows filled and consistent with the dictionary
    for f in GOVERNANCE_FIELDS:
        cells = by_field.get(f)
        if not cells or len(cells) < 5:
            problems.append(f"Worksheet section 1: row for '{f}' is missing or incomplete")
            continue
        classification, filter_role = _clean(cells[2]).lower(), _clean(cells[3]).lower()
        d = dict_by_field.get(f)
        if classification not in VALID_CLASSES:
            problems.append(f"Worksheet section 1: '{f}' classification '{classification or '(blank)'}' is not valid")
        elif d and classification != d["classification"]:
            problems.append(f"Worksheet section 1: '{f}' classification does not match metadata-dictionary.json")
        if filter_role not in VALID_FILTER_ROLES:
            problems.append(f"Worksheet section 1: '{f}' filter role '{filter_role or '(blank)'}' is not valid")
        elif d and filter_role != d["filter_role"]:
            problems.append(f"Worksheet section 1: '{f}' filter role does not match metadata-dictionary.json")

    # Section 2 — source-link rows filled
    for doc in SOURCE_DOCS:
        cells = by_field.get(doc)
        if not cells or len(cells) < 4:
            problems.append(f"Worksheet section 2: row for '{doc}' is missing or incomplete")
            continue
        if not _clean(cells[1]):
            problems.append(f"Worksheet section 2: '{doc}' is missing the authoritative system")
        if not _clean(cells[2]):
            problems.append(f"Worksheet section 2: '{doc}' is missing the lookup path")

    # Section 3 — at least 3 tradeoff notes with real content
    completed, in_section = 0, False
    for line in md.splitlines():
        if "Storage Tradeoff" in line:
            in_section = True
            continue
        if in_section:
            m = re.match(r"^\s*\d+\.\s*(.*)$", line)
            if m:
                body = re.sub(r"^\*\*.*?:\*\*", "", m.group(1)).strip()
                if len(body) >= 15:
                    completed += 1
    if completed < 3:
        problems.append(f"Worksheet section 3: found {completed} completed tradeoff note(s); at least 3 are required")

    return problems


def relevance_filter(records, region=None, content_type=None):
    out = records
    if region:
        out = [r for r in out if r["region"] == region]
    if content_type:
        out = [r for r in out if r["content_type"] == content_type]
    return out


def governance_filter(records, access_group, allowed_sensitivities):
    # SECURITY filter: only return records this caller is permitted to retrieve.
    return [
        r for r in records
        if r["access_group"] == access_group
        and r["sensitivity_label"] in allowed_sensitivities
    ]


def _ids(rs):
    return [r["vector_id"] for r in rs]


def demo_filtering(records):
    print("\nFiltering demo:")
    print(f"  Candidates (top matches by similarity): {_ids(records)}")
    rel = relevance_filter(records, region="global")
    print(f"  Relevance filter (region=global)            -> kept {_ids(rel)}  dropped {[r['vector_id'] for r in records if r not in rel]}")
    gov = governance_filter(records, "support-readonly", {"public"})
    print(f"  Governance filter (support-readonly/public) -> kept {_ids(gov)}  dropped {[r['vector_id'] for r in records if r not in gov]}")
    combined = governance_filter(rel, "support-readonly", {"public"})
    print(f"  Combined (relevance THEN governance)        -> {_ids(combined)}")
    print("  Note: only the GOVERNANCE filter reliably hides internal/confidential records.")


if __name__ == "__main__":
    records = json.load(open(RECORDS_PATH, encoding="utf-8"))
    dictionary = json.load(open(DICT_PATH, encoding="utf-8"))
    worksheet = WORKSHEET_PATH.read_text(encoding="utf-8")

    rec_ok, problems = validate_records(records)
    problems += audit_dictionary(dictionary)
    problems += check_worksheet(worksheet, dictionary)

    if problems:
        print("Not ready yet. Fix the following, then run this script again:\n")
        for p in problems:
            print(f"  [ ] {p}")
        print(f"\n{len(problems)} item(s) remaining.")
    else:
        gov = [e["field"] for e in dictionary if e["filter_role"] == "governance"]
        print("--- START SCREENSHOT ---")
        print("=" * 64)
        print("  ALL CHECKS PASSED - Module 2 metadata artifact is complete")
        print("=" * 64)
        print(f"  Schema      : {rec_ok}/{len(records)} sample records valid")
        print(f"  Dictionary  : {len(dictionary)}/{len(dictionary)} fields classified")
        print(f"  Governance  : security filters = {gov}")
        print(f"  Worksheet   : dictionary, source-link mapping, and tradeoffs complete")
        demo_filtering(records)
        print("\nNice work. Your schema, dictionary, and worksheet are consistent and complete.")
        print("--- END SCREENSHOT ---")

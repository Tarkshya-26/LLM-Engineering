# schema-lab.py
# Draft and validate a metadata-rich vector schema for a retrieval system.
# Runs fully offline: pure Python + Pydantic, no model downloads, no network.

import json
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, ConfigDict, ValidationError

DATA_DIR = Path(__file__).parent
RECORDS_PATH = DATA_DIR / "sample-records.json"


# --- The draft vector schema ---
# extra="forbid" makes validation FAIL if a record carries a field the schema does not
# declare, so the schema is forced to capture every field your records actually need.
class VectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Core vector fields
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
    # TODO: Declare at least 4 governance/access-control fields that the sample records
    #       carry. Until you do, extra="forbid" rejects every record. Check the record
    #       keys (or the Solution Hint) for the exact field names and types.
    ...
    
    tenant_id : str
    access_group : str
    sensitivity_label : str
    source_owner : str

    # Evaluation & lifecycle
    created_at: datetime
    last_validated_at: datetime | None = None
    deleted_at: datetime | None = None
    eval_split: str | None = None


# Field groups the schema is expected to cover (used by the coverage report below).
GOVERNANCE_FIELDS = {"tenant_id", "access_group", "sensitivity_label", "source_owner"}
SOURCE_FIELDS = {"source_document_id", "chunk_id", "source_uri", "content_version"}
EVAL_FIELDS = {"created_at", "last_validated_at", "deleted_at", "eval_split"}


def validate_records(records):
    # Try to build a VectorRecord for each row; report any that the schema rejects.
    ok = 0
    for rec in records:
        try:
            VectorRecord(**rec)
            ok += 1
        except ValidationError as e:
            print(f"INVALID  {rec.get('vector_id', '?')}: {e.error_count()} error(s)")
            for err in e.errors():
                field = ".".join(str(p) for p in err["loc"])
                print(f"    - {field}: {err['msg']}")
    return ok, len(records) - ok


def coverage_report():
    # Check that the schema covers each required field group for a governable system.
    fields = set(VectorRecord.model_fields)
    gov = sorted(GOVERNANCE_FIELDS & fields)
    print("\nSchema coverage:")
    print(f"  Source traceability : {len(SOURCE_FIELDS & fields)}/{len(SOURCE_FIELDS)} fields")
    print(f"  Evaluation/lifecycle: {len(EVAL_FIELDS & fields)}/{len(EVAL_FIELDS)} fields")
    print(f"  Governance/access   : {len(gov)} field(s) -> {gov}")
    status = "PASS" if len(gov) >= 4 else "FAIL"
    print(f"  Governance requirement (>= 4 fields): {status}")


if __name__ == "__main__":
    records = json.load(open(RECORDS_PATH, encoding="utf-8"))
    print("--- START SCREENSHOT ---")
    ok, bad = validate_records(records)
    print(f"\nValidated {ok} record(s) OK, {bad} invalid.")
    coverage_report()
    print("--- END SCREENSHOT ---")

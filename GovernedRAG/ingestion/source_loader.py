from pathlib import Path
from hashlib import sha256
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


SOURCE_ROOT = Path(
    "/Users/tarkshya/Work/LLM Engineering/GovernedRAG/data/source"
)

DOCUMENTS_ROOT = SOURCE_ROOT / "documents"


class AccessRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: Literal[
        "self",
        "manager_of",
        "account_team_of",
    ]

    subject: str


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Identity
    schema_version: str
    document_id: str
    version: int
    document_version_id: str

    # Content
    title: str
    document_type: str

    # Source / lineage
    source_system: str
    source_uri: str
    source_record_ids: list[str]

    # Entities
    subject_entities: list[str]

    # Governance
    tenant_id: str
    owner_department_id: str
    source_owner_id: str
    sensitivity_label: str
    access_groups: list[str]
    access_relations: list[AccessRelation]
    access_principals: list[str]

    # Location / lifecycle
    region: str
    language: str
    status: str
    supersedes: str | None

    # Provenance
    content_origin: str
    content_sha256: str
    retention_class: str

    # Dates
    created_at: str
    updated_at: str
    valid_from: str
    valid_to: str | None

    # Actual Markdown body
    body: str


def parse_document(path: Path) -> SourceDocument:
    """
    Read one Markdown source document, parse its YAML front matter,
    extract the Markdown body, and verify its content hash.
    """

    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        raise ValueError(f"Missing YAML front matter: {path}")

    parts = text.split("---", 2)

    if len(parts) != 3:
        raise ValueError(f"Invalid front matter structure: {path}")

    _, front_matter, body = parts

    metadata = yaml.safe_load(front_matter)

    if not isinstance(metadata, dict):
        raise ValueError(f"Front matter is not a mapping: {path}")

    body = body.lstrip("\n")

    actual_hash = sha256(body.encode("utf-8")).hexdigest()

    expected_hash = metadata["content_sha256"]

    if actual_hash != expected_hash:
        raise ValueError(
            f"Content hash mismatch: {path}\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )

    return SourceDocument(
        **metadata,
        body=body,
    )


def fetch_documents() -> list[SourceDocument]:
    """
    Load every Markdown source document.

    Includes both v1 and v2 documents.
    Ignores .gitkeep and other non-Markdown files.
    """

    documents = []

    for path in DOCUMENTS_ROOT.rglob("*.md"):
        documents.append(parse_document(path))

    print(f"Loaded {len(documents)} documents")

    return documents
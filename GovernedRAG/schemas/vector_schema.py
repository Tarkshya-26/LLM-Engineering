from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AccessRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: Literal[
        "self",
        "manager_of",
        "account_team_of",
    ]

    subject: str


class VectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Identity
    chunk_id: str
    document_id: str
    document_version_id: str

    # Content
    title: str
    text: str
    content_origin: Literal[
        "internal",
        "customer_submitted",
        "public_source",
    ]

    # Source / lineage
    source_uri: str
    source_system: Literal[
        "hris",
        "crm",
        "clm",
        "erp",
        "wiki",
        "grc",
        "itsm",
        "pm",
        "support",
        "public_web",
    ]
    document_type: str
    source_content_sha256: str

    # Entity relationships
    subject_entities: list[str]

    # Governance
    tenant_id: str
    sensitivity_label: Literal[
        "public",
        "internal",
        "confidential",
        "restricted",
    ]
    access_groups: list[str]
    access_relations: list[AccessRelation]
    access_principals: list[str]

    # Lifecycle
    region: str
    status: Literal[
        "current",
        "superseded",
        "archived",
        "deleted",
    ]
    valid_from: str
    valid_to: str | None

    # Chunk / embedding
    chunk_index: int
    chunk_hash: str
    embedding_model: str
    embedding_version: str

    # Ingestion
    ingested_at: datetime
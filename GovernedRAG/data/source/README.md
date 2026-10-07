# Governed RAG Source Data

This directory contains the synthetic enterprise source-of-truth data
used by the Governed RAG system.

The source data is authoritative.

Vector databases, embeddings, chunks, and retrieval indexes are derived
artifacts and must be reproducible from this source data.

Do not manually modify generated vector data.

---

## Insurellm source world: schemas and contracts (v1.0)

The synthetic world is a fictional Insurellm enterprise. Nothing in this directory is a vector, a chunk or an embedding; those are created later by `ingestion/` (see section 2C).

Status: **complete source dataset.** 372 document versions (350 documents) are written with approved front matter; every check passes (`datagen.check_world`: 57 of 57). Dataset digest is in `_build/dataset_manifest.json`.

#### Pipeline (run from the GovernedRAG root)

```bash
../.venv/bin/python -m datagen.seed_kb        # KB -> seed/ (facts with verbatim quotes, stable IDs, conflicts)
../.venv/bin/python -m datagen.check_seed     # proves every seeded fact against the KB text
../.venv/bin/python -m datagen.build_world    # T0 world + 4 CDC batches + document plan + ground truth
../.venv/bin/python -m datagen.check_world    # independent checker: schemas, seed preservation, replay, invariants, authz
../.venv/bin/python -m datagen.report         # counts and scenario spot checks
../.venv/bin/python -m datagen.manifest       # sha256 of every file + dataset digest -> _build/dataset_manifest.json
```

- `seed/` is the provenance layer: `kb_seed.json` (every KB value with its quote), `id_registry.json` (stable IDs, never regenerated), `kb_file_hashes.json` (proves the KB was not modified), `kb_conflicts.json` (contradictions inside the KB and how they are handled).
- `datagen/world_config.py` and `datagen/content_config.py` list every generated person, customer, amendment, project, policy, incident, ticket and persona explicitly.
- T0 HR contains exactly the 32 KB employees. Contract signatories Jennifer Rodriguez, Sarah Chen and Michael Torres exist only as printed on contracts, never as identities.

Check the schemas:

```bash
python data/source/tools/check_schemas.py   # from the GovernedRAG root
```

It validates every schema (JSON Schema draft 2020-12) and every embedded example, confirms that ingestion-only fields are rejected in source data, runs 20 contract rules that must reject bad data, validates `access_control/policies.yaml` against its schema plus its consistency and security invariants, and proves each invariant fires on 17 deliberately broken policy variants. The examples inside each schema are illustrative; the generated data may use different IDs and people.

---

### 1. Directory structure

```
data/source/
├── README.md
├── schema/                                   # the contracts (this release)
│   ├── common.schema.json                    # ID patterns, enums, money, envelope, reserved field names
│   ├── entities/                             # one schema per entity type (17)
│   │   ├── location.schema.json        department.schema.json      team.schema.json
│   │   ├── employee.schema.json        compensation.schema.json    performance_review.schema.json
│   │   ├── product.schema.json         product_tier.schema.json    customer.schema.json
│   │   ├── contract.schema.json        contract_version.schema.json
│   │   ├── project.schema.json         policy.schema.json          policy_version.schema.json
│   │   └── incident.schema.json        support_ticket.schema.json  financial_record.schema.json
│   ├── documents/front_matter.schema.json
│   ├── relationships/edge.schema.json
│   ├── access_control/
│   │   ├── tenant.schema.json          principal.schema.json
│   │   ├── group.schema.json           membership.schema.json      policy_set.schema.json
│   ├── cdc/
│   │   ├── manifest.schema.json        event.schema.json
│   └── ground_truth/
│       ├── persona.schema.json         access_decision.schema.json
│       ├── versioned_fact.schema.json  checkpoint.schema.json      document_annotation.schema.json
│
├── entities/                                 # T0 state of every system of record (JSONL)
│   ├── locations.jsonl  departments.jsonl  teams.jsonl
│   ├── employees.jsonl  compensation.jsonl  performance_reviews.jsonl
│   ├── products.jsonl  product_tiers.jsonl  customers.jsonl
│   ├── contracts.jsonl  contract_versions.jsonl
│   ├── projects.jsonl  policies.jsonl  policy_versions.jsonl
│   └── incidents.jsonl  support_tickets.jsonl  financial_records.jsonl
├── documents/                                # what the RAG ingests: Markdown + YAML front matter
│   └── <source_system>/<document_id>/v<N>.md # e.g. documents/clm/DOC-CLM-0031/v2.md
│       hris/ crm/ clm/ erp/ wiki/ grc/ itsm/ pm/ support/ public_web/
├── relationships/edges.jsonl                 # typed, time-bounded, derived from foreign keys; full history (T0 + every batch)
├── access_control/
│   ├── tenants.jsonl  principals.jsonl  groups.jsonl  memberships.jsonl
│   └── policies.yaml                         # the authorization policy set (data, not code)
├── cdc/
│   ├── manifest.json                         # T0 time + batch list
│   └── events.jsonl                          # every change after T0, in delivery order
├── ground_truth/                             # answers for evaluation; never ingested
│   ├── personas.jsonl  access_matrix.jsonl  versioned_facts.jsonl
│   └── checkpoints.jsonl  document_annotations.jsonl
├── seed/                                     # KB provenance layer (see Pipeline)
├── _build/document_plan.jsonl                # every document version: front matter + body recipe (verbatim, patch, generated)
├── _build/dataset_manifest.json              # sha256 per file and the dataset digest
└── tools/
    └── check_schemas.py
```

| Data file | Schema |
|---|---|
| `entities/<plural>.jsonl` | `schema/entities/<singular>.schema.json` |
| `documents/**/v<N>.md` (front matter) | `schema/documents/front_matter.schema.json` |
| `relationships/edges.jsonl` | `schema/relationships/edge.schema.json` |
| `access_control/tenants.jsonl` | `schema/access_control/tenant.schema.json` |
| `access_control/principals.jsonl` | `schema/access_control/principal.schema.json` |
| `access_control/groups.jsonl` | `schema/access_control/group.schema.json` |
| `access_control/memberships.jsonl` | `schema/access_control/membership.schema.json` |
| `access_control/policies.yaml` | `schema/access_control/policy_set.schema.json` |
| `cdc/manifest.json` | `schema/cdc/manifest.schema.json` |
| `cdc/events.jsonl` | `schema/cdc/event.schema.json` |
| `ground_truth/personas.jsonl` | `schema/ground_truth/persona.schema.json` |
| `ground_truth/access_matrix.jsonl` | `schema/ground_truth/access_decision.schema.json` |
| `ground_truth/versioned_facts.jsonl` | `schema/ground_truth/versioned_fact.schema.json` |
| `ground_truth/checkpoints.jsonl` | `schema/ground_truth/checkpoint.schema.json` |
| `ground_truth/document_annotations.jsonl` | `schema/ground_truth/document_annotation.schema.json` |

Generated size: 372 document versions (280 at T0), 32 employees at T0 growing to 50, 35 customers, 46 contract versions, 16 personas, 26,224 ground-truth access decisions. Run `datagen.report` for the full breakdown.

---

### 2. Field ownership: source vs ingestion

The source system is the source of truth. The vector store is derived. So every field belongs to exactly one side.

#### A. Source-system fields (in this dataset)

Everything defined by these schemas. Highlights from the document front matter:

| Field | Meaning |
|---|---|
| `document_id`, `version`, `document_version_id` | Stable identity; a new version never changes `document_id` |
| `document_type`, `source_system`, `source_uri`, `title` | What it is and where it lives |
| `source_record_ids`, `subject_entities` | Lineage to entity rows, and every entity it mentions |
| `tenant_id`, `owner_department_id`, `source_owner_id` | Ownership |
| `sensitivity_label`, `access_groups`, `access_relations`, `access_principals` | Access metadata (inputs to authorization) |
| `region`, `language`, `retention_class`, `content_origin` | Filtering and handling |
| `status`, `supersedes`, `valid_from`, `valid_to` | Lifecycle and versioning |
| `content_sha256` | Source etag of the body (ingestion verifies it) |
| `created_at`, `updated_at` | Source timestamps |

#### B. Source fields ingestion should copy onto every chunk

Copy these unchanged, so filtering, authorization and lineage work on chunks without a lookup: `document_id`, `version`, `document_version_id`, `document_type`, `source_system`, `source_uri`, `title`, `tenant_id`, `owner_department_id`, `source_owner_id`, `sensitivity_label`, `access_groups`, `access_relations`, `access_principals`, `region`, `language`, `status`, `valid_from`, `valid_to`, `subject_entities`, `content_origin`, plus `content_sha256` and `updated_at` (suggested names on the vector: `source_content_sha256`, `source_updated_at`).

How lists are stored on the vector (some vector stores only accept scalar metadata) is a Phase 4 decision.

#### C. Ingestion-created fields (reserved; never in source data)

Every source schema rejects these names (`common.schema.json#/$defs/reserved_ingestion_field`).

| Field | Created by | Meaning |
|---|---|---|
| `vector_id` | ingestion | Primary key in the vector store |
| `chunk_id` | chunker | Stable id, e.g. `document_version_id` + chunk index |
| `chunk_index`, `chunk_count`, `parent_chunk_id` | chunker | Position within the document |
| `chunk_hash` | chunker | Hash of the chunk text, for idempotent upserts |
| `char_start`, `char_end`, `token_count` | chunker | Span and size |
| `embedding`, `embedding_model`, `embedding_version`, `embedding_dim` | embedder | The vector and how it was made |
| `ingested_at`, `ingestion_run_id`, `pipeline_version` | pipeline | When and by which run |
| `index_name`, `collection_name` | pipeline | Where it was written (supports shadow rebuilds) |
| `acl_principal_hashes` | ACL resolver | Precomputed principals, if you choose that design; derived from B plus memberships |

Mapping from your notes' "minimum schema": `tenant_id`, `source_system`, `title`, `created_at`, `updated_at` are A. `source_doc_id` is `document_id`, `source_version` is `version`/`document_version_id`, `source_url` is `source_uri`, `owner_team` is `owner_department_id`, `classification` is `sensitivity_label` (all A, copied per B). `chunk_id`, `chunk_hash`, `ingested_at`, `embedding_model`, `embedding_version`, `acl_principal_hashes` are C.

---

### 3. IDs

| Prefix | Example | Notes |
|---|---|---|
| `T-` | `T-INSURELLM`, `T-CUST-012` | Customer tenant number equals its customer number |
| `LOC-` `DEPT-` `TEAM-` | `LOC-01` | |
| `EMP-` `COMP-` `PRV-` | `EMP-021`, `COMP-0147`, `PRV-0088` | |
| `PROD-` `TIER-` | `PROD-002`, `TIER-005` | |
| `CUST-` `CON-` `CON-nnn@vN` | `CON-031@v2` | `contract_number` keeps the KB's business key (`CL-2025-0234`) |
| `PROJ-` `POL-` `POL-nnn@vN` `INC-` `TCK-` `FIN-` | | |
| `DOC-<SYS>-nnnn` and `@vN` | `DOC-CLM-0031@v2` | `<SYS>`: HRIS CRM CLM ERP WIKI GRC ITSM PM SUP WEB |
| `P-EMP-` `P-CUS-` `P-SVC-` | `P-EMP-021` | Principals; employees wrap their `EMP` id |
| `GRP-` `MEM-` `EDGE-` `EVT-` `BATCH-` | `GRP-hr-comp` | |
| `PERS-` `DEC-` `FACT-` `CP-` `ANN-` `PSET-` | | Ground truth and policy |

---

### 4. Time model

- Seeded rows and documents whose source date is unknown carry the assembly time `2025-06-30T00:00:00Z`; versioned facts for them start at the T0 date (observed-from, not true start).
- Document body modes: `kb_verbatim` (line ranges of one KB file, T0 only), `kb_patch` (a later version = previous body with exact-phrase replacements), `generated` (written in the document phase from the entity facts listed in the plan).

- **T0** (`cdc/manifest.json → t0_snapshot_at`): `entities/`, `access_control/` and `relationships/` hold the state at T0.
- **T0 document load**: every `documents/**/v<N>.md` whose front matter `updated_at <= t0_snapshot_at`.
- **After T0**: every change is an event in `cdc/events.jsonl`. New entity rows, new memberships and new document versions appear only as CDC `insert` events. Status changes of an existing version (current → superseded, archived, deleted) are CDC `update`/`delete` events on that `document_version`.
- **Files are immutable**: a document file's front matter is the version as first written. Later status changes live in CDC only, as in a real system.
- **Ordering**: file order of `events.jsonl` = delivery order. `sequence` = commit order. Duplicates and one out-of-order event are deliberate and listed only in `ground_truth/checkpoints.jsonl`.
- **Original 150 tests**: run at T0 with the `baseline_eval` persona.

---

### 5. Authorization contract (summary)

The full, reviewed rules are in `access_control/policies.yaml`. Default deny. Steps run in order: `global_deny → tenant → label → grant`. A deny at any step is final; no later grant, role or title can override it, and there is no break-glass path in v1. A grant that fails a `grant_validity_rules` check (expired membership, expired edge, group ceiling, relation not allowed for the label) is ignored rather than denying.

| Label | Who may pass the label step | Grant needed |
|---|---|---|
| public | employees, customer users, service accounts | no |
| internal | employees, service accounts | no |
| confidential | employees, customer users, service accounts | yes: group, relation (`self`, `manager_of`, `account_team_of`), named principal, or tenant membership |
| restricted | employees, service accounts | yes: group, named principal, or `self` only |

- **Tenant step:** customer users see public documents plus their own tenant only; another customer's tenant is always denied. Employees need a grant to read a customer tenant.
- **Relations:** relation grants are evaluated against `relationships/edges.jsonl` as of the decision time.
- **Groups:** the complete catalog (16 groups, no nesting, contractors excluded from all) is in `policies.yaml`; `groups.jsonl` mirrors it.
- **Not an authorization rule:** `lifecycle_visibility` in `policies.yaml` says which statuses normal retrieval returns. Superseded and archived versions are history-only; deleted versions are never returned.

---

### 6. Invariants the generator must satisfy

These cross-record rules can't be expressed in JSON Schema. The dataset validator (written with the generator) enforces them:

1. `document_version_id == document_id + "@v" + version`, and the file path is `documents/<source_system>/<document_id>/v<version>.md`.
2. `content_sha256` equals SHA-256 of the body (UTF-8, LF).
3. Every referenced ID exists at the time it is referenced (foreign-key integrity across files and batches).
4. `subject_entities` ⊇ `source_record_ids`. `supersedes` points to an earlier version of the same `document_id`.
5. At every checkpoint, each `document_id` has at most one `current` version; each contract and policy has exactly one current version, matching the header's `current_version`.
6. `customer.portal_tenant_id` number equals the customer number; a support ticket's `tenant_id` equals its customer's portal tenant; account manager and CSM are in `account_team_ids`.
7. One open compensation row per employee; pay periods do not overlap.
8. One CEO (`manager_id = null`); the manager chain has no cycles.
9. Each employee has exactly one `P-EMP` principal; termination disables it on the termination date.
10. No document is looser than its `document_type_defaults`: its label is never lower, and at the same label it never adds a group, relation or principal grant (a higher label may carry any grants). No document grants a group whose `max_label` is below the document's label.
11. Every edge is derivable from the foreign key named in `derived_from`, with validity windows that match CDC history.
12. Every number, date and ID in a document body appears in one of its `source_record_ids` rows (fact check).
13. In YAML front matter all dates and timestamps are quoted strings (PyYAML would otherwise turn them into date objects).
14. All people and organisations are fictional; every email and URL uses the reserved `.example` domain.
15. Facts that already exist in the original KB (`../Week5_RAG/knowledge-base/`, relative to the GovernedRAG root) keep their values at T0, so the original 150 tests remain answerable.
16. `access_control/groups.jsonl` contains exactly the groups in `policies.yaml`, and every membership follows that group's `membership_rule`.
17. The baseline evaluator (`P-SVC-001`) can read every T0 document that holds a fact from the original KB; if not, the document placement or the binding is fixed and re-reviewed, never widened silently.
18. After an erasure, no vector, fact evidence or ground-truth row created after the erasure checkpoint refers to the erased documents.

---

### 7. Open design review items

- **Finance access to contract content (least privilege).** `contract`, `contract_amendment` and `contract_renewal` grant `GRP-finance`, so a Finance analyst reads every contract version in full (seen when Emily Carter moves from Sales to Finance in BATCH-03: 8 contracts via account teams before, 35 via Finance after). Under review: whether Finance needs the full text or only commercial fields. Policy unchanged until that review.
- **Headcount stored as a financial line item.** Board packs keep `headcount` in `line_items`, which forces a currency on a count. Harmless for retrieval; a dedicated metrics field would be cleaner.
- **Sanitised postmortems.** Only the BATCH-04 incident has an internal postmortem; the five T0 incidents have restricted reports only.


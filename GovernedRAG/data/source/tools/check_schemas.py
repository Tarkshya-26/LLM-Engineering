"""Self-check for the source-world schemas and the policy set.

1. Every schema is valid JSON Schema (draft 2020-12).
2. Every embedded example validates against its own schema.
3. Reserved ingestion fields are rejected by entity rows and document front matter.
4. Contract rules reject bad data (each case mutates a valid example).
5. access_control/policies.yaml validates against its schema and passes the
   policy consistency and security invariants below, and each invariant is
   proven to fire by a deliberately broken copy of the policy.

Run from the GovernedRAG root:  python data/source/tools/check_schemas.py
"""

import copy
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SOURCE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = SOURCE_DIR / "schema"
POLICY_FILE = SOURCE_DIR / "access_control" / "policies.yaml"
POLICY_SCHEMA = "access_control/policy_set.schema.json"
FM = "documents/front_matter.schema.json"

NEGATIVE_CASES = [
    (FM, "confidential document with no grants",
     lambda d: d.update(access_groups=[], access_relations=[], access_principals=[])),
    (FM, "public document that carries grants",
     lambda d: d.update(sensitivity_label="public")),
    (FM, "hris source with a CLM document id",
     lambda d: d.update(source_system="hris", document_type="employee_profile")),
    (FM, "customer-tenant document from the wiki",
     lambda d: d.update(tenant_id="T-CUST-012")),
    (FM, "version 2 that supersedes nothing",
     lambda d: d.update(supersedes=None)),
    (FM, "customer_submitted content outside support",
     lambda d: d.update(content_origin="customer_submitted")),
    (FM, "account_team_of pointing at an employee",
     lambda d: d.update(access_relations=[{"relation": "account_team_of", "subject": "EMP-001"}])),
    ("entities/employee.schema.json", "terminated employee without a termination date",
     lambda d: d.update(employment_status="terminated")),
    ("entities/compensation.schema.json", "compensation row not labelled restricted",
     lambda d: d.update(sensitivity_label="confidential")),
    ("entities/contract_version.schema.json", "v2 labelled as the original",
     lambda d: d.update(version=2)),
    ("entities/customer.schema.json", "portal customer without a portal tenant",
     lambda d: d.update(portal_tenant_id=None)),
    ("entities/support_ticket.schema.json", "ticket stored in the internal tenant",
     lambda d: d.update(tenant_id="T-INSURELLM")),
    ("relationships/edge.schema.json", "tech_lead_of from a customer",
     lambda d: d.update(from_type="customer", from_id="CUST-001")),
    ("access_control/principal.schema.json", "customer user homed in the internal tenant",
     lambda d: d.update(principal_id="P-CUS-0001", principal_type="customer_user", home_tenant_id="T-INSURELLM",
                        employee_id=None, customer_id="CUST-012", customer_role="portal_member")),
    ("access_control/principal.schema.json", "disabled principal without disabled_at",
     lambda d: d.update(principal_status="disabled")),
    ("entities/contract_version.schema.json", "generated contract version without a monthly fee",
     lambda d: d.update(origin="generated", monthly_fee=None)),
    ("entities/compensation.schema.json", "generated pay row without an approver",
     lambda d: d.update(origin="generated", approved_by=None)),
    ("entities/customer.schema.json", "generated customer without a region",
     lambda d: d.update(origin="generated", region=None)),
    ("entities/product_tier.schema.json", "custom-priced tier that still has a list price",
     lambda d: d.update(pricing_model="custom")),
    ("ground_truth/access_decision.schema.json", "deny that still names a matched grant",
     lambda d: d.update(decision="deny", reason_code="deny_no_matching_grant")),
    ("cdc/event.schema.json", "insert event with a before image",
     lambda d: d.update(operation="insert")),
    ("cdc/event.schema.json", "membership event whose after image is not a membership",
     lambda d: d["after"].pop("group_id")),
    ("ground_truth/checkpoint.schema.json", "deleted version that must stay indexed",
     lambda d: d["document_states"][0].update(status="deleted")),
    ("ground_truth/document_annotation.schema.json", "prompt injection outside a support ticket",
     lambda d: d.update(document_version_id="DOC-WIKI-0001@v1")),
]


def _tenant_rule(policy, principal_type, document_tenant):
    return next(r for r in policy["tenant_rules"]
                if r["principal_type"] == principal_type and r["document_tenant"] == document_tenant)


def _label_rule(policy, label):
    return next(r for r in policy["label_rules"] if r["label"] == label)


def _default(policy, document_type):
    return next(d for d in policy["document_type_defaults"] if d["document_type"] == document_type)


# Each case breaks one thing in a copy of policies.yaml; schema + invariants must catch it
POLICY_NEGATIVE_CASES = [
    ("default decision of allow", lambda p: p.update(default_decision="allow")),
    ("a tenant rule missing", lambda p: p["tenant_rules"].pop()),
    ("customer users reading other tenants", lambda p: _tenant_rule(p, "customer_user", "other_customer_tenant").update(access="allowed")),
    ("customer users reading internal non-public data", lambda p: _tenant_rule(p, "customer_user", "internal").update(access="allowed")),
    ("employees reading customer tenants without a grant", lambda p: _tenant_rule(p, "employee", "other_customer_tenant").update(access="allowed")),
    ("restricted label allowing manager_of", lambda p: _label_rule(p, "restricted")["allowed_relations"].append("manager_of")),
    ("customer users allowed on restricted", lambda p: _label_rule(p, "restricted")["allowed_principal_types"].append("customer_user")),
    ("confidential not requiring a grant", lambda p: _label_rule(p, "confidential").update(requires_grant=False)),
    ("compensation granted to a confidential-ceiling group", lambda p: _default(p, "compensation_record")["access_groups"].append("GRP-hr")),
    ("default granting an unknown group", lambda p: _default(p, "contract")["access_groups"].append("GRP-everyone")),
    ("internal document type carrying grants", lambda p: _default(p, "employee_profile")["access_groups"].append("GRP-hr")),
    ("a document type without a default", lambda p: p["document_type_defaults"].pop(0)),
    ("support ticket defaulted to the internal tenant", lambda p: _default(p, "support_ticket").update(tenant_scope="internal")),
    ("relation over an edge type that does not exist", lambda p: p["relation_definitions"][1]["evaluation"].update(edge_relations=["manages"])),
    ("contractors admitted to a group", lambda p: p["groups"][0]["membership_rule"].update(exclude_employment_types=[])),
    ("evaluator scoped into a customer tenant", lambda p: p["service_bindings"][0]["service_scopes"].append("T-CUST-012")),
    ("deleted versions visible in history", lambda p: p["lifecycle_visibility"].update(deleted="history_only")),
]


def policy_problems(policy, schemas):
    """Consistency and security invariants that JSON Schema cannot express."""
    problems = []
    rank = {label: i for i, label in enumerate(policy["label_order"])}
    groups = {g["group_id"]: g for g in policy["groups"]}

    # Coverage: every case is explicit, exactly once
    pairs = [(r["principal_type"], r["document_tenant"]) for r in policy["tenant_rules"]]
    if len(set(pairs)) != 9:
        problems.append("tenant_rules must cover all 9 (principal_type, document_tenant) pairs exactly once")
    if sorted(r["label"] for r in policy["label_rules"]) != sorted(policy["label_order"]):
        problems.append("label_rules must cover each label exactly once")
    relation_names = schemas[SCHEMA_DIR / "common.schema.json"]["$defs"]["relation_rule"]["enum"]
    if sorted(r["name"] for r in policy["relation_definitions"]) != sorted(relation_names):
        problems.append("relation_definitions must define each relation rule exactly once")
    if len(groups) != len(policy["groups"]):
        problems.append("duplicate group_id in groups")

    # Document types: one default each, consistent with the front matter contract
    fm = schemas[SCHEMA_DIR / FM]
    doc_types = fm["properties"]["document_type"]["enum"]
    system_of = {}
    for rule in fm["allOf"]:
        system = rule.get("if", {}).get("properties", {}).get("source_system", {}).get("const")
        allowed = rule.get("then", {}).get("properties", {}).get("document_type", {})
        for t in allowed.get("enum", [allowed["const"]] if "const" in allowed else []):
            system_of[t] = system
    defaults = [d["document_type"] for d in policy["document_type_defaults"]]
    if sorted(defaults) != sorted(doc_types):
        problems.append("document_type_defaults must list every front-matter document_type exactly once")
    edge_relations = schemas[SCHEMA_DIR / "relationships/edge.schema.json"]["properties"]["relation"]["enum"]

    for d in policy["document_type_defaults"]:
        t, label = d["document_type"], d["sensitivity_label"]
        rule = _label_rule(policy, label)
        if system_of.get(t) != d["source_system"]:
            problems.append(f"{t}: source_system {d['source_system']} disagrees with the front matter contract ({system_of.get(t)})")
        if (d["tenant_scope"] == "customer") != (t == "support_ticket"):
            problems.append(f"{t}: only support_ticket lives in customer tenants")
        has_grant = d["access_groups"] or d["access_relation_templates"] or d["access_principal_templates"]
        if not rule["requires_grant"] and has_grant:
            problems.append(f"{t}: {label} documents must not carry grants")
        if rule["requires_grant"] and not has_grant:
            problems.append(f"{t}: {label} documents need at least one grant")
        for g in d["access_groups"]:
            if g not in groups:
                problems.append(f"{t}: unknown group {g}")
            elif rank[label] > rank[groups[g]["max_label"]]:
                problems.append(f"{t}: {g} has max_label {groups[g]['max_label']} and could never open a {label} document")
        for tpl in d["access_relation_templates"]:
            if tpl["relation"] not in rule["allowed_relations"]:
                problems.append(f"{t}: relation {tpl['relation']} is not allowed on {label}")
        if d["access_principal_templates"] and "principal" not in rule["allowed_grant_types"]:
            problems.append(f"{t}: principal grants are not allowed on {label}")

    for r in policy["relation_definitions"]:
        for e in r["evaluation"]["edge_relations"]:
            if e not in edge_relations:
                problems.append(f"relation {r['name']}: edge relation {e} does not exist")

    for g in policy["groups"]:
        if "contractor" not in g["membership_rule"]["exclude_employment_types"]:
            problems.append(f"{g['group_id']}: contractors must be excluded from every group in v1")
        if g["group_type"] == "department" and g["membership_rule"].get("department_code") != g["department_code"]:
            problems.append(f"{g['group_id']}: department group must draw members from its own department")

    for b in policy["service_bindings"]:
        for g in b["groups"]:
            if g not in groups:
                problems.append(f"{b['principal_id']}: bound to unknown group {g}")
        if b["purpose"] == "baseline_eval" and b["service_scopes"] != ["T-INSURELLM"]:
            problems.append(f"{b['principal_id']}: the baseline evaluator must be scoped to T-INSURELLM only")

    # Security invariants: these must hold whatever else changes
    if _tenant_rule(policy, "customer_user", "other_customer_tenant")["access"] != "never":
        problems.append("SECURITY: customer users must never read another customer's tenant")
    if _tenant_rule(policy, "customer_user", "internal")["access"] != "public_only":
        problems.append("SECURITY: customer users may read only public documents in the internal tenant")
    if _tenant_rule(policy, "employee", "other_customer_tenant")["access"] != "grant_required":
        problems.append("SECURITY: employees must need an explicit grant to read a customer tenant")
    restricted = _label_rule(policy, "restricted")
    if "customer_user" in restricted["allowed_principal_types"]:
        problems.append("SECURITY: customer users must never read restricted documents")
    if set(restricted["allowed_relations"]) - {"self"}:
        problems.append("SECURITY: restricted documents may only use the self relation")
    for label in ("confidential", "restricted"):
        if not _label_rule(policy, label)["requires_grant"]:
            problems.append(f"SECURITY: {label} must require a grant")
    if "customer_user" in _label_rule(policy, "internal")["allowed_principal_types"]:
        problems.append("SECURITY: customer users must never read internal documents")
    return problems


def load_registry():
    schemas = {}
    for path in sorted(SCHEMA_DIR.rglob("*.schema.json")):
        schemas[path] = json.loads(path.read_text(encoding="utf-8"))
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    return schemas, registry


def validator_for(schema, registry):
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def main():
    schemas, registry = load_registry()
    failures = 0

    for path, schema in schemas.items():
        name = path.relative_to(SCHEMA_DIR)
        Draft202012Validator.check_schema(schema)
        validator = validator_for(schema, registry)
        for index, example in enumerate(schema.get("examples", [])):
            errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
            for error in errors:
                failures += 1
                print(f"FAIL {name} example {index}: {'/'.join(map(str, error.path))}: {error.message}")
        print(f"ok   {name} ({len(schema.get('examples', []))} example)")

    # Reserved ingestion fields must be rejected in source data
    reserved = schemas[SCHEMA_DIR / "common.schema.json"]["$defs"]["reserved_ingestion_field"]["enum"]
    targets = [SCHEMA_DIR / FM] + sorted((SCHEMA_DIR / "entities").glob("*.schema.json"))
    for path in targets:
        schema = schemas[path]
        validator = validator_for(schema, registry)
        for field in reserved:
            bad = copy.deepcopy(schema["examples"][0])
            bad[field] = "x"
            if validator.is_valid(bad):
                failures += 1
                print(f"FAIL {path.relative_to(SCHEMA_DIR)} accepted reserved field {field!r}")
    print(f"ok   reserved ingestion fields rejected by {len(targets)} source schemas")

    # Contract rules: each case mutates a valid example and must be REJECTED
    for rel_path, description, mutate in NEGATIVE_CASES:
        schema = schemas[SCHEMA_DIR / rel_path]
        bad = copy.deepcopy(schema["examples"][0])
        mutate(bad)
        if validator_for(schema, registry).is_valid(bad):
            failures += 1
            print(f"FAIL {rel_path} accepted: {description}")
    print(f"ok   {len(NEGATIVE_CASES)} contract rules reject bad data")

    # The policy set itself
    policy_validator = validator_for(schemas[SCHEMA_DIR / POLICY_SCHEMA], registry)
    policy = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
    errors = list(policy_validator.iter_errors(policy))
    for error in errors:
        failures += 1
        print(f"FAIL policies.yaml: {'/'.join(map(str, error.path))}: {error.message}")
    problems = [] if errors else policy_problems(policy, schemas)
    for problem in problems:
        failures += 1
        print(f"FAIL policies.yaml: {problem}")
    if not errors and not problems:
        print(f"ok   policies.yaml: schema, {len(policy['document_type_defaults'])} document types, "
              f"{len(policy['groups'])} groups, security invariants")

    for description, mutate in POLICY_NEGATIVE_CASES:
        bad = copy.deepcopy(policy)
        mutate(bad)
        caught = not policy_validator.is_valid(bad) or policy_problems(bad, schemas)
        if not caught:
            failures += 1
            print(f"FAIL policies.yaml invariants missed: {description}")
    print(f"ok   {len(POLICY_NEGATIVE_CASES)} broken policy variants all rejected")

    print(f"\n{len(schemas)} schemas checked, {failures} failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

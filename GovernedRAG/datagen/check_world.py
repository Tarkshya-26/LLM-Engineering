"""Independent checker for the generated source world (pre-document phase).

    python -m datagen.check_world      (from the GovernedRAG root)

Works only from the files written to data/source/ (and the KB). It does not import
the generator. Sections:
  A  schema validation of every row, event, plan entry and ground-truth record
  B  seed preservation: KB files unchanged, seeded entity values equal the seed,
     seeded document bodies rebuild byte-for-byte from the KB
  C  CDC replay: T0 files + events (dedupe by event_id, discard stale sequences)
  D  cross-record invariants (README section 6) at every checkpoint
  E  independent authorization recomputation vs access_matrix.jsonl
  F  versioned facts, checkpoints and annotations vs replayed state
"""

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .docplan import PENDING_SHA, body_from_spec, sha256, split_document
from .kb import KB_ROOT, SEED_DIR, SOURCE_ROOT

S = SOURCE_ROOT
SCHEMA = S / "schema"
ENTITY_FILES = {"locations": "location", "departments": "department", "teams": "team", "employees": "employee",
                "compensation": "compensation", "performance_reviews": "performance_review", "products": "product",
                "product_tiers": "product_tier", "customers": "customer", "contracts": "contract", "contract_versions": "contract_version",
                "projects": "project", "policies": "policy", "policy_versions": "policy_version", "incidents": "incident",
                "support_tickets": "support_ticket", "financial_records": "financial_record"}
PK = {"location": "location_id", "department": "department_id", "team": "team_id", "employee": "employee_id", "compensation": "compensation_id",
      "performance_review": "review_id", "product": "product_id", "product_tier": "tier_id", "customer": "customer_id", "contract": "contract_id",
      "contract_version": "contract_version_id", "project": "project_id", "policy": "policy_id", "policy_version": "policy_version_id",
      "incident": "incident_id", "support_ticket": "ticket_id", "financial_record": "financial_id", "tenant": "tenant_id",
      "principal": "principal_id", "group": "group_id", "membership": "membership_id"}
RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def jl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


class Report:
    def __init__(self):
        self.results = []

    def check(self, section, name, failures, detail=""):
        failures = list(failures)
        self.results.append((section, name, len(failures), detail))
        for f in failures[:5]:
            print(f"   FAIL [{section}] {name}: {f}")
        if len(failures) > 5:
            print(f"   ... {len(failures) - 5} more")


def load_validators():
    schemas = {p: json.loads(p.read_text()) for p in SCHEMA.rglob("*.schema.json")}
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas.values())
    return {p.relative_to(SCHEMA).as_posix(): Draft202012Validator(s, registry=registry, format_checker=FormatChecker()) for p, s in schemas.items()}


# =============================================================================== A
def section_a(rep, V, data):
    def run(name, schema, rows):
        bad = []
        for i, r in enumerate(rows):
            errs = list(V[schema].iter_errors(r))
            if errs:
                bad.append(f"{name}[{i}] {'/'.join(map(str, errs[0].path))}: {errs[0].message[:120]}")
        rep.check("A", f"{name} ({len(rows)})", bad)
    for fname, otype in ENTITY_FILES.items():
        run(f"entities/{fname}", f"entities/{otype}.schema.json", data["entities"][otype])
    for fname, schema in [("tenants", "tenant"), ("principals", "principal"), ("groups", "group"), ("memberships", "membership")]:
        run(f"access_control/{fname}", f"access_control/{schema}.schema.json", data["access"][fname])
    run("access_control/policies.yaml", "access_control/policy_set.schema.json", [data["policy"]])
    run("relationships/edges", "relationships/edge.schema.json", data["edges"])
    run("cdc/events", "cdc/event.schema.json", data["events"])
    run("cdc/manifest", "cdc/manifest.schema.json", [data["manifest"]])
    run("_build/document_plan front matter", "documents/front_matter.schema.json", [p["front_matter"] for p in data["plan"]])
    for name, schema in [("personas", "persona"), ("access_matrix", "access_decision"), ("versioned_facts", "versioned_fact"),
                         ("checkpoints", "checkpoint"), ("document_annotations", "document_annotation")]:
        run(f"ground_truth/{name}", f"ground_truth/{schema}.schema.json", data["gt"][name])


# =============================================================================== B
def section_b(rep, data):
    hashes = json.loads((SEED_DIR / "kb_file_hashes.json").read_text())
    rep.check("B", "KB files unchanged since seeding (sha256)",
              [p for p, h in hashes.items() if hashlib.sha256((KB_ROOT / p).read_text(encoding="utf-8").encode()).hexdigest() != h])
    r = subprocess.run([sys.executable, "-m", "datagen.check_seed"], capture_output=True, text=True, cwd=S.parent.parent)
    rep.check("B", "seed provenance (datagen.check_seed)", [] if r.returncode == 0 else [r.stdout.strip().splitlines()[-1]],
              r.stdout.strip().splitlines()[0])

    seed = json.loads((SEED_DIR / "kb_seed.json").read_text())
    val = lambda f: f.get("value") if isinstance(f, dict) else None
    ents = {o: {r[PK[o]]: r for r in rows} for o, rows in data["entities"].items()}
    bad = []
    for e in seed["employees"]:
        row = ents["employee"][e["id"]]
        for field, expected in [("date_of_birth", val(e["date_of_birth"])), ("job_title", val(e["job_title"]))]:
            if row[field] != expected:
                bad.append(f"{e['id']}.{field}: {row[field]!r} != seed {expected!r}")
        if row["hire_date"][:len(val(e["hire"]))] != val(e["hire"]):
            bad.append(f"{e['id']}.hire_date {row['hire_date']} != seed {val(e['hire'])}")
        awards = sorted((r["award_name"], r["year"]) for r in row["recognitions"])
        if awards != sorted((val(r["award_name"]), val(r["year"])) for r in e["recognitions"]):
            bad.append(f"{e['id']}.recognitions differ from seed")
        comp = sorted(c["base_salary"]["amount"] for c in ents["compensation"].values() if c["employee_id"] == e["id"])
        if comp != sorted(val(c["base_salary"]) for c in e["compensation_history"] if val(c["base_salary"]) is not None):
            bad.append(f"{e['id']} compensation amounts differ from seed")
        open_rows = [c for c in ents["compensation"].values() if c["employee_id"] == e["id"] and c["effective_to"] is None]
        if len(open_rows) != 1 or open_rows[0]["base_salary"]["amount"] != val(e["current_salary"]):
            bad.append(f"{e['id']} open compensation row != seed current salary {val(e['current_salary'])}")
        ratings = sorted((r["review_year"], r["rating_label"] or r["rating_score"]) for r in ents["performance_review"].values() if r["employee_id"] == e["id"])
        if ratings != sorted((val(r["year"]), val(r["rating"])) for r in e["performance_history"]):
            bad.append(f"{e['id']} performance ratings differ from seed")
    for p in seed["products"]:
        if ents["product"][p["id"]]["name"] != p["name"]["value"]:
            bad.append(f"{p['id']} name differs")
        for t in p["tiers"]:
            row = ents["product_tier"][t["id"]]
            price = (row["monthly_list_price"] or {}).get("amount")
            if price != val(t["price"]) or row["tier_name"] != t["tier_name"]["value"]:
                bad.append(f"{t['id']} tier {row['tier_name']} {price} != seed {t['tier_name']['value']} {val(t['price'])}")
    for c in seed["contracts"]:
        h, v = ents["contract"][c["id"]], ents["contract_version"][f"{c['id']}@v1"]
        sched = [(r["from_month"], r["to_month"], r["monthly_fee"]["amount"]) for r in v["fee_schedule"]]
        checks = [("contract_number", h["contract_number"], val(c["contract_number"])), ("signed_on", h["signed_on"], val(c["signed_on"])),
                  ("customer", ents["customer"][c["customer_id"]]["display_name"], c["customer_display_name"]["value"]),
                  ("term_months", v["term_months"], val(c["term_months"])), ("total", (v["total_contract_value"] or {}).get("amount"), val(c["total_value"])),
                  ("licenses", v["user_licenses"], val(c["user_licenses"])),
                  ("schedule", sched, [(r["from_month"], r["to_month"], val(r["monthly_fee"])) for r in c["fee_schedule"]]),
                  ("fee", (v["monthly_fee"] or {}).get("amount"), val(c["monthly_fee"]) if val(c["monthly_fee"]) is not None else (sched[0][2] if sched else None)),
                  ("signatory_as_printed", (h["insurellm_signatory_as_printed"] or {}).get("name"), c["insurellm_signatory"].get("name", {}).get("value"))]
        for name, got, want in checks:
            if got != want:
                bad.append(f"{c['id']}.{name}: {got!r} != seed {want!r}")
        if h["insurellm_signatory_id"] is not None:
            bad.append(f"{c['id']}: a seeded contract links its signatory to an employee identity")
    rep.check("B", "seeded entity values equal the seed (employees, pay, ratings, awards, tiers, contracts)", bad)

    plan = {p["front_matter"]["document_version_id"]: p for p in data["plan"]}
    bad, covered = [], defaultdict(set)
    for dvid, p in plan.items():
        if p["body"]["mode"] in ("kb_verbatim", "kb_patch"):
            text = body_from_spec(p["body"], plan)
            if sha256(text) != p["front_matter"]["content_sha256"]:
                bad.append(f"{dvid}: rebuilt body hash differs from front matter")
            if p["body"]["mode"] == "kb_verbatim":
                lines = (KB_ROOT / p["body"]["kb_file"]).read_text(encoding="utf-8").splitlines(keepends=True)
                for a, b in p["body"]["line_ranges"]:
                    covered[p["body"]["kb_file"]].update(range(a, b))
                if p["batch_id"] != "BATCH-00":
                    bad.append(f"{dvid}: verbatim KB body outside the T0 load")
        elif p["front_matter"]["content_sha256"] == PENDING_SHA:
            bad.append(f"{dvid}: generated body still has the pending hash")
    for f in hashes:
        n = len((KB_ROOT / f).read_text(encoding="utf-8").splitlines(keepends=True))
        if covered[f] != set(range(n)):
            bad.append(f"{f}: {n - len(covered[f])} KB lines not carried into any seeded document")
    rep.check("B", "seeded document bodies rebuild byte-for-byte; every KB line carried over", bad,
              f"{sum(1 for p in plan.values() if p['body']['mode'] == 'kb_verbatim')} verbatim, "
              f"{sum(1 for p in plan.values() if p['body']['mode'] == 'kb_patch')} patched")


# =============================================================================== C
def replay(data):
    """State at each checkpoint, rebuilt from T0 files + CDC in delivery order."""
    state = {o: {r[PK[o]]: copy.deepcopy(r) for r in rows} for o, rows in data["entities"].items()}
    for fname, otype in [("tenants", "tenant"), ("principals", "principal"), ("groups", "group"), ("memberships", "membership")]:
        state[otype] = {r[PK[otype]]: copy.deepcopy(r) for r in data["access"][fname]}
    state["document_version"] = {p["front_matter"]["document_version_id"]: {"front_matter": copy.deepcopy(p["front_matter"]), "body_path": None}
                                 for p in data["plan"] if p["batch_id"] == "BATCH-00"}
    seen, last_seq, stats = set(), {}, Counter()
    snapshots = {"CP-T0": copy.deepcopy(state)}
    deleted = {"CP-T0": set()}
    gone = set()
    for batch in [b["batch_id"] for b in data["manifest"]["batches"][1:]]:
        for e in [e for e in data["events"] if e["batch_id"] == batch]:
            if e["event_id"] in seen:
                stats["duplicate_ignored"] += 1
                continue
            seen.add(e["event_id"])
            k = (e["object_type"], e["object_id"])
            if last_seq.get(k, 0) > e["sequence"]:
                stats["stale_discarded"] += 1
                continue
            last_seq[k] = e["sequence"]
            table = state[e["object_type"]]
            if e["operation"] == "delete":
                table.pop(e["object_id"], None)
                if e["object_type"] == "document_version":
                    gone.add(e["object_id"])
            else:
                table[e["object_id"]] = copy.deepcopy(e["after"])
            stats[e["operation"]] += 1
        cp = "CP-" + batch.replace("BATCH-", "B")
        snapshots[cp], deleted[cp] = copy.deepcopy(state), set(gone)
    return snapshots, deleted, stats


# =============================================================================== D
def fk_fields(edge_schema):
    out = defaultdict(list)
    for rel, spec in edge_schema["$defs"]["relation_catalog"]["const"].items():
        entity, path = spec["derived_from"].split(".", 1)
        target = spec["to_type"] if spec["from_type"] == entity and spec["to_type"] != entity or spec["from_type"] == spec["to_type"] else spec["from_type"]
        out[entity].append((path, target, rel, spec))
    return out


def derive_edges(st, fks):
    """Open edges implied by the state, as (relation, from, to)."""
    out = set()
    for otype, specs in fks.items():
        for row in st.get(otype, {}).values():
            key = row[PK[otype]]
            for path, target, rel, spec in specs:
                if "." in path:
                    container, field = path.split(".", 1)
                    values = [i.get(field) for i in row.get(container, [])]
                else:
                    v = row.get(path)
                    values = v if isinstance(v, list) else [v]
                for v in values:
                    if not v:
                        continue
                    same = spec["from_type"] == spec["to_type"]
                    out.add((rel, key, v) if (spec["from_type"] == otype and (same or spec["to_type"] != otype)) else (rel, v, key))
    return out


def section_d(rep, data, snaps, deleted, as_of):
    policy = data["policy"]
    fks = fk_fields(json.loads((SCHEMA / "relationships/edge.schema.json").read_text()))
    plan = {p["front_matter"]["document_version_id"]: p for p in data["plan"]}
    defaults = {d["document_type"]: d for d in policy["document_type_defaults"]}
    groups = {g["group_id"]: g for g in policy["groups"]}
    tables_for_type = {"location": "location", "department": "department", "team": "team", "employee": "employee", "compensation": "compensation",
                       "performance_review": "performance_review", "product": "product", "product_tier": "product_tier", "customer": "customer",
                       "contract": "contract", "contract_version": "contract_version", "project": "project", "policy": "policy",
                       "policy_version": "policy_version", "incident": "incident", "support_ticket": "support_ticket",
                       "financial_record": "financial_record", "tenant": "tenant"}
    prefix_table = {"LOC": "location", "DEPT": "department", "TEAM": "team", "EMP": "employee", "COMP": "compensation", "PRV": "performance_review",
                    "PROD": "product", "TIER": "product_tier", "CUST": "customer", "CON": "contract", "PROJ": "project", "POL": "policy",
                    "INC": "incident", "TCK": "support_ticket", "FIN": "financial_record", "T": "tenant"}

    def table_of(ref):
        if "@v" in ref:
            return "contract_version" if ref.startswith("CON") else "policy_version"
        return prefix_table[ref.split("-")[0]]

    fk_bad, doc_bad, ver_bad, org_bad, acc_bad, edge_bad, misc_bad = [], [], [], [], [], [], []
    for cp, st in snaps.items():
        d = as_of[cp][:10]
        # 3. foreign keys
        for otype, specs in fks.items():
            for row in st.get(otype, {}).values():
                for path, target, rel, spec in specs:
                    if "." in path:
                        values = [i.get(path.split(".")[1]) for i in row.get(path.split(".")[0], [])]
                    else:
                        v = row.get(path)
                        values = v if isinstance(v, list) else [v]
                    for v in values:
                        if v and v not in st[tables_for_type[target]]:
                            fk_bad.append(f"{cp} {otype} {row[PK[otype]]}.{path} -> missing {v}")
        for p in st["principal"].values():
            for f, t in [("employee_id", "employee"), ("customer_id", "customer"), ("home_tenant_id", "tenant")]:
                if p[f] and p[f] not in st[t]:
                    fk_bad.append(f"{cp} principal {p['principal_id']}.{f} -> missing {p[f]}")
        for m in st["membership"].values():
            if m["principal_id"] not in st["principal"] or m["group_id"] not in st["group"]:
                fk_bad.append(f"{cp} membership {m['membership_id']} dangling")
        # 1, 4, 5, 10. documents
        current = Counter()
        for dvid, row in st["document_version"].items():
            fm = row["front_matter"]
            if fm["document_version_id"] != f"{fm['document_id']}@v{fm['version']}":
                doc_bad.append(f"{dvid}: id/version mismatch")
            if not set(fm["source_record_ids"]) <= set(fm["subject_entities"]):
                doc_bad.append(f"{dvid}: subject_entities missing source_record_ids")
            if fm["supersedes"] and (not fm["supersedes"].startswith(fm["document_id"] + "@") or int(fm["supersedes"].split("@v")[1]) >= fm["version"]):
                doc_bad.append(f"{dvid}: supersedes {fm['supersedes']} is not an earlier version")
            for ref in fm["source_record_ids"] + fm["subject_entities"]:
                if ref not in st[table_of(ref)]:
                    fk_bad.append(f"{cp} {dvid} references missing {ref}")
            if fm["owner_department_id"] not in st["department"] or fm["source_owner_id"] not in st["employee"]:
                fk_bad.append(f"{cp} {dvid} owner missing")
            if fm["status"] == "current":
                current[fm["document_id"]] += 1
            dflt = defaults[fm["document_type"]]
            if RANK[fm["sensitivity_label"]] < RANK[dflt["sensitivity_label"]]:
                acc_bad.append(f"{dvid}: label {fm['sensitivity_label']} looser than default {dflt['sensitivity_label']}")
            if fm["sensitivity_label"] == dflt["sensitivity_label"] and not set(fm["access_groups"]) <= set(dflt["access_groups"]):
                acc_bad.append(f"{dvid}: adds group grants at the default label")
            for g in fm["access_groups"]:
                if RANK[fm["sensitivity_label"]] > RANK[groups[g]["max_label"]]:
                    acc_bad.append(f"{dvid}: grants {g} above its max_label")
        doc_bad += [f"{cp} {doc}: {n} current versions" for doc, n in current.items() if n > 1]
        for otype, vtype, fk in [("contract", "contract_version", "contract_id"), ("policy", "policy_version", "policy_id")]:
            for key, h in st[otype].items():
                cur = [v for v in st[vtype].values() if v[fk] == key and v["version_status"] == "current"]
                live = [v for v in st[vtype].values() if v[fk] == key]
                latest = max(v["version"] for v in live)
                if h["current_version"] != latest or len(cur) > 1:
                    ver_bad.append(f"{cp} {key}: header current_version {h['current_version']} vs latest {latest}, {len(cur)} current")
        # 6, 7, 8, 9
        for c in st["customer"].values():
            if c["portal_tenant_id"] and c["portal_tenant_id"][-3:] != c["customer_id"][-3:]:
                org_bad.append(f"{c['customer_id']} portal tenant number mismatch")
            if c["account_manager_id"] not in c["account_team_ids"] or (c["customer_success_manager_id"] and c["customer_success_manager_id"] not in c["account_team_ids"]):
                org_bad.append(f"{cp} {c['customer_id']}: AM/CSM not on account team")
        for t in st["support_ticket"].values():
            if t["tenant_id"] != st["customer"][t["customer_id"]]["portal_tenant_id"]:
                org_bad.append(f"{t['ticket_id']} tenant != customer portal tenant")
        for e in st["employee"].values():
            rows = sorted((c for c in st["compensation"].values() if c["employee_id"] == e["employee_id"]), key=lambda c: c["effective_from"])
            if rows and sum(1 for c in rows if c["effective_to"] is None) != 1:
                org_bad.append(f"{cp} {e['employee_id']}: {sum(1 for c in rows if c['effective_to'] is None)} open pay rows")
            for a, b in zip(rows, rows[1:]):
                if a["effective_to"] is None or a["effective_to"] >= b["effective_from"]:
                    org_bad.append(f"{cp} {e['employee_id']}: overlapping pay rows")
            if e["employment_status"] == "terminated" and st["principal"]["P-" + e["employee_id"]]["principal_status"] == "active":
                org_bad.append(f"{cp} {e['employee_id']}: terminated but principal active")
        roots = [e for e in st["employee"].values() if e["manager_id"] is None]
        if len(roots) != 1 or roots[0]["job_title"] != "Co-Founder & Chief Executive Officer (CEO)":
            org_bad.append(f"{cp}: {len(roots)} employees without a manager")
        for e in st["employee"].values():
            seen, node = set(), e["employee_id"]
            while node and node not in seen:
                seen.add(node)
                node = st["employee"][node]["manager_id"]
            if node:
                org_bad.append(f"{cp}: management cycle at {node}")
        emp_principals = Counter(p["employee_id"] for p in st["principal"].values() if p["principal_type"] == "employee")
        org_bad += [f"{cp} {eid}: {emp_principals[eid]} principals" for eid in st["employee"] if emp_principals[eid] != 1]
        # 11. edges equal what the state implies
        open_edges = {(e["relation"], e["from_id"], e["to_id"]) for e in data["edges"] if e["valid_from"] <= d and (e["valid_to"] is None or d <= e["valid_to"])}
        implied = derive_edges(st, fks)
        edge_bad += [f"{cp} edge in file but not implied by state: {x}" for x in sorted(open_edges - implied)[:3]]
        edge_bad += [f"{cp} implied by state but missing from edges.jsonl: {x}" for x in sorted(implied - open_edges)[:3]]
        # 16. groups mirror policy
        if {g for g in st["group"]} != set(groups):
            misc_bad.append(f"{cp}: groups.jsonl differs from policies.yaml")
        for m in st["membership"].values():
            pr = st["principal"][m["principal_id"]]
            if pr["principal_type"] == "employee" and st["employee"][pr["employee_id"]]["employment_type"] == "contractor":
                misc_bad.append(f"{cp}: contractor {pr['principal_id']} holds membership {m['membership_id']}")
    # 14. fictional identities
    kb_names = {e["full_name"]["value"] for e in json.loads((SEED_DIR / "kb_seed.json").read_text())["employees"]}
    signers = {"Sarah Chen", "Michael Torres", "Jennifer Rodriguez"}
    final = snaps[max(snaps)]
    for p in final["principal"].values():
        if not p["email"].endswith(".example"):
            misc_bad.append(f"{p['principal_id']}: non-.example email")
        if p["principal_type"] == "employee" and p["display_name"] in signers:
            misc_bad.append(f"{p['principal_id']}: contract signatory created as an employee identity")
    new_people = [e for e in final["employee"].values() if e["origin"] == "generated"]
    misc_bad += [f"new hire reuses a KB name: {e['first_name']} {e['last_name']}" for e in new_people if f"{e['first_name']} {e['last_name']}" in kb_names | signers]
    rep.check("D", "3  foreign keys resolve at every checkpoint (entities, principals, memberships, documents)", fk_bad)
    rep.check("D", "1,4,5  document ids, supersession, at most one current version", doc_bad)
    rep.check("D", "5  contract/policy headers match their current version", ver_bad)
    rep.check("D", "6-9  tenants, account teams, pay rows, one CEO, no cycles, one principal per employee", org_bad)
    rep.check("D", "10  no document looser than its default; group ceilings respected", acc_bad)
    rep.check("D", "11  edges.jsonl equals the edges implied by replayed state", edge_bad)
    rep.check("D", "14,16  .example identities, signatories not employees, groups mirror policy, contractors in no group", misc_bad)


# =============================================================================== E
class IndependentEvaluator:
    """Recomputes decisions from replayed state. Relationships come from entity fields, not edges.jsonl."""

    def __init__(self, policy, st, as_of):
        self.p, self.st, self.d = policy, st, as_of[:10]
        self.labels = {r["label"]: r for r in policy["label_rules"]}
        self.tenant = {(r["principal_type"], r["document_tenant"]): r["access"] for r in policy["tenant_rules"]}
        self.max_label = {g["group_id"]: g["max_label"] for g in policy["groups"]}

    def member(self, pid, gid):
        return any(m["principal_id"] == pid and m["group_id"] == gid and m["valid_from"] <= self.d and (m["valid_to"] is None or self.d <= m["valid_to"])
                   for m in self.st["membership"].values())

    def relation(self, rel, emp, subject):
        if rel == "self":
            return emp == subject
        if rel == "manager_of":
            m1 = self.st["employee"].get(subject, {}).get("manager_id")
            m2 = self.st["employee"].get(m1, {}).get("manager_id") if m1 else None
            return emp in (m1, m2)
        if rel == "account_team_of":
            return emp in self.st["customer"].get(subject, {}).get("account_team_ids", [])
        return False

    def one(self, pr, fm, status):
        if pr["principal_status"] != "active":
            return "deny", "deny_principal_not_active", None
        if status == "deleted":
            return "deny", "deny_document_deleted", None
        t = self.st["tenant"].get(fm["tenant_id"])
        if not t or t["tenant_status"] != "active":
            return "deny", "deny_tenant_not_active", None
        where = "internal" if fm["tenant_id"] == "T-INSURELLM" else ("own_customer_tenant" if fm["tenant_id"] == pr["home_tenant_id"] else "other_customer_tenant")
        access, label = self.tenant[(pr["principal_type"], where)], fm["sensitivity_label"]
        if access == "never" or (access == "scope_required" and fm["tenant_id"] not in pr["service_scopes"]):
            return "deny", "deny_tenant_isolation", None
        if access == "public_only" and label != "public":
            return "deny", "deny_public_only", None
        lr = self.labels[label]
        if pr["principal_type"] not in lr["allowed_principal_types"]:
            return "deny", "deny_principal_type_for_label", None
        if not lr["requires_grant"] and access != "grant_required":
            return "allow", f"allow_{label}_label", None
        ok = lr["allowed_grant_types"]
        if "group" in ok:
            for g in fm["access_groups"]:
                if RANK[label] <= RANK[self.max_label[g]] and self.member(pr["principal_id"], g):
                    return "allow", "allow_group_grant", ("group", g)
        if "relation" in ok and pr["employee_id"]:
            for r in fm["access_relations"]:
                if r["relation"] in lr["allowed_relations"] and self.relation(r["relation"], pr["employee_id"], r["subject"]):
                    return "allow", "allow_relation_grant", ("relation", f"{r['relation']}:{r['subject']}")
        if "principal" in ok and pr["principal_id"] in fm["access_principals"]:
            return "allow", "allow_principal_grant", ("principal", pr["principal_id"])
        if "tenant_membership" in ok and pr["principal_type"] == "customer_user" and fm["tenant_id"] == pr["home_tenant_id"]:
            return "allow", "allow_tenant_membership", ("tenant_membership", fm["tenant_id"])
        return "deny", "deny_no_matching_grant", None


def section_e(rep, data, snaps, deleted, as_of):
    plan = {p["front_matter"]["document_version_id"]: p["front_matter"] for p in data["plan"]}
    personas = {p["persona_id"]: p["principal_id"] for p in data["gt"]["personas"]}
    rows = defaultdict(dict)
    for r in data["gt"]["access_matrix"]:
        rows[r["checkpoint_id"]][(r["persona_id"], r["document_version_id"])] = r
    mismatch, coverage, edge_refs = [], [], []
    edges = {e["edge_id"]: e for e in data["edges"]}
    totals = Counter()
    for cp, st in snaps.items():
        ev = IndependentEvaluator(data["policy"], st, as_of[cp])
        docs = {k: (v["front_matter"], v["front_matter"]["status"]) for k, v in st["document_version"].items()}
        for dvid in deleted[cp]:
            docs[dvid] = (plan[dvid], "deleted")
        expected_keys = set()
        for persona, pid in personas.items():
            pr = st["principal"].get(pid)
            if pr is None:
                continue
            for dvid, (fm, status) in docs.items():
                expected_keys.add((persona, dvid))
                decision, reason, grant = ev.one(pr, fm, status)
                if decision == "allow" and status in ("superseded", "archived"):
                    cur = [v for v in docs.values() if v[0]["document_id"] == fm["document_id"] and v[1] == "current"]
                    if cur and ev.one(pr, cur[0][0], "current")[0] == "deny":
                        decision, reason, grant = "deny", "deny_history_exceeds_current", None
                got = rows[cp].get((persona, dvid))
                totals[decision] += 1
                if got is None:
                    continue
                g = got["matched_grant"]
                if (got["decision"], got["reason_code"]) != (decision, reason) or (grant and (g["grant_type"], g["value"]) != grant):
                    mismatch.append(f"{cp} {persona} {dvid}: matrix {got['decision']}/{got['reason_code']} vs recomputed {decision}/{reason}")
                if g:
                    for eid in g["via_edge_ids"]:
                        e = edges.get(eid)
                        if not e or not (e["valid_from"] <= as_of[cp][:10] and (e["valid_to"] is None or as_of[cp][:10] <= e["valid_to"])):
                            edge_refs.append(f"{cp} {got['decision_id']}: via edge {eid} not valid at checkpoint")
                    if g["via_membership_id"] and g["via_membership_id"] not in st["membership"]:
                        edge_refs.append(f"{cp} {got['decision_id']}: via membership {g['via_membership_id']} missing")
        have = set(rows[cp])
        coverage += [f"{cp} missing row {k}" for k in sorted(expected_keys - have)[:3]] + [f"{cp} unexpected row {k}" for k in sorted(have - expected_keys)[:3]]
    rep.check("E", "access matrix covers every (persona, document version) at every checkpoint", coverage,
              f"{sum(len(v) for v in rows.values())} rows")
    rep.check("E", "independent recomputation agrees with every decision", mismatch,
              f"{totals['allow']} allow / {totals['deny']} deny")
    rep.check("E", "matched grants cite memberships and edges valid at the checkpoint", edge_refs)
    # 17. baseline evaluator reads every seeded T0 document
    seeded = {p["front_matter"]["document_version_id"] for p in data["plan"] if p["body"]["mode"] == "kb_verbatim"}
    base = [k for (persona, dvid), r in rows["CP-T0"].items() if persona == "PERS-01" and dvid in seeded and r["decision"] != "allow" for k in [dvid]]
    rep.check("E", "17  baseline evaluator can read every T0 document holding a KB fact", base, f"{len(seeded)} seeded documents")
    rep.check("E", "approved policy rules exercised (history rule, manager_of depth, tenant isolation)",
              [f"never exercised: {r}" for r in ["deny_history_exceeds_current", "deny_tenant_isolation", "deny_public_only", "deny_principal_not_active",
                                                  "deny_tenant_not_active", "deny_document_deleted", "allow_relation_grant", "allow_principal_grant", "allow_tenant_membership"]
               if not any(x["reason_code"] == r for x in data["gt"]["access_matrix"])])


# =============================================================================== F
def section_f(rep, data, snaps, deleted, as_of):
    plan = {p["front_matter"]["document_version_id"]: p for p in data["plan"]}
    final = snaps[max(snaps)]
    erased = deleted[max(deleted)]
    bad = []
    for f in data["gt"]["versioned_facts"]:
        for dvid in f["evidence_document_versions"]:
            if dvid in erased:
                bad.append(f"{f['fact_id']}: evidence {dvid} was erased")
            entry = plan.get(dvid)
            if not entry or not any(x["entity"] == f["source_record"]["record_id"] or x["entity"] == f["subject_entity_id"] for x in entry["facts"]):
                bad.append(f"{f['fact_id']}: evidence {dvid} does not state this record")
        labels = [plan[d]["front_matter"]["sensitivity_label"] for d in f["evidence_document_versions"] if d in plan]
        if labels and f["min_label_to_know"] != min(labels, key=RANK.get):
            bad.append(f"{f['fact_id']}: min_label_to_know {f['min_label_to_know']} wrong")
        rid, rtype = f["source_record"]["record_id"], f["source_record"]["entity_type"]
        if rtype in ("contract_version", "product_tier", "compensation"):
            row = next((s[rtype][rid] for s in reversed(list(snaps.values())) if rid in s[rtype]), None)
            if row is None:
                bad.append(f"{f['fact_id']}: record {rid} not found")
                continue
            path = f["source_record"]["field_path"].split(".")
            v = row
            for part in path:
                v = v[part]
            if v != f["value"]:
                bad.append(f"{f['fact_id']}: value {f['value']} != record {v}")
    rep.check("F", "versioned facts: values match records, evidence states them, labels right, nothing erased", bad,
              f"{len(data['gt']['versioned_facts'])} facts")
    bad = []
    for cp in data["gt"]["checkpoints"]:
        st = snaps[cp["checkpoint_id"]]
        states = {s["document_version_id"]: s for s in cp["document_states"]}
        live = {k: v["front_matter"] for k, v in st["document_version"].items()}
        for dvid, fm in live.items():
            s = states.get(dvid)
            if not s or s["status"] != fm["status"] or s["content_sha256"] != fm["content_sha256"]:
                bad.append(f"{cp['checkpoint_id']} {dvid}: checkpoint state differs from replayed state")
        for dvid in deleted[cp["checkpoint_id"]]:
            if states.get(dvid, {}).get("must_be_indexed") is not False:
                bad.append(f"{cp['checkpoint_id']} {dvid}: deleted but still must be indexed")
        if set(states) != set(live) | deleted[cp["checkpoint_id"]]:
            bad.append(f"{cp['checkpoint_id']}: document set differs from replay")
    rep.check("F", "checkpoints equal the replayed state (status, hash, deletions)", bad)
    ann_bad = [f"{a['annotation_id']}: refers to erased {a['document_version_id']}" for a in data["gt"]["document_annotations"] if a["document_version_id"] in erased]
    rep.check("F", "18  no annotation or fact refers to erased documents", ann_bad)


# =============================================================================== G
import re as _re
from datetime import date as _date

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MRE = "|".join(MONTHS)
ID_RE = _re.compile(r"\b(?:DOC-[A-Z]+-\d{4}(?:@v\d+)?|CON-\d{3}@v\d+|POL-\d{3}@v\d+|P-(?:EMP-\d{3}|CUS-\d{4}|SVC-\d{3})|T-CUST-\d{3}|T-INSURELLM"
                    r"|EMP-\d{3}|COMP-\d{4}|PRV-\d{4}|PROD-\d{3}|TIER-\d{3}|CUST-\d{3}|CON-\d{3}|PROJ-\d{3}|POL-\d{3}|INC-\d{3}|TCK-\d{4}|FIN-\d{3}"
                    r"|LOC-\d{2}|DEPT-\d{2}|TEAM-\d{2}|MEM-\d{5}|EDGE-\d{6}|EVT-\d{6})\b")
ISO_DT = _re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):\d{2}Z")
ISO_D = _re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUM = _re.compile(r"(?<![\w.])[$£€]?(\d[\d,]*(?:\.\d+)?)%?")
DATE_FIELDS = ("created_at", "updated_at", "valid_from", "valid_to")


class Allowed:
    def __init__(self):
        self.ids, self.dates, self.stamps, self.numbers, self.strings = set(), set(), set(), set(), set()

    def harvest(self, v):
        if isinstance(v, dict):
            for x in v.values():
                self.harvest(x)
        elif isinstance(v, list):
            for x in v:
                self.harvest(x)
        elif isinstance(v, bool) or v is None:
            return
        elif isinstance(v, (int, float)):
            self.numbers.add(float(v))
        elif isinstance(v, str):
            self.strings.add(v)
            rest = v
            for m in ID_RE.finditer(rest):
                self.ids.add(m.group())
            rest = ID_RE.sub(" ", rest)
            for m in ISO_DT.finditer(rest):
                self.dates.add(m.group(1))
                self.stamps.add((m.group(1), f"{m.group(2)}:{m.group(3)}"))
            rest = ISO_DT.sub(" ", rest)
            for m in ISO_D.finditer(rest):
                self.dates.add(m.group())
            rest = ISO_D.sub(" ", rest)
            for m in _re.finditer(r"\d[\d,]*(?:\.\d+)?", rest):
                self.numbers.add(float(m.group().replace(",", "")))


def _iso(month, day, year):
    return _date(int(year), MONTHS.index(month) + 1, int(day)).isoformat()


def unsupported(body, a):
    issues, text = [], body
    for m in ID_RE.finditer(text):
        if m.group() not in a.ids:
            issues.append(f"ID {m.group()}")
    text = ID_RE.sub(" ", text)
    for m in _re.finditer(rf"({MRE}) (\d{{1,2}}), (\d{{4}}) at (\d{{2}}):(\d{{2}}) UTC", text):
        if (_iso(*m.group(1, 2, 3)), f"{m.group(4)}:{m.group(5)}") not in a.stamps:
            issues.append(f"timestamp {m.group()}")
    text = _re.sub(rf"({MRE}) (\d{{1,2}}), (\d{{4}}) at (\d{{2}}):(\d{{2}}) UTC", " ", text)
    for m in _re.finditer(rf"({MRE}) (\d{{1,2}}), (\d{{4}})", text):
        if _iso(*m.group(1, 2, 3)) not in a.dates:
            issues.append(f"date {m.group()}")
    text = _re.sub(rf"({MRE}) (\d{{1,2}}), (\d{{4}})", " ", text)
    for m in _re.finditer(rf"({MRE}) (\d{{4}})", text):
        if f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}" not in {d[:7] for d in a.dates}:
            issues.append(f"month {m.group()}")
    text = _re.sub(rf"({MRE}) (\d{{4}})", " ", text)
    for m in _re.finditer(r"\b(\d{4}-Q[1-4]|FY\d{4})\b", text):
        if m.group() not in a.strings:
            issues.append(f"period {m.group()}")
    text = _re.sub(r"\b(\d{4}-Q[1-4]|FY\d{4})\b", " ", text)
    for m in ISO_D.finditer(text):
        if m.group() not in a.dates:
            issues.append(f"date {m.group()}")
    text = ISO_D.sub(" ", text)
    for m in _re.finditer(r"\b[A-Za-z]+\d+\w*\b", text):
        if not any(m.group().lower() in x.lower() for x in a.strings):
            issues.append(f"code {m.group()}")
    text = _re.sub(r"\b[A-Za-z]+\d+\w*\b", " ", text)
    for m in NUM.finditer(text):
        if float(m.group(1).replace(",", "")) not in a.numbers:
            issues.append(f"number {m.group()}")
    if "—" in body or "–" in body:
        issues.append("long dash in generated text")
    return issues


def stated_forms(value, names):
    """Ways a declared fact value may appear in a body."""
    if value is None or value == [] or value == "":
        return None
    if isinstance(value, bool):
        return [["yes", "true"] if value else ["no", "false"]]
    if isinstance(value, (int, float)):
        return [[f"{value:,}", f"{value:g}", str(value)]]
    if isinstance(value, dict):
        if "item" in value:
            if value["item"] == "headcount":
                return [[f"{int(value['amount']):,}"]]
            return stated_forms({"amount": value["amount"], "currency": value["currency"]}, names)
        if "amount" in value and "currency" in value:
            sym = {"USD": "$", "GBP": "£", "EUR": "€"}[value["currency"]]
            a = value["amount"]
            forms = [f"{sym}{a:,.2f}" if isinstance(a, float) and not a.is_integer() else f"{sym}{int(a):,}"]
            return [forms + (["free"] if a == 0 else [])]
        if "name" in value and "title" in value:
            return [[value["name"]], [value["title"]] if value["title"] else ["", ""]]
        if "monthly_fee" in value:
            return stated_forms(value["monthly_fee"], names)
        if "rule" in value:
            v = value["value"]
            return [[str(v).lower()]] if isinstance(v, bool) else stated_forms(v, names)
        if "metric" in value:
            return stated_forms(value["value"], names)
        if "feature" in value:
            return [[value["target_quarter"]], [value["feature"]]]
        if "award_code" in value:
            return None
    if isinstance(value, list):
        out = []
        for v in value:
            f = stated_forms(v, names)
            if f:
                out += f
        return out or None
    if isinstance(value, str):
        if ISO_DT.fullmatch(value) or ISO_D.fullmatch(value):
            d = _date.fromisoformat(value[:10])
            return [[f"{MONTHS[d.month - 1]} {d.day}, {d.year}", f"{MONTHS[d.month - 1]} {d.year}"]]
        if ID_RE.fullmatch(value):
            return [[value] + ([names[value]] if value in names else [])]
        return [[value, value.replace("_", " ")]]
    return None


def section_g(rep, data):
    plan = {p["front_matter"]["document_version_id"]: p for p in data["plan"]}
    expected = {S / f"documents/{p['front_matter']['source_system']}/{p['front_matter']['document_id']}/v{p['front_matter']['version']}.md": dv
                for dv, p in plan.items()}
    on_disk = set((S / "documents").rglob("*.md"))
    rep.check("G", "every planned document version exists as a file, no extra files",
              [f"missing {p}" for p in sorted(set(expected) - on_disk)] + [f"unexpected {p}" for p in sorted(on_disk - set(expected))],
              f"{len(on_disk)} files")

    # entity versions over time, to know what each document could see when it was written
    timeline = defaultdict(list)
    for otype, rows in data["entities"].items():
        for r in rows:
            timeline[r[PK[otype]]].append((0, r))
    for r in data["access"]["tenants"]:
        timeline[r["tenant_id"]].append((0, r))
    insert_seq = {}
    for e in sorted({e["event_id"]: e for e in data["events"]}.values(), key=lambda e: e["sequence"]):
        if e["object_type"] == "document_version":
            if e["operation"] == "insert":
                insert_seq[e["object_id"]] = e["sequence"]
        elif e["after"] is not None and e["object_type"] in PK:
            timeline[e["object_id"]].append((e["sequence"], e["after"]))
    names = {}
    for ref, versions in timeline.items():
        r = versions[-1][1]
        label = f"{r['first_name']} {r['last_name']}" if "first_name" in r else r.get("display_name") or r.get("tier_name") or r.get("name")
        if label:
            names[ref] = label

    def row_at(ref, seq):
        rows = [r for s_, r in timeline.get(ref, []) if s_ < seq or s_ == 0]
        return rows[-1] if rows else None

    fm_bad, quoted, hash_bad, fact_bad, missing_bad = [], 0, [], [], []
    generated = 0
    for path, dvid in sorted(expected.items()):
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        try:
            fm_text, body = split_document(raw)
            fm = yaml.safe_load(fm_text)
        except Exception as exc:                      # noqa: BLE001 - report any parse failure
            fm_bad.append(f"{dvid}: cannot parse ({exc})")
            continue
        p = plan[dvid]
        for k in DATE_FIELDS:
            if fm.get(k) is not None:
                quoted += 1
                if not isinstance(fm[k], str):
                    fm_bad.append(f"{dvid}: {k} parsed as {type(fm[k]).__name__}, not a quoted string")
        if fm != p["front_matter"]:
            diff = [k for k in set(fm) | set(p["front_matter"]) if fm.get(k) != p["front_matter"].get(k)]
            fm_bad.append(f"{dvid}: front matter differs from the approved plan in {sorted(diff)}")
        if sha256(body) != fm.get("content_sha256"):
            hash_bad.append(f"{dvid}: body hash differs from front matter")
        if p["body"]["mode"] != "generated":
            if body != body_from_spec(p["body"], plan):
                hash_bad.append(f"{dvid}: seeded body differs from its KB recipe")
            continue
        generated += 1
        seq = insert_seq.get(dvid, 0)
        refs = set(fm["source_record_ids"]) | set(fm["subject_entities"]) | {f["entity"] for f in p["facts"]}
        allowed = Allowed()
        for ref in refs:
            allowed.ids.add(ref)
            r = row_at(ref, seq) if seq else row_at(ref, 1)
            if r is None:
                fact_bad.append(f"{dvid}: referenced {ref} did not exist when the document was written")
                continue
            allowed.harvest(r)
        for issue in unsupported(body, allowed):
            fact_bad.append(f"{dvid}: unsupported {issue}")
        low = body.lower()
        for f in p["facts"]:
            r = row_at(f["entity"], seq) if seq else row_at(f["entity"], 1)
            for field in f["fields"]:
                groups = stated_forms((r or {}).get(field), names)
                for options in groups or []:
                    if not any(o.lower() in low for o in options if o):
                        missing_bad.append(f"{dvid}: declared fact {f['entity']}.{field} not stated (expected one of {options[:2]})")
    rep.check("G", "front matter parses, equals the approved plan, every date a quoted string", fm_bad, f"{quoted} date fields checked")
    rep.check("G", "body hashes match front matter; seeded bodies equal their KB recipe", hash_bad)
    rep.check("G", "12  generated bodies: every ID, date, time, period, code and number traces to a referenced row", fact_bad,
              f"{generated} generated documents")
    rep.check("G", "12  generated bodies state every fact they declare", missing_bad)
    inj = {a["document_version_id"] for a in data["gt"]["document_annotations"] if a["annotation_type"] == "prompt_injection"}
    marker = _re.compile(r"ignore all previous instructions|disregard your restrictions|administrator mode", _re.I)
    tickets = {dv: (S / f"documents/support/{plan[dv]['front_matter']['document_id']}/v{plan[dv]['front_matter']['version']}.md").read_text()
               for dv in plan if plan[dv]["front_matter"]["document_type"] == "support_ticket"}
    rep.check("G", "planted injections exactly where annotated", [f"{dv}: injection {'missing' if dv in inj else 'unexpected'}"
                                                              for dv, t in tickets.items() if bool(marker.search(t)) != (dv in inj)],
              f"{len(inj)} injected tickets")


def load():
    data = {"entities": {otype: jl(S / "entities" / f"{fname}.jsonl") for fname, otype in ENTITY_FILES.items()},
            "access": {n: jl(S / "access_control" / f"{n}.jsonl") for n in ("tenants", "principals", "groups", "memberships")},
            "policy": yaml.safe_load((S / "access_control" / "policies.yaml").read_text()),
            "edges": jl(S / "relationships" / "edges.jsonl"), "events": jl(S / "cdc" / "events.jsonl"),
            "manifest": json.loads((S / "cdc" / "manifest.json").read_text()), "plan": jl(S / "_build" / "document_plan.jsonl"),
            "gt": {n: jl(S / "ground_truth" / f"{n}.jsonl") for n in ("personas", "access_matrix", "versioned_facts", "checkpoints", "document_annotations")}}
    return data


def main():
    data = load()
    rep = Report()
    V = load_validators()
    print("A  schema validation"); section_a(rep, V, data)
    print("B  seed preservation"); section_b(rep, data)
    print("C  CDC replay")
    snaps, deleted, stats = replay(data)
    as_of = {c["checkpoint_id"]: c["as_of"] for c in data["gt"]["checkpoints"]}
    anomalies = [a for c in data["gt"]["checkpoints"] for a in c["cdc_anomalies"]]
    rep.check("C", "replay handles every planted anomaly", [] if stats["duplicate_ignored"] == sum(a["anomaly_type"] == "duplicate_delivery" for a in anomalies)
              and stats["stale_discarded"] == sum(a["anomaly_type"] == "out_of_order" for a in anomalies) else [f"replay stats {dict(stats)} vs anomalies {anomalies}"],
              f"{dict(stats)}")
    print("D  cross-record invariants"); section_d(rep, data, snaps, deleted, as_of)
    print("E  independent authorization"); section_e(rep, data, snaps, deleted, as_of)
    print("F  ground truth"); section_f(rep, data, snaps, deleted, as_of)
    print("G  document files"); section_g(rep, data)
    print("\nRESULTS")
    for section, name, n, detail in rep.results:
        print(f"  [{section}] {'PASS' if n == 0 else 'FAIL'}  {name}" + (f"   ({detail})" if detail else "") + (f"   <{n} failures>" if n else ""))
    total = sum(n for *_, n, _ in rep.results)
    print(f"\n{len(rep.results)} checks, {sum(1 for r in rep.results if r[2] == 0)} passed, {total} failures")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()

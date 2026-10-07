"""Build the Insurellm source world: T0 snapshot, four change batches, document plan.

    python -m datagen.build_world      (from the GovernedRAG root)

Reads seed/kb_seed.json (verified KB facts), world_config.py and content_config.py.
Writes entities/, access_control/{tenants,principals,groups,memberships}.jsonl,
relationships/edges.jsonl, cdc/, ground_truth/ and _build/document_plan.jsonl.
No document bodies are written in this phase.
"""

import copy
import json
import re
from datetime import date, timedelta

import yaml

from . import content_config as K
from . import world_config as W
from .docplan import DocumentPlanner, body_from_spec, employee_split, front_matter_block, whole_file
from .ground_truth import build_ground_truth
from .render import render
from .kb import KB_ROOT, SEED_DIR, SOURCE_ROOT
from .store import PK, Store, day_before, edge_catalog, plus_seconds

SCHEMA_DIR = SOURCE_ROOT / "schema"
PLURAL = {"location": "locations", "department": "departments", "team": "teams", "employee": "employees",
          "compensation": "compensation", "performance_review": "performance_reviews", "product": "products",
          "product_tier": "product_tiers", "customer": "customers", "contract": "contracts", "contract_version": "contract_versions",
          "project": "projects", "policy": "policies", "policy_version": "policy_versions", "incident": "incidents",
          "support_ticket": "support_tickets", "financial_record": "financial_records"}
TIMEZONES = {"san-francisco": "America/Los_Angeles", "new-york": "America/New_York", "austin": "America/Chicago",
             "chicago": "America/Chicago", "denver": "America/Denver", "remote-us": "America/Chicago"}
CITY_TO_LOCATION = {"San Francisco": "san-francisco", "New York": "new-york", "Austin": "austin", "Chicago": "chicago", "Denver": "denver"}
TIER_SUFFIX = {"Rellm": "Plan"}


def ts(d, hh=9, mm=0):
    return f"{d}T{hh:02d}:{mm:02d}:00Z"


def money(amount, currency="USD"):
    return None if amount is None else {"amount": amount, "currency": currency}


def term_end(start, months):
    s = date.fromisoformat(start)
    y, m = divmod(s.month - 1 + months, 12)
    try:
        nxt = s.replace(year=s.year + y, month=m + 1)
    except ValueError:
        nxt = date(s.year + y, m + 1, 28)
    return (nxt - timedelta(days=1)).isoformat()


def contract_month(start, d):
    """1-based contract month containing date d, for months anchored on the start day."""
    a, b = date.fromisoformat(start), date.fromisoformat(d)
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0) + 1


def val(f):
    return f.get("value") if isinstance(f, dict) else None


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class World:
    def __init__(self):
        self.seed = json.loads((SEED_DIR / "kb_seed.json").read_text(encoding="utf-8"))
        self.reg = json.loads((SEED_DIR / "id_registry.json").read_text(encoding="utf-8"))
        self.policy = yaml.safe_load((SOURCE_ROOT / "access_control" / "policies.yaml").read_text(encoding="utf-8"))
        self.store = Store(edge_catalog(SCHEMA_DIR))
        self.docs = DocumentPlanner(self.policy)
        self.docs.renderer = lambda entry: render(self, entry)
        self.emp = dict(self.reg["employees"])
        self.prod = dict(self.reg["products"])
        self.cust = dict(self.reg["customers"])
        self.con = dict(self.reg["contracts"])
        self.loc = dict(self.reg["locations"])
        self.dept = {code: v[0] for code, v in W.DEPARTMENTS.items()}
        self.dept_code = {v[0]: code for code, v in W.DEPARTMENTS.items()}
        self.team = {key: v[0] for key, v in W.TEAMS.items()}
        self.tier = {}
        self.counters = {}
        self.minutes = {}
        self.ops = []
        self.t0_snapshot = None
        self.checkpoints = []
        self.doc_of = {}            # logical key -> document_id
        self.cus_principal = {}     # (customer, role) -> principal id
        self.membership_open = {}   # (principal, group) -> membership id
        self.anomalies = []

    # ------------------------------------------------------------------ small helpers
    def nid(self, prefix, width):
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]:0{width}d}"

    def at(self, d):
        """Monotonic timestamp on date d: 09:00, 09:01, ..."""
        n = self.minutes.get(d, 0)
        self.minutes[d] = n + 1
        return ts(d, 9 + n // 60, n % 60)

    def pid(self, name):
        return "P-" + self.emp[name]

    def schedule(self, d, fn):
        self.ops.append((d, len(self.ops), fn))

    def run_batch(self, batch_id):
        self.store.begin_batch(batch_id)
        for d, _, fn in sorted(self.ops):
            fn(self.at(d))
        self.ops = []
        start, end = next((b[3], b[4]) for b in W.BATCHES if b[0] == batch_id)
        self.checkpoints.append({"checkpoint_id": "CP-" + batch_id.replace("BATCH-", "B"), "batch_id": batch_id, "as_of": end,
                                 "tables": self.store.snapshot(), "edges": copy.deepcopy(self.store.edges)})

    def envelope(self, source_system, label, created, origin="generated", tenant="T-INSURELLM", updated=None):
        return {"schema_version": "1.0", "tenant_id": tenant, "source_system": source_system, "sensitivity_label": label,
                "record_status": "active", "created_at": created, "updated_at": updated or created, "origin": origin}

    def head_of(self, code):
        dept = self.store.tables["department"].get(self.dept[code])
        return dept["head_employee_id"] if dept else self.emp["Avery Lancaster"]

    def owner(self, code):
        """(department id, owner employee id) for documents owned by a department, falling back to the CEO."""
        if self.dept[code] in self.store.tables["department"]:
            return self.dept[code], self.head_of(code)
        return self.dept["executive"], self.emp["Avery Lancaster"]

    def add_doc(self, when, *, t0=False, **kw):
        entry = self.docs.new_version(**kw)
        front = entry["front_matter"]
        row = {"front_matter": front, "body_path": self.docs.body_path(front)}
        if t0:
            self.store.t0("document_version", row, kw["valid_from"])
        else:
            if front["supersedes"]:
                self.supersede_doc(front["supersedes"], when, front["valid_from"])
            self.store.insert("document_version", row, when, self.pid_for_emp(front["source_owner_id"]), "new_record" if front["version"] == 1 else "amendment")
        return front

    def pid_for_emp(self, emp_id):
        return "P-" + emp_id

    def supersede_doc(self, dvid, when, successor_valid_from):
        fm = self.store.get("document_version", dvid)["front_matter"]
        valid_to = day_before(successor_valid_from) if successor_valid_from > fm["valid_from"] else fm["valid_from"]
        self.store.update("document_version", dvid, {"status": "superseded", "valid_to": valid_to}, when,
                          self.pid_for_emp(fm["source_owner_id"]), "status_change", nested="front_matter")

    def set_doc_status(self, dvid, status, when, actor, reason):
        self.store.update("document_version", dvid, {"status": status}, when, actor, reason, nested="front_matter")

    def latest_version(self, document_id):
        versions = [k for k in self.store.tables["document_version"] if k.startswith(document_id + "@")]
        return max(versions, key=lambda k: int(k.split("@v")[1])) if versions else None

    # ------------------------------------------------------------------ memberships
    def desired_groups(self, principal):
        if principal["principal_status"] != "active":
            return {}
        if principal["principal_type"] == "service_account":
            return {g: "service_binding" for b in self.policy["service_bindings"] if b["principal_id"] == principal["principal_id"]
                    for g in b["groups"]}
        if principal["principal_type"] != "employee":
            return {}
        e = self.store.get("employee", principal["employee_id"])
        if e["employment_status"] == "terminated":
            return {}
        out = {}
        code = self.dept_code[e["department_id"]]
        for g in self.policy["groups"]:
            r = g["membership_rule"]
            if e["employment_type"] in r["exclude_employment_types"]:
                continue
            if (r["kind"] == "department_members" and r["department_code"] == code) \
                    or (r["kind"] == "job_levels" and e["job_level"] in r["levels"]) \
                    or (r["kind"] == "job_titles" and e["job_title"] in r["titles"]):
                out[g["group_id"]] = "department_default" if r["kind"] == "department_members" else "role_based"
        return out

    def sync_memberships(self, when=None, start_dates=None):
        """Open and close memberships so they match the policy rules right now."""
        granted_by = self.pid_for_emp(self.head_of("hr")) if when else self.pid("Avery Lancaster")
        for p in sorted(self.store.tables["principal"].values(), key=lambda r: r["principal_id"]):
            want = self.desired_groups(p)
            have = {g for (pid, g) in self.membership_open if pid == p["principal_id"]}
            for g in sorted(have - set(want)):
                mid = self.membership_open.pop((p["principal_id"], g))
                self.store.update("membership", mid, {"valid_to": day_before(when[:10])}, when, granted_by, "access_change")
            for g in sorted(set(want) - have):
                mid = self.nid("MEM", 5)
                row = {"schema_version": "1.0", "membership_id": mid, "principal_id": p["principal_id"], "group_id": g,
                       "membership_role": "member", "valid_from": (start_dates or {}).get(p["principal_id"], (when or W.T0)[:10]),
                       "valid_to": None, "granted_by": granted_by, "grant_reason": want[g]}
                self.membership_open[(p["principal_id"], g)] = mid
                if when:
                    self.store.insert("membership", row, when, granted_by, "access_change")
                else:
                    self.store.t0("membership", row, row["valid_from"])

    # ------------------------------------------------------------------ T0: seeded entities
    def build_t0(self):
        self._t0_locations()
        self._t0_org()
        self._t0_employees()
        self._t0_products()
        self._t0_customers_and_contracts()
        self._t0_access()
        self._t0_content()
        self._t0_documents()
        self.t0_snapshot = {"tables": self.store.snapshot(), "edges": copy.deepcopy(self.store.edges)}
        self.checkpoints.append({"checkpoint_id": "CP-T0", "batch_id": "BATCH-00", "as_of": W.T0,
                                 "tables": self.t0_snapshot["tables"], "edges": self.t0_snapshot["edges"]})

    def _t0_locations(self):
        for loc in self.seed["locations"]:
            row = {**self.envelope("hris", "internal", W.ASSEMBLED_AT, origin="kb_seed"), "location_id": loc["id"], "name": loc["name"],
                   "location_type": loc["location_type"], "city": loc["city"] or "Remote", "state_or_province": loc["state"],
                   "country": "US", "region": "us", "timezone": TIMEZONES[loc["key"]], "opened_on": None}
            self.store.t0("location", row, W.T0_DATE)

    def _t0_org(self):
        for code, (did, name, cc, batch) in W.DEPARTMENTS.items():
            if batch != "BATCH-00":
                continue
            row = {**self.envelope("hris", "internal", W.ASSEMBLED_AT), "department_id": did, "name": name, "code": code,
                   "head_employee_id": self.emp[W.T0_DEPARTMENT_HEADS[code]], "parent_department_id": None,
                   "default_group_id": f"GRP-{code}", "cost_center": cc}
            self.store.t0("department", row, W.T0_DATE)
        for key, (tid, name, code, lead, loc, products, batch) in W.TEAMS.items():
            if batch == "BATCH-00":
                self.store.t0("team", self._team_row(key, W.ASSEMBLED_AT), W.T0_DATE)

    def _team_row(self, key, created):
        tid, name, code, lead, loc, products, _ = W.TEAMS[key]
        return {**self.envelope("hris", "internal", created), "team_id": tid, "name": name, "department_id": self.dept[code],
                "lead_employee_id": self.emp[lead], "primary_location_id": self.loc[loc], "owned_product_ids": [self.prod[p] for p in products]}

    def _manager(self, name, code, team_key):
        if name == "Avery Lancaster":
            return None
        if team_key and W.TEAMS[team_key][3] != name:
            return W.TEAMS[team_key][3]
        head = W.T0_DEPARTMENT_HEADS[code]
        return head if head != name else "Avery Lancaster"

    def _t0_employees(self):
        for e in self.seed["employees"]:
            name = e["full_name"]["value"]
            code, team_key, level = e["org"]["department_code"], e["org"]["team_key"], e["org"]["job_level"]
            loc = e["location"]
            remote = loc["arrangement"]["value"] == "remote"
            city = loc["city"]["value"]
            hire, precision = val(e["hire"]), e["hire"]["kind"]
            hire_date = hire + ("-01" * (3 - len(hire.split("-"))))
            first, last = " ".join(name.split()[:-1]), name.split()[-1]
            email = re.sub(r"\.+", ".", re.sub(r"[^a-z.]", "", f"{first}.{last}".lower().replace(" ", "."))) + "@insurellm.example"
            mgr = self._manager(name, code, team_key)
            row = {**self.envelope("hris", "internal", ts(hire_date), origin="kb_seed", updated=W.ASSEMBLED_AT),
                   "employee_id": e["id"], "first_name": first, "last_name": last, "preferred_name": None, "work_email": email,
                   "date_of_birth": val(e["date_of_birth"]), "job_title": val(e["job_title"]), "job_level": level,
                   "department_id": self.dept[code], "team_id": self.team[team_key] if team_key else None,
                   "manager_id": self.emp[mgr] if mgr else None,
                   "location_id": self.loc["remote-us"] if remote else self.loc[CITY_TO_LOCATION[city.split(",")[0]]],
                   "work_arrangement": "remote" if remote else "hybrid", "remote_city": city if remote else None,
                   "employment_type": "full_time", "employment_status": "active", "hire_date": hire_date,
                   "hire_date_precision": precision if precision in ("month", "year") else "day", "termination_date": None,
                   "recognitions": [{"award_code": r["award_code"], "award_name": val(r["award_name"]), "year": val(r["year"])} for r in e["recognitions"]]}
            self.store.t0("employee", row, hire_date)
            self._t0_compensation(e, row)
            self._t0_reviews(e, row)

    def _period_start(self, period):
        p = str(period)
        return (p + "-01-01" if len(p) == 4 else p + "-01"), ("year" if len(p) == 4 else "month")

    def _t0_compensation(self, e, emp_row):
        entries = []
        for c in e["compensation_history"]:
            start, precision = self._period_start(val(c["period"]))
            entries.append((start, precision, val(c["base_salary"]), val(c["bonus"])))
        entries.sort(key=lambda x: x[0])
        salaried = [x for x in entries if x[2] is not None]
        rows = []
        for i, (start, precision, base, bonus) in enumerate(salaried):
            end = day_before(salaried[i + 1][0]) if i + 1 < len(salaried) else None
            rows.append({**self.envelope("hris", "restricted", ts(start), origin="kb_seed", updated=W.ASSEMBLED_AT),
                         "compensation_id": self.nid("COMP", 4), "employee_id": emp_row["employee_id"], "effective_from": start,
                         "effective_from_precision": precision, "effective_to": end, "job_title_at_time": None,
                         "base_salary": money(base), "bonus_target_pct": None, "bonus_paid": money(bonus), "change_reason": None, "approved_by": None})
        for start, _, base, bonus in entries:                      # bonus-only entries attach to the row in force
            if base is None and bonus is not None:
                row = max((r for r in rows if r["effective_from"] <= start), key=lambda r: r["effective_from"])
                row["bonus_paid"] = row["bonus_paid"] or money(bonus)
        for r in rows:
            self.store.t0("compensation", r, r["effective_from"])

    def _t0_reviews(self, e, emp_row):
        for r in e["performance_history"]:
            rating = val(r["rating"])
            row = {**self.envelope("hris", "confidential", W.ASSEMBLED_AT, origin="kb_seed"), "review_id": self.nid("PRV", 4),
                   "employee_id": emp_row["employee_id"], "review_year": val(r["year"]), "reviewer_id": None,
                   "rating_label": rating if isinstance(rating, str) else None,
                   "rating_score": rating if isinstance(rating, float) else None,
                   "highlight_codes": [], "metrics": [], "finalized_on": None}
            self.store.t0("performance_review", row, W.T0_DATE)

    def _t0_products(self):
        taglines = self.seed["company"]["product_taglines"]
        for p in self.seed["products"]:
            name = p["name"]["value"]
            tech, owner, design = W.PRODUCT_LEADS[name]
            team = next(k for k, v in W.TEAMS.items() if name in v[5])
            row = {**self.envelope("pm", "internal", W.ASSEMBLED_AT, origin="kb_seed"), "product_id": p["id"], "name": name,
                   "category": W.PRODUCT_CATEGORY[name], "tagline": taglines[name]["value"], "launch_date": None,
                   "launch_order": 1 if name == self.seed["company"]["first_product"]["value"] else None, "lifecycle_status": "active",
                   "retired_on": None, "tech_lead_id": self.emp[tech], "product_owner_id": self.emp[owner],
                   "design_lead_id": self.emp[design] if design else None, "owning_team_id": self.team[team],
                   "roadmap_items": [{"feature": val(r["feature"])[:300], "target_quarter": val(r["target_period"])} for r in p["roadmap"]]}
            self.store.t0("product", row, W.T0_DATE)
            for rank, t in enumerate(p["tiers"], 1):
                tname = t["tier_name"]["value"]
                self.tier[(name, tname)] = t["id"]
                row = {**self.envelope("pm", "public", W.ASSEMBLED_AT, origin="kb_seed"), "tier_id": t["id"], "product_id": p["id"],
                       "tier_name": tname, "tier_rank": rank, "monthly_list_price": money(val(t["price"])),
                       "pricing_model": t["pricing_model"]["value"], "audience": t["audience"], "price_unit": t["price_unit"],
                       "included_capacity": [], "features": [], "valid_from": None, "valid_to": None}
                self.store.t0("product_tier", row, W.T0_DATE)

    def tier_for(self, product, tier_name):
        if tier_name is None:
            return None
        if (product, tier_name) in self.tier:
            return self.tier[(product, tier_name)]
        return self.tier.get((product, f"{tier_name} {TIER_SUFFIX.get(product, 'Tier')}"))

    def account_team(self, product, tier_name):
        am = next(n for n, prods in W.ACCOUNT_MANAGERS.items() if product in prods)
        team = [am, "Marcus Johnson"] + ([W.ENTERPRISE_SE] if tier_name and tier_name.startswith("Enterprise") and am != W.ENTERPRISE_SE else [])
        return am, [self.emp[n] for n in dict.fromkeys(team)]

    def _t0_customers_and_contracts(self):
        for c in self.seed["contracts"]:
            name, product = c["customer_display_name"]["value"], c["product"]["value"]
            tier_name = val(c["tier"])
            am, team = self.account_team(product, tier_name)
            since = val(c["signed_on"]) or val(c["effective_from"])
            portal = name in W.PORTAL_CUSTOMERS
            cid = c["customer_id"]
            row = {**self.envelope("crm", "confidential", ts(since) if since else W.ASSEMBLED_AT, origin="kb_seed"),
                   "customer_id": cid, "legal_name": val(c["legal_name"]) or name, "display_name": name, "segment": W.SEGMENT[product],
                   "hq_city": None, "country": None, "region": None, "account_manager_id": self.emp[am],
                   "customer_success_manager_id": self.emp["Marcus Johnson"], "account_team_ids": team, "customer_since": since,
                   "customer_status": "active", "has_portal_tenant": portal, "portal_tenant_id": "T-CUST-" + cid[-3:] if portal else None,
                   "is_public_reference": name in W.PUBLIC_REFERENCES}
            self.store.t0("customer", row, since or W.T0_DATE)
            self._t0_contract(c, name, product, tier_name)

    def _t0_contract(self, c, name, product, tier_name):
        signed, effective = val(c["signed_on"]), val(c["effective_from"]) or val(c["signed_on"])
        months, end = val(c["term_months"]), val(c["term_end"])
        if end is None and effective and months:
            end = term_end(effective, months)
        sig, csig = c["insurellm_signatory"], c["customer_signatory"]
        schedule = [{"from_month": r["from_month"], "to_month": r["to_month"], "monthly_fee": money(val(r["monthly_fee"]))} for r in c["fee_schedule"]]
        fee = val(c["monthly_fee"]) if val(c["monthly_fee"]) is not None else (schedule[0]["monthly_fee"]["amount"] if schedule else None)
        created = ts(signed or effective) if (signed or effective) else W.ASSEMBLED_AT
        ctype = "marketplace_listing" if product == "Markellm" else "enterprise_license" if (tier_name or "").startswith("Enterprise") else "subscription"
        header = {**self.envelope("clm", "confidential", created, origin="kb_seed"), "contract_id": c["id"],
                  "contract_number": val(c["contract_number"]), "customer_id": c["customer_id"], "primary_product_id": c["product_id"],
                  "contract_type": ctype, "legal_owner_id": None, "insurellm_signatory_id": None,
                  "insurellm_signatory_as_printed": {"name": sig["name"]["value"], "title": sig["title"]["value"]} if "name" in sig else None,
                  "customer_signatory": {"name": csig["name"]["value"], "title": csig["title"]["value"]} if "name" in csig else None,
                  "signed_on": signed, "current_version": 1, "contract_status": "active"}
        self.store.t0("contract", header, (signed or effective or W.T0_DATE))
        unit = {"members": "members", "policies": "policies", "claims": "claims", "states": "states"}
        period = {"projected_claims_year_1": "year_1", "baseline_claims_per_year": "year"}
        version = {**self.envelope("clm", "confidential", created, origin="kb_seed"), "contract_version_id": f"{c['id']}@v1",
                   "contract_id": c["id"], "version": 1, "change_type": "original", "supersedes": None, "version_status": "current",
                   "effective_from": effective, "term_end": end, "term_months": months, "auto_renew": True if val(c["auto_renew"]) else None,
                   "renewal_term_months": None, "non_renewal_notice_days": val(c["renewal_notice_days"]),
                   "termination_notice_days": val(c["termination_notice_days"]), "max_annual_price_increase_pct": None,
                   "tier_id": self.tier_for(product, tier_name), "monthly_fee": money(fee), "fee_schedule": schedule,
                   "setup_fee": money(val(c["setup_fee"])), "per_lead_fee": money(val(c["per_lead_fee"])),
                   "total_contract_value": money(val(c["total_value"])), "payment_terms": None, "user_licenses": val(c["user_licenses"]),
                   "training_seats": None,
                   "volume_commitments": [{"metric": v["metric"], "value": val(v["value"]), "unit": unit[v["unit"]],
                                           "period": period.get(v["metric"], "contract")} for v in c["volumes"]],
                   "scope_product_ids": [c["product_id"]], "support_level": None, "change_summary": None, "approved_by": None}
        self.store.t0("contract_version", version, (effective or W.T0_DATE))

    # ------------------------------------------------------------------ T0: access control
    def _t0_access(self):
        self.store.t0("tenant", {"schema_version": "1.0", "tenant_id": "T-INSURELLM", "tenant_type": "internal", "name": "Insurellm",
                                 "customer_id": None, "region": "us", "tenant_status": "active",
                                 "created_at": "2015-03-02T09:00:00Z", "updated_at": W.ASSEMBLED_AT}, W.T0_DATE)
        for c in sorted(self.store.rows("customer"), key=lambda r: r["customer_id"]):
            if c["has_portal_tenant"]:
                self._tenant_and_users(c, None)
        for e in sorted(self.store.rows("employee"), key=lambda r: r["employee_id"]):
            self.store.t0("principal", self._employee_principal(e, e["created_at"]), e["hire_date"])
        self.store.t0("principal", {"schema_version": "1.0", "principal_id": "P-SVC-001", "principal_type": "service_account",
                                    "display_name": "Baseline evaluator", "email": "baseline-eval@svc.insurellm.example",
                                    "home_tenant_id": "T-INSURELLM", "employee_id": None, "customer_id": None, "customer_role": None,
                                    "service_scopes": ["T-INSURELLM"], "principal_status": "active", "created_at": W.ASSEMBLED_AT,
                                    "disabled_at": None}, W.T0_DATE)
        for g in self.policy["groups"]:
            dept_code = g["department_code"]
            owner = self.pid_for_emp(self.head_of(dept_code)) if dept_code and self.dept.get(dept_code) in self.store.tables["department"] else self.pid("Avery Lancaster")
            self.store.t0("group", {"schema_version": "1.0", "group_id": g["group_id"], "name": g["name"], "group_type": g["group_type"],
                                    "tenant_id": "T-INSURELLM", "department_id": self.dept.get(dept_code) if g["group_type"] == "department" else None,
                                    "owner_principal_id": owner, "description": g["description"][:300], "max_label": g["max_label"],
                                    "group_status": "active", "created_at": W.ASSEMBLED_AT}, W.T0_DATE)
        starts = {p["principal_id"]: (self.store.get("employee", p["employee_id"])["hire_date"] if p["employee_id"] else W.T0_DATE)
                  for p in self.store.rows("principal")}
        self.sync_memberships(None, starts)

    def _employee_principal(self, e, created):
        return {"schema_version": "1.0", "principal_id": "P-" + e["employee_id"], "principal_type": "employee",
                "display_name": f"{e['first_name']} {e['last_name']}", "email": e["work_email"], "home_tenant_id": "T-INSURELLM",
                "employee_id": e["employee_id"], "customer_id": None, "customer_role": None, "service_scopes": [],
                "principal_status": "active", "created_at": created, "disabled_at": None}

    def _tenant_and_users(self, customer, when):
        name = customer["display_name"]
        tenant = {"schema_version": "1.0", "tenant_id": customer["portal_tenant_id"], "tenant_type": "customer", "name": f"{name} portal",
                  "customer_id": customer["customer_id"], "region": customer["region"] or "us", "tenant_status": "active",
                  "created_at": when or W.ASSEMBLED_AT, "updated_at": when or W.ASSEMBLED_AT}
        domain = slug(name.split()[0]) + ".example"
        users = []
        for person, role, local in W.CUSTOMER_USERS[name]:
            pid = self.nid("P-CUS", 4)
            self.cus_principal[(name, role)] = pid
            users.append({"schema_version": "1.0", "principal_id": pid, "principal_type": "customer_user", "display_name": person,
                          "email": f"{local}@{domain}", "home_tenant_id": customer["portal_tenant_id"], "employee_id": None,
                          "customer_id": customer["customer_id"], "customer_role": role, "service_scopes": [],
                          "principal_status": "active", "created_at": when or W.ASSEMBLED_AT, "disabled_at": None})
        if when is None:
            self.store.t0("tenant", tenant, W.T0_DATE)
            for u in users:
                self.store.t0("principal", u, W.T0_DATE)
        else:
            actor = self.pid_for_emp(customer["customer_success_manager_id"])
            self.store.insert("tenant", tenant, when, actor, "new_record")
            for u in users:
                self.store.insert("principal", u, when, actor, "new_record")

    # ------------------------------------------------------------------ T0: generated content entities
    def _t0_content(self):
        self.project = {}
        for spec in K.PROJECTS:
            self.project[spec[0]] = self._project_row(spec)
            self.store.t0("project", self.project[spec[0]], spec[11])
        self.policy_rows = {}
        for spec in K.POLICIES:
            pol, ver = self._policy_rows(spec)
            self.policy_rows[spec[0]] = pol["policy_id"]
            self.store.t0("policy", pol, W.T0_DATE)
            self.store.t0("policy_version", ver, ver["effective_from"])
        self.incident = {}
        for spec in K.INCIDENTS:
            if spec[-1] == "BATCH-00":
                self.incident[spec[0]] = self._incident_row(spec)
                self.store.t0("incident", self.incident[spec[0]], spec[5][:10])
        self.tickets = []
        for spec in K.TICKETS:
            if spec[-1] == "BATCH-00":
                row = self._ticket_row(spec)
                self.tickets.append((spec, row))
                self.store.t0("support_ticket", row, spec[5][:10])
        self.fin = {}
        for period, rtype in [("2024-Q4", "quarterly_pnl"), ("2025-Q1", "quarterly_pnl"), ("2025-Q1", "receivables_summary"), ("2025-Q1", "board_metrics")]:
            row = self._financial_row(rtype, period, W.T0_DATE, None)
            self.fin[(rtype, period)] = row
            self.store.t0("financial_record", row, W.T0_DATE)
        for code, (_, _, _, batch) in W.DEPARTMENTS.items():
            if batch == "BATCH-00":
                row = self._financial_row("department_budget", "FY2025", W.T0_DATE, code)
                self.fin[("department_budget", code)] = row
                self.store.t0("financial_record", row, W.T0_DATE)

    def _project_row(self, spec):
        key, name, codename, ptype, team, sponsor, lead, members, products, customers, status, start, target, done, budget, label = spec
        return {**self.envelope("pm", label, ts(start)), "project_id": self.nid("PROJ", 3), "name": name, "codename": codename,
                "project_type": ptype, "owning_team_id": self.team[team], "sponsor_id": self.emp[sponsor], "lead_id": self.emp[lead],
                "member_ids": [self.emp[m] for m in members], "product_ids": [self.prod[p] for p in products],
                "customer_ids": [self.cust[c] for c in customers], "project_status": status, "start_date": start,
                "target_date": target, "completed_on": done, "budget": money(budget), "outcome_metrics": []}

    def _policy_rows(self, spec):
        title, area, code, owner, applies, rules, label, groups = spec
        pid = self.nid("POL", 3)
        created = "2023-01-09T09:00:00Z"
        pol = {**self.envelope("grc", label, created, updated=W.ASSEMBLED_AT), "policy_id": pid, "title": title, "policy_area": area,
               "owner_department_id": self.dept[code], "owner_employee_id": self.emp[owner], "current_version": 1,
               "review_cycle_months": 12, "applies_to": applies}
        ver = {**self.envelope("grc", label, created), "policy_version_id": f"{pid}@v1", "policy_id": pid, "version": 1,
               "supersedes": None, "version_status": "current", "effective_from": "2023-02-01", "effective_to": None,
               "approved_by": self.emp["Avery Lancaster"],
               "key_rules": [{"rule": k, "value": v, "unit": None} for k, v in rules.items()], "change_summary": None}
        return pol, ver

    def _incident_row(self, spec):
        key, title, sev, cat, status, detected, resolved, commander, responders, products, customers, records, cause, notify, batch = spec
        return {**self.envelope("itsm", "restricted", detected, updated=resolved or detected), "incident_id": self.nid("INC", 3),
                "title": title, "severity": sev, "category": cat, "incident_status": status, "detected_at": detected,
                "resolved_at": resolved, "incident_commander_id": self.emp[commander], "responder_ids": [self.emp[r] for r in responders],
                "affected_product_ids": [self.prod[p] for p in products], "affected_customer_ids": [self.cust[c] for c in customers],
                "records_exposed": records, "root_cause_category": cause, "customer_notification_required": notify}

    def _ticket_row(self, spec):
        customer, product, subject, priority, status, opened, resolved, injection, lookalike, batch = spec
        cid = self.cust[customer]
        tenant = self.store.get("customer", cid)["portal_tenant_id"]
        support = [n for n in ("Arjun Rao", "Owen Gallagher", "Lucia Ferraro") if n in self.emp and self.emp[n] in self.store.tables["employee"]]
        assignee = support[self.counters.get("TCK", 0) % len(support)] if support else "Brandon Walker"
        con = self.con[customer]
        return {**self.envelope("support", "confidential", opened, tenant=tenant, updated=resolved or opened),
                "ticket_id": self.nid("TCK", 4), "customer_id": cid, "product_id": self.prod[product], "contract_id": con,
                "opened_by_principal_id": self.cus_principal[(customer, "portal_admin")], "assignee_id": self.emp[assignee],
                "subject": subject, "priority": priority, "ticket_status": status, "channel": "portal", "opened_at": opened,
                "resolved_at": resolved, "related_incident_id": None}

    # ---------------------------------------------------------- derived finance figures
    def fee_at(self, version, d):
        if version["fee_schedule"] and version["effective_from"]:
            months = contract_month(version["effective_from"], d)
            for r in version["fee_schedule"]:
                if r["from_month"] <= months <= r["to_month"]:
                    return r["monthly_fee"]
        return version["monthly_fee"]

    def mrr(self, d):
        """Contracted monthly recurring revenue by product and currency at date d (contracts active at d)."""
        out = {}
        for c in self.store.rows("contract"):
            if c["contract_status"] != "active":
                continue
            v = self.store.get("contract_version", f"{c['contract_id']}@v{c['current_version']}")
            if v["effective_from"] and v["effective_from"] > d:
                prior = [x for x in self.store.rows("contract_version") if x["contract_id"] == c["contract_id"] and x["version"] < v["version"]]
                v = max(prior, key=lambda x: x["version"]) if prior else None
                if v is None or (v["effective_from"] and v["effective_from"] > d):
                    continue
            fee = self.fee_at(v, d)
            if fee is None:
                continue
            key = (c["primary_product_id"], fee["currency"])
            out[key] = out.get(key, 0) + fee["amount"]
        return out

    def payroll(self, dept_id=None):
        total = 0
        for e in self.store.rows("employee"):
            if e["employment_status"] != "active" or e["employment_type"] == "contractor" or (dept_id and e["department_id"] != dept_id):
                continue
            rows = [r for r in self.store.rows("compensation") if r["employee_id"] == e["employee_id"] and r["effective_to"] is None]
            total += rows[0]["base_salary"]["amount"] if rows else 0
        return total

    def headcount(self):
        return sum(1 for e in self.store.rows("employee") if e["employment_status"] == "active" and e["employment_type"] != "contractor")

    def _financial_row(self, rtype, period, d, dept_code):
        quarter_end = {"2024-Q4": "2024-12-31", "2025-Q1": "2025-03-31", "2025-Q2": "2025-06-30", "2025-Q3": "2025-09-30"}
        prepared = self.head_of("finance") if self.dept["finance"] in self.store.tables["department"] else self.emp["Avery Lancaster"]
        label = "restricted" if rtype == "board_metrics" else "confidential"
        items = []
        if rtype in ("quarterly_pnl", "board_metrics"):
            mrr = self.mrr(quarter_end[period])
            for (prod, cur), amount in sorted(mrr.items()):
                items.append({"item": f"mrr_{slug(self.store.get('product', prod)['name']).replace('-', '_')}", "amount": amount, "currency": cur, "customer_id": None})
            items.append({"item": "annual_payroll", "amount": self.payroll(), "currency": "USD", "customer_id": None})
            if rtype == "board_metrics":
                items.append({"item": "headcount", "amount": self.headcount(), "currency": "USD", "customer_id": None})
        elif rtype == "receivables_summary":
            for i, c in enumerate(sorted(self.store.rows("customer"), key=lambda r: r["customer_id"])[:8]):
                items.append({"item": "outstanding_balance", "amount": 2500 * (i % 4 + 1), "currency": "USD", "customer_id": c["customer_id"]})
        elif rtype == "department_budget":
            items = [{"item": "payroll_budget", "amount": self.payroll(self.dept[dept_code]), "currency": "USD", "customer_id": None},
                     {"item": "program_budget", "amount": 50000, "currency": "USD", "customer_id": None}]
        return {**self.envelope("erp", label, ts(d)), "financial_id": self.nid("FIN", 3), "record_type": rtype, "period": period,
                "department_id": self.dept[dept_code] if dept_code else None, "product_id": None, "line_items": items,
                "prepared_by": prepared, "approved_by": self.emp["Avery Lancaster"], "is_final": True}

    # ------------------------------------------------------------------ T0: documents
    def _t0_documents(self):
        hr_dept, hr_owner = self.owner("hr")
        for e in self.seed["employees"]:
            eid, name, kb_file = e["id"], e["full_name"]["value"], e["kb_file"]
            split = employee_split(kb_file)
            comp_ids = [r["compensation_id"] for r in self.store.rows("compensation") if r["employee_id"] == eid]
            review_ids = [r["review_id"] for r in self.store.rows("performance_review") if r["employee_id"] == eid]
            emp_row = self.store.get("employee", eid)
            for dtype, title, ids, facts in [
                ("employee_profile", f"HR profile: {name}", [eid], [{"entity": eid, "fields": ["job_title", "location_id", "hire_date", "recognitions"]}]),
                ("compensation_record", f"Compensation record: {name}", [eid] + comp_ids, [{"entity": eid, "fields": ["date_of_birth"]}] + [{"entity": c, "fields": ["base_salary", "bonus_paid"]} for c in comp_ids]),
                ("performance_review", f"Performance reviews: {name}", [eid] + review_ids, [{"entity": r, "fields": ["rating_label", "rating_score"]} for r in review_ids]),
            ]:
                front = self.add_doc(None, t0=True, system="hris", document_type=dtype, title=title,
                                     source_uri=f"hris://employees/{eid}/{dtype.replace('_', '-')}", source_record_ids=ids,
                                     subject_entities=[emp_row["department_id"]], tenant_id="T-INSURELLM",
                                     owner_department_id=hr_dept, source_owner_id=hr_owner, region="us",
                                     created_at=emp_row["created_at"], updated_at=W.ASSEMBLED_AT, valid_from=emp_row["hire_date"],
                                     valid_to=None, body={"mode": "kb_verbatim", "kb_file": kb_file, "line_ranges": split[dtype]},
                                     facts=facts, batch_id="BATCH-00", primary_employee=eid)
                self.doc_of[(dtype, eid)] = front["document_id"]
        sales_dept, sales_owner = self.owner("sales")
        for c in self.seed["contracts"]:
            header = self.store.get("contract", c["id"])
            v1 = self.store.get("contract_version", f"{c['id']}@v1")
            front = self.add_doc(None, t0=True, system="clm", document_type="contract", title=c["kb_file"].split("/")[1][:-3],
                                 source_uri=f"clm://contracts/{c['id']}/versions/1", source_record_ids=[c["id"], f"{c['id']}@v1"],
                                 subject_entities=[c["customer_id"], c["product_id"]] + ([v1["tier_id"]] if v1["tier_id"] else []),
                                 tenant_id="T-INSURELLM", owner_department_id=sales_dept, source_owner_id=sales_owner, region="us",
                                 created_at=header["created_at"], updated_at=header["created_at"],
                                 valid_from=v1["effective_from"] or header["signed_on"] or W.T0_DATE, valid_to=v1["term_end"],
                                 body={"mode": "kb_verbatim", "kb_file": c["kb_file"], "line_ranges": whole_file(c["kb_file"])},
                                 facts=[{"entity": f"{c['id']}@v1", "fields": ["monthly_fee", "fee_schedule", "term_months", "term_end", "user_licenses",
                                                                             "total_contract_value", "tier_id", "volume_commitments"]},
                                        {"entity": c["id"], "fields": ["signed_on", "contract_number", "insurellm_signatory_as_printed", "customer_signatory"]}],
                                 batch_id="BATCH-00", primary_customer=c["customer_id"])
            self.doc_of[("contract", c["id"])] = front["document_id"]
        prod_dept, prod_owner = self.owner("product")
        for p in self.seed["products"]:
            front = self.add_doc(None, t0=True, system="wiki", document_type="product_overview", title=f"{p['name']['value']} product summary",
                                 source_uri=f"wiki://products/{slug(p['name']['value'])}", source_record_ids=[p["id"]] + [t["id"] for t in p["tiers"]],
                                 subject_entities=[], tenant_id="T-INSURELLM", owner_department_id=prod_dept, source_owner_id=prod_owner,
                                 region="us", created_at=W.ASSEMBLED_AT, updated_at=W.ASSEMBLED_AT, valid_from=W.T0_DATE, valid_to=None,
                                 body={"mode": "kb_verbatim", "kb_file": p["kb_file"], "line_ranges": whole_file(p["kb_file"])},
                                 facts=[{"entity": t["id"], "fields": ["monthly_list_price"]} for t in p["tiers"]] + [{"entity": p["id"], "fields": ["roadmap_items"]}],
                                 batch_id="BATCH-00")
            self.doc_of[("product_overview", p["id"])] = front["document_id"]
        exec_dept, exec_owner = self.owner("executive")
        mkt_dept, mkt_owner = self.owner("marketing")
        pages = {"company/about.md": ("public_web", "company_about", "https://www.insurellm.example/about", mkt_dept, mkt_owner),
                 "company/careers.md": ("public_web", "company_about", "https://www.insurellm.example/careers", mkt_dept, mkt_owner),
                 "company/overview.md": ("wiki", "company_page", "wiki://company/overview", exec_dept, exec_owner),
                 "company/culture.md": ("wiki", "company_page", "wiki://company/culture", exec_dept, exec_owner)}
        for kb_file, (system, dtype, uri, dept, owner) in pages.items():
            title = (KB_ROOT / kb_file).read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            front = self.add_doc(None, t0=True, system=system, document_type=dtype, title=title, source_uri=uri,
                                 source_record_ids=["T-INSURELLM"], subject_entities=[], tenant_id="T-INSURELLM", owner_department_id=dept,
                                 source_owner_id=owner, region="us", created_at=W.ASSEMBLED_AT, updated_at=W.ASSEMBLED_AT,
                                 valid_from=W.T0_DATE, valid_to=None,
                                 body={"mode": "kb_verbatim", "kb_file": kb_file, "line_ranges": whole_file(kb_file)},
                                 facts=[{"entity": "T-INSURELLM", "fields": ["stated_headcount"]}] if kb_file in K.HEADCOUNT_PATCHES else [],
                                 batch_id="BATCH-00")
            self.doc_of[("company", kb_file)] = front["document_id"]
        self._t0_generated_documents()

    def gen(self, template, facts=(), notes=None):
        return {"mode": "generated", "template": template, "notes": notes}, [{"entity": e, "fields": f} for e, f in facts]

    def _t0_generated_documents(self):
        crm_dept, crm_owner = self.owner("sales")
        for c in sorted(self.store.rows("customer"), key=lambda r: r["customer_id"]):
            self.customer_profile_doc(c, None, crm_dept, crm_owner, t0=True)
        for name in K.ACCOUNT_PLAN_CUSTOMERS:
            cid, con = self.cust[name], self.con[name]
            body, facts = self.gen("account_plan", [(f"{con}@v1", ["term_end", "monthly_fee", "fee_schedule"]), (cid, ["account_manager_id", "account_team_ids"])])
            self.add_doc(None, t0=True, system="crm", document_type="account_plan", title=f"Account plan: {name}",
                         source_uri=f"crm://accounts/{cid}/plan", source_record_ids=[cid], subject_entities=[con],
                         tenant_id="T-INSURELLM", owner_department_id=crm_dept, source_owner_id=self.store.get("customer", cid)["account_manager_id"],
                         region="us", created_at=W.ASSEMBLED_AT, updated_at=W.ASSEMBLED_AT, valid_from=W.T0_DATE, valid_to=None,
                         body=body, facts=facts, batch_id="BATCH-00", primary_customer=cid)
        for name in K.PRICING_APPROVALS_T0:
            self.pricing_approval_doc(name, 1, None, t0=True)
        exec_dept, exec_owner = self.owner("executive")
        for (rtype, key), row in self.fin.items():
            self.financial_doc(row, None, t0=True)
        eng_dept, eng_owner = self.owner("engineering")
        handbook_policies = {"Employee handbook: benefits and time off": ["Leave Policy", "Remote Work Policy"],
                             "Employee handbook: tools and onboarding": ["Acceptable Use Policy", "Information Security Policy"]}
        quarters = {"All-hands notes, 2025 Q1": ("2025-01-01", "2025-03-31"), "All-hands notes, 2025 Q2": ("2025-04-01", "2025-06-30")}
        for dtype, title, code, subjects, batch in K.WIKI_PAGES:
            dept, owner = self.owner(code)
            prods = [self.prod[p] for p in subjects]
            fields = [(pid, ["tech_lead_id", "owning_team_id"]) for pid in prods] if dtype == "technical_architecture" else []
            if dtype == "employee_handbook":
                fields = [(f"{self.policy_rows[t]}@v1", ["key_rules"]) for t in handbook_policies[title]]
            if dtype == "meeting_notes":
                lo, hi = quarters[title]
                fields = [(c["contract_id"], ["signed_on"]) for c in sorted(self.store.rows("contract"), key=lambda r: r["contract_id"])
                          if c["signed_on"] and lo <= c["signed_on"] <= hi]
            body, facts = self.gen(dtype, fields)
            self.add_doc(None, t0=True, system="wiki", document_type=dtype, title=title, source_uri=f"wiki://{dtype.replace('_', '-')}/{slug(title)}",
                         source_record_ids=prods or [self.dept[code]], subject_entities=[], tenant_id="T-INSURELLM", owner_department_id=dept,
                         source_owner_id=owner, region="us", created_at=W.ASSEMBLED_AT, updated_at=W.ASSEMBLED_AT,
                         valid_from=W.T0_DATE, valid_to=None, body=body, facts=facts, batch_id="BATCH-00")
        for spec in K.POLICIES:
            self.policy_doc(self.policy_rows[spec[0]], 1, None, t0=True)
        for key, row in self.incident.items():
            self.incident_docs(key, row, None, t0=True)
        for key, row in self.project.items():
            self.project_doc(key, row, 1, None, t0=True)
        pm_dept, pm_owner = self.owner("product")
        body, facts = self.gen("roadmap", [(p, ["roadmap_items"]) for p in sorted(self.prod.values())])
        self.add_doc(None, t0=True, system="pm", document_type="roadmap", title="Product roadmap 2025-2027", source_uri="pm://roadmap/2025-2027",
                     source_record_ids=sorted(self.prod.values()), subject_entities=[], tenant_id="T-INSURELLM", owner_department_id=pm_dept,
                     source_owner_id=pm_owner, region="us", created_at=W.ASSEMBLED_AT, updated_at=W.ASSEMBLED_AT, valid_from=W.T0_DATE,
                     valid_to=None, body=body, facts=facts, batch_id="BATCH-00")
        for spec, row in self.tickets:
            self.ticket_doc(spec, row, None, t0=True)
        for p in sorted(self.prod):
            self.public_page_doc(p, 1, None, t0=True)
        for title, d, customers, products, fact_fields in K.PRESS_RELEASES:
            self.press_release_doc(title, d, customers, products, fact_fields)

    # ------------------------------------------------------------------ document builders (T0 and batches)
    def customer_profile_doc(self, c, when, dept, owner, t0=False):
        con = self.con[c["display_name"]]
        body, facts = self.gen("customer_account_profile", [(c["customer_id"], ["display_name", "segment", "account_manager_id",
                                                                                 "customer_success_manager_id", "account_team_ids", "customer_since"])])
        front = self.add_doc(when, t0=t0, system="crm", document_type="customer_account_profile", title=f"Account profile: {c['display_name']}",
                             source_uri=f"crm://accounts/{c['customer_id']}/profile", source_record_ids=[c["customer_id"]],
                             subject_entities=[con] + self.store.get("contract", con)["primary_product_id"].split(),
                             tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=c["account_manager_id"], region="us",
                             created_at=when or c["created_at"], updated_at=when or W.ASSEMBLED_AT, valid_from=(when or W.T0)[:10],
                             valid_to=None, body=body, facts=facts, batch_id=self.store.batch, primary_customer=c["customer_id"])
        self.doc_of[("customer_account_profile", c["customer_id"])] = front["document_id"]

    def pricing_approval_doc(self, name, version_no, when, t0=False):
        cid, con = self.cust[name], self.con[name]
        dept, owner = self.owner("sales") if t0 else self.owner("finance")
        tier = self.store.get("contract_version", f"{con}@v{version_no}")["tier_id"]
        body, facts = self.gen("pricing_approval", [(f"{con}@v{version_no}", ["monthly_fee", "fee_schedule", "total_contract_value", "tier_id"])]
                               + ([(tier, ["monthly_list_price"])] if tier else []))
        self.add_doc(when, t0=t0, system="clm", document_type="pricing_approval", title=f"Pricing approval: {name} (v{version_no})",
                     source_uri=f"clm://contracts/{con}/approvals/{version_no}", source_record_ids=[f"{con}@v{version_no}"],
                     subject_entities=[cid, con], tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=owner, region="us",
                     created_at=when or W.ASSEMBLED_AT, updated_at=when or W.ASSEMBLED_AT, valid_from=(when or W.T0)[:10], valid_to=None,
                     body=body, facts=facts, batch_id=self.store.batch)

    def financial_doc(self, row, when, t0=False):
        dtype = {"quarterly_pnl": "financial_report", "product_revenue": "financial_report", "department_budget": "department_budget",
                 "receivables_summary": "receivables_summary", "board_metrics": "board_pack"}[row["record_type"]]
        dept, owner = self.owner("finance")
        heads = {}
        if row["department_id"]:
            heads = {"department_head": ["P-" + self.store.get("department", row["department_id"])["head_employee_id"]]}
        body, facts = self.gen(dtype, [(row["financial_id"], ["line_items", "period"])])
        title = {"financial_report": f"Quarterly results {row['period']}", "board_pack": f"Board pack {row['period']}",
                 "receivables_summary": f"Receivables summary {row['period']}",
                 "department_budget": f"Budget {row['period']}: {self.store.get('department', row['department_id'])['name'] if row['department_id'] else ''}"}[dtype]
        self.add_doc(when, t0=t0, system="erp", document_type=dtype, title=title, source_uri=f"erp://records/{row['financial_id']}",
                     source_record_ids=[row["financial_id"]], subject_entities=[row["department_id"]] if row["department_id"] else [],
                     tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=owner, region="us",
                     created_at=row["created_at"], updated_at=row["updated_at"], valid_from=row["created_at"][:10], valid_to=None,
                     body=body, facts=facts, batch_id=self.store.batch, principals_for=heads)

    def policy_doc(self, policy_id, version_no, when, t0=False, supersedes=None, label=None, groups=None):
        pol = self.store.get("policy", policy_id)
        ver = self.store.get("policy_version", f"{policy_id}@v{version_no}")
        spec = next(s for s in K.POLICIES if s[0] == pol["title"])
        body, facts = self.gen("policy", [(ver["policy_version_id"], ["key_rules", "effective_from", "change_summary"])])
        front = self.add_doc(when, t0=t0, document_id=self.doc_of.get(("policy", policy_id)), version=version_no, supersedes=supersedes,
                             system="grc", document_type="policy", title=f"{pol['title']} (v{version_no})",
                             source_uri=f"grc://policies/{policy_id}/versions/{version_no}", source_record_ids=[policy_id, ver["policy_version_id"]],
                             subject_entities=[pol["owner_department_id"]], tenant_id="T-INSURELLM", owner_department_id=pol["owner_department_id"],
                             source_owner_id=pol["owner_employee_id"], region="us", created_at=ver["created_at"], updated_at=ver["updated_at"],
                             valid_from=ver["effective_from"], valid_to=None, body=body, facts=facts, batch_id=self.store.batch,
                             label_override=label or (spec[6] if spec[6] != "internal" else None), groups_override=groups or spec[7] or None)
        self.doc_of[("policy", policy_id)] = front["document_id"]

    def incident_docs(self, key, row, when, t0=False):
        dept, owner = self.owner("security")
        body, facts = self.gen("incident_report", [(row["incident_id"], ["title", "severity", "detected_at", "resolved_at", "affected_customer_ids", "records_exposed", "root_cause_category"])])
        self.add_doc(when, t0=t0, system="itsm", document_type="incident_report", title=f"Incident report {row['incident_id']}: {row['title']}",
                     source_uri=f"itsm://incidents/{row['incident_id']}/report", source_record_ids=[row["incident_id"]],
                     subject_entities=row["affected_product_ids"] + row["affected_customer_ids"], tenant_id="T-INSURELLM",
                     owner_department_id=dept, source_owner_id=owner, region="us", created_at=row["created_at"], updated_at=row["updated_at"],
                     valid_from=row["detected_at"][:10], valid_to=None, body=body, facts=facts, batch_id=self.store.batch)

    def postmortem_doc(self, key, row, when, t0=False):
        dept, owner = self.owner("security")
        body, facts = self.gen("postmortem_summary", [(row["incident_id"], ["severity", "root_cause_category"])],
                               notes="Sanitised: no customer names and no record counts.")
        self.add_doc(when, t0=t0, system="itsm", document_type="postmortem_summary", title=f"Postmortem: {row['title']}",
                     source_uri=f"itsm://incidents/{row['incident_id']}/postmortem", source_record_ids=[row["incident_id"]],
                     subject_entities=row["affected_product_ids"], tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=owner,
                     region="us", created_at=row["updated_at"], updated_at=row["updated_at"], valid_from=row["resolved_at"][:10],
                     valid_to=None, body=body, facts=facts, batch_id=self.store.batch)

    def project_doc(self, key, row, version_no, when, t0=False, supersedes=None):
        restricted = row["sensitivity_label"] == "restricted"
        body, facts = self.gen("project_brief", [(row["project_id"], ["name", "codename", "project_status", "lead_id", "member_ids", "target_date", "budget"])])
        dept, owner = self.owner("product") if not restricted else self.owner("executive")
        front = self.add_doc(when, t0=t0, document_id=self.doc_of.get(("project", key)), version=version_no, supersedes=supersedes,
                             system="pm", document_type="project_brief", title=f"Project brief: {row['codename'] or row['name']}",
                             source_uri=f"pm://projects/{row['project_id']}/brief", source_record_ids=[row["project_id"]],
                             subject_entities=row["product_ids"] + row["customer_ids"], tenant_id="T-INSURELLM", owner_department_id=dept,
                             source_owner_id=owner, region="us", created_at=row["created_at"], updated_at=when or row["updated_at"],
                             valid_from=(when or row["created_at"])[:10], valid_to=None, body=body, facts=facts, batch_id=self.store.batch,
                             label_override="restricted" if restricted else None, groups_override=["GRP-board"] if restricted else None,
                             principals_override=["P-" + m for m in row["member_ids"]] if restricted else None)
        self.doc_of[("project", key)] = front["document_id"]

    def ticket_doc(self, spec, row, when, t0=False):
        customer, product, subject, priority, status, opened, resolved, injection, lookalike, batch = spec
        dept, owner = self.owner("customer-success")
        notes = "; ".join(x for x in [
            "Customer message contains instructions addressed to an AI assistant (planted prompt injection)." if injection else None,
            f"lookalike:{lookalike}" if lookalike else None] if x) or None
        body, facts = self.gen("support_ticket", [(row["ticket_id"], ["subject", "priority", "ticket_status", "opened_at", "resolved_at"])], notes=notes)
        front = self.add_doc(when, t0=t0, system="support", document_type="support_ticket", title=f"{row['ticket_id']}: {subject}",
                             source_uri=f"support://{row['tenant_id']}/tickets/{row['ticket_id']}", source_record_ids=[row["ticket_id"]],
                             subject_entities=[row["customer_id"], row["product_id"], row["contract_id"]], tenant_id=row["tenant_id"],
                             owner_department_id=dept, source_owner_id=owner, region="us", created_at=opened, updated_at=resolved or opened,
                             valid_from=opened[:10], valid_to=None, body=body, facts=facts, batch_id=self.store.batch,
                             primary_customer=row["customer_id"])
        self.doc_of[("ticket", row["ticket_id"])] = front["document_id"]
        self.ticket_traps = getattr(self, "ticket_traps", [])
        self.ticket_traps.append((front["document_version_id"], injection, lookalike, row))

    def public_page_doc(self, product_name, version_no, when, t0=False, supersedes=None):
        pid = self.prod[product_name]
        tiers = [t["tier_id"] for t in self.store.rows("product_tier") if t["product_id"] == pid and t["valid_to"] is None]
        dept, owner = self.owner("marketing")
        body, facts = self.gen("public_product_page", [(t, ["tier_name", "monthly_list_price"]) for t in tiers] + [(pid, ["tagline"])])
        front = self.add_doc(when, t0=t0, document_id=self.doc_of.get(("public_page", pid)), version=version_no, supersedes=supersedes,
                             system="public_web", document_type="public_product_page", title=f"{product_name} pricing and features",
                             source_uri=f"https://www.insurellm.example/products/{slug(product_name)}", source_record_ids=[pid] + tiers,
                             subject_entities=[], tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=owner, region="us",
                             created_at=when or W.ASSEMBLED_AT, updated_at=when or W.ASSEMBLED_AT, valid_from=(when or W.T0)[:10],
                             valid_to=None, body=body, facts=facts, batch_id=self.store.batch)
        self.doc_of[("public_page", pid)] = front["document_id"]

    def press_release_doc(self, title, d, customers, products, fact_fields):
        dept, owner = self.owner("marketing")
        cids = [self.cust[c] for c in customers]
        cons = [self.con[c] for c in customers]
        body, facts = self.gen("press_release", [(f"{c}@v1", fact_fields) for c in cons] + [(c, ["display_name"]) for c in cids])
        front = self.add_doc(None, t0=True, system="public_web", document_type="press_release", title=title,
                             source_uri=f"https://www.insurellm.example/press/{slug(title)}",
                             source_record_ids=cids + [self.prod[p] for p in products] or [self.prod[products[0]]],
                             subject_entities=cons, tenant_id="T-INSURELLM", owner_department_id=dept, source_owner_id=owner, region="us",
                             created_at=ts(d), updated_at=ts(d), valid_from=d, valid_to=None, body=body, facts=facts, batch_id="BATCH-00")
        self.press = getattr(self, "press", [])
        self.press.append((front["document_version_id"], cids, cons))

    # ================================================================== batches
    def batch_01(self):
        lon = W.LONDON
        self.schedule("2025-07-01", lambda when: self.store.insert("location", {
            **self.envelope("hris", "internal", when), "location_id": lon[1], "name": lon[2], "location_type": lon[3], "city": lon[4],
            "state_or_province": lon[5], "country": lon[6], "region": lon[7], "timezone": lon[8], "opened_on": lon[9]},
            when, self.pid("Avery Lancaster"), "new_record"))
        self.loc["london"] = lon[1]
        for code, (did, name, cc, batch) in W.DEPARTMENTS.items():
            if batch == "BATCH-01":
                self.schedule("2025-07-03", lambda when, did=did, name=name, cc=cc, code=code: self.store.insert("department", {
                    **self.envelope("hris", "internal", when), "department_id": did, "name": name, "code": code,
                    "head_employee_id": self.emp["Avery Lancaster"], "parent_department_id": None, "default_group_id": f"GRP-{code}",
                    "cost_center": cc}, when, self.pid("Avery Lancaster"), "org_change"))
        for spec in W.HIRES:
            self.schedule(spec[10], lambda when, spec=spec: self.hire(spec, when))
        for code, head in W.NEW_DEPARTMENT_HEADS.items():
            hire_day = next(h[10] for h in W.HIRES if h[0] == head)
            self.schedule(hire_day, lambda when, code=code, head=head: self.set_head(code, head, when))
        for key, spec in W.TEAMS.items():
            if spec[6] == "BATCH-01":
                hire_day = next(h[10] for h in W.HIRES if h[0] == spec[3])
                self.schedule(hire_day, lambda when, key=key: self.store.insert("team", self._team_row(key, when), when, self.pid("Avery Lancaster"), "org_change"))
        self.schedule("2025-07-07", lambda when: self.reassign_manager("Amanda Foster", "Naomi Brandt", when))
        self.schedule("2025-07-14", lambda when: [self.reassign_manager(n, "Claire Dubois", when) for n in ("Michael O'Brien", "Alex Thomson")])
        for spec in W.NEW_CUSTOMERS:
            self.schedule(spec[6], lambda when, spec=spec: self.new_customer(spec, when))
        self.schedule(K.LIGHTHOUSE_ADD_MEMBERS[0], lambda when: self.lighthouse_members(when))
        self.schedule("2025-08-05", lambda when: self.new_financial("quarterly_pnl", "2025-Q2", None, when))
        for name in W.EXPIRE_IN_BATCH_01:
            self.schedule("2025-08-08", lambda when, name=name: self.expire_contract(name, when))
        self.schedule("2025-08-11", lambda when: self.headcount_pages(when))
        for code, (_, _, _, batch) in W.DEPARTMENTS.items():
            if batch == "BATCH-01":
                self.schedule("2025-08-12", lambda when, code=code: self.new_financial("department_budget", "FY2025", code, when))
        self.schedule_tickets("BATCH-01")
        self.run_batch("BATCH-01")

    def hire(self, spec, when):
        name, title, level, code, team_key, manager, loc_key, salary, etype, dob, hire_date = spec
        eid = f"EMP-{len(self.emp) + 1:03d}"
        self.emp[name] = eid
        first, last = name.split()[0], name.split()[-1]
        remote = loc_key == "remote-us"
        hr = self.pid_for_emp(self.head_of("hr"))
        row = {**self.envelope("hris", "internal", when), "employee_id": eid, "first_name": first, "last_name": last, "preferred_name": None,
               "work_email": f"{first.lower()}.{last.lower()}@insurellm.example", "date_of_birth": dob, "job_title": title, "job_level": level,
               "department_id": self.dept[code], "team_id": self.team[team_key] if self.team[team_key] in self.store.tables["team"] else None,
               "manager_id": self.emp[manager], "location_id": self.loc[loc_key], "work_arrangement": "remote" if remote else "hybrid",
               "remote_city": W.REMOTE_CITIES.get(name) if remote else None, "employment_type": etype, "employment_status": "active",
               "hire_date": hire_date, "hire_date_precision": "day", "termination_date": None, "recognitions": []}
        self.store.insert("employee", row, when, hr, "new_record")
        if salary:
            comp = {**self.envelope("hris", "restricted", when), "compensation_id": self.nid("COMP", 4), "employee_id": eid,
                    "effective_from": hire_date, "effective_from_precision": "day", "effective_to": None, "job_title_at_time": title,
                    "base_salary": money(salary), "bonus_target_pct": 15 if level.startswith(("E", "M")) else 10, "bonus_paid": None,
                    "change_reason": "hire", "approved_by": self.emp[manager]}
            self.store.insert("compensation", comp, when, hr, "new_record")
        self.store.insert("principal", self._employee_principal(row, when), when, hr, "new_record")
        self.sync_memberships(when)
        hr_dept, hr_owner = self.owner("hr")
        for dtype, label in [("employee_profile", "HR profile"), ("compensation_record", "Compensation record")]:
            if dtype == "compensation_record" and not salary:
                continue
            ids = [eid] + ([comp["compensation_id"]] if dtype == "compensation_record" else [])
            fields = [(eid, ["job_title", "department_id", "location_id", "hire_date", "manager_id"])] if dtype == "employee_profile" \
                else [(comp["compensation_id"], ["base_salary", "bonus_target_pct", "effective_from"])]
            body, facts = self.gen(dtype, fields)
            front = self.add_doc(when, system="hris", document_type=dtype, title=f"{label}: {name}", source_uri=f"hris://employees/{eid}/{dtype.replace('_', '-')}",
                                 source_record_ids=ids, subject_entities=[row["department_id"]], tenant_id="T-INSURELLM",
                                 owner_department_id=hr_dept, source_owner_id=hr_owner, region="us", created_at=when, updated_at=when,
                                 valid_from=hire_date, valid_to=None, body=body, facts=facts, batch_id=self.store.batch, primary_employee=eid)
            self.doc_of[(dtype, eid)] = front["document_id"]

    def set_head(self, code, head, when):
        self.store.update("department", self.dept[code], {"head_employee_id": self.emp[head]}, when, self.pid("Avery Lancaster"), "org_change")

    def reassign_manager(self, name, manager, when):
        self.store.update("employee", self.emp[name], {"manager_id": self.emp[manager]}, when, self.pid_for_emp(self.head_of("hr")), "org_change")

    def new_customer(self, spec, when):
        display, legal, product, tier_name, fee, months, effective, city, country, region, currency, portal = spec
        cid = f"CUST-{len(self.cust) + 1:03d}"
        con = f"CON-{len(self.con) + 1:03d}"
        self.cust[display], self.con[display] = cid, con
        am, team = self.account_team(product, tier_name)
        claire = self.emp["Claire Dubois"]
        row = {**self.envelope("crm", "confidential", when), "customer_id": cid, "legal_name": legal, "display_name": display,
               "segment": W.SEGMENT[product], "hq_city": city, "country": country, "region": region, "account_manager_id": self.emp[am],
               "customer_success_manager_id": self.emp["Marcus Johnson"], "account_team_ids": team, "customer_since": effective,
               "customer_status": "active", "has_portal_tenant": portal, "portal_tenant_id": f"T-CUST-{cid[-3:]}" if portal else None,
               "is_public_reference": False}
        self.store.insert("customer", row, when, self.pid_for_emp(self.emp[am]), "new_record")
        number = {"Carllm": "CR", "Homellm": "HM", "Rellm": "RE"}[product] + f"-2025-{300 + int(cid[-3:]):04d}"
        legal_owner = self.emp["Victor Almeida"]
        header = {**self.envelope("clm", "confidential", when), "contract_id": con, "contract_number": number, "customer_id": cid,
                  "primary_product_id": self.prod[product], "contract_type": "subscription", "legal_owner_id": legal_owner,
                  "insurellm_signatory_id": claire, "insurellm_signatory_as_printed": {"name": "Claire Dubois", "title": "Director of Sales"},
                  "customer_signatory": {"name": f"{legal.split()[0]} Operations Lead", "title": "Chief Operating Officer"},
                  "signed_on": effective, "current_version": 1, "contract_status": "active"}
        self.store.insert("contract", header, when, self.pid_for_emp(legal_owner), "new_record")
        version = {**self.envelope("clm", "confidential", when), "contract_version_id": f"{con}@v1", "contract_id": con, "version": 1,
                   "change_type": "original", "supersedes": None, "version_status": "current", "effective_from": effective,
                   "term_end": term_end(effective, months), "term_months": months, "auto_renew": True, "renewal_term_months": 12,
                   "non_renewal_notice_days": 60, "termination_notice_days": 60, "max_annual_price_increase_pct": 5,
                   "tier_id": self.tier_for(product, tier_name), "monthly_fee": money(fee, currency), "fee_schedule": [], "setup_fee": None,
                   "per_lead_fee": None, "total_contract_value": money(fee * months, currency), "payment_terms": "net_30",
                   "user_licenses": 20, "training_seats": 10, "volume_commitments": [], "scope_product_ids": [self.prod[product]],
                   "support_level": "standard", "change_summary": None, "approved_by": self.emp["Daniela Okafor"]}
        self.store.insert("contract_version", version, when, self.pid_for_emp(legal_owner), "new_record")
        if portal:
            self._tenant_and_users(row, when)
            self.sync_memberships(when)
        crm_dept, _ = self.owner("sales")
        self.customer_profile_doc(row, when, crm_dept, row["account_manager_id"])
        legal_dept, legal_head = self.owner("legal")
        body, facts = self.gen("contract", [(f"{con}@v1", ["monthly_fee", "term_months", "term_end", "tier_id", "total_contract_value", "user_licenses",
                                                           "payment_terms", "support_level"]),
                                            (con, ["signed_on", "contract_number", "insurellm_signatory_as_printed", "customer_signatory"])])
        front = self.add_doc(when, system="clm", document_type="contract", title=f"Contract with {display} for {product}",
                             source_uri=f"clm://contracts/{con}/versions/1", source_record_ids=[con, f"{con}@v1"],
                             subject_entities=[cid, self.prod[product], version["tier_id"]], tenant_id="T-INSURELLM", owner_department_id=legal_dept,
                             source_owner_id=legal_owner, region=region, created_at=when, updated_at=when, valid_from=effective,
                             valid_to=version["term_end"], body=body, facts=facts, batch_id=self.store.batch, primary_customer=cid)
        self.doc_of[("contract", con)] = front["document_id"]

    def lighthouse_members(self, when):
        row = self.project["lighthouse"]
        pid = row["project_id"]
        members = row["member_ids"] + [self.emp[n] for n in K.LIGHTHOUSE_ADD_MEMBERS[1]]
        self.project["lighthouse"] = self.store.update("project", pid, {"member_ids": members}, when, self.pid("Avery Lancaster"), "access_change")
        prev = self.latest_version(self.doc_of[("project", "lighthouse")])
        self.project_doc("lighthouse", self.project["lighthouse"], 2, when, supersedes=prev)

    def new_financial(self, rtype, period, code, when):
        row = self._financial_row(rtype, period, when[:10], code)
        row["created_at"] = row["updated_at"] = when
        self.store.insert("financial_record", row, when, self.pid_for_emp(row["prepared_by"]), "new_record")
        self.financial_doc(row, when)

    def expire_contract(self, name, when):
        con = self.con[name]
        actor = self.pid_for_emp(self.head_of("legal"))
        self.store.update("contract", con, {"contract_status": "expired"}, when, actor, "status_change")
        self.store.update("contract_version", f"{con}@v1", {"version_status": "expired"}, when, actor, "status_change")
        c = self.store.get("customer", self.cust[name])
        self.store.update("customer", c["customer_id"], {"customer_status": "churned"}, when, self.pid_for_emp(c["account_manager_id"]), "status_change")

    def headcount_pages(self, when):
        n = self.headcount()
        self.headcount_after_b01 = n
        for kb_file, patches in K.HEADCOUNT_PATCHES.items():
            doc_id = self.doc_of[("company", kb_file)]
            base = f"{doc_id}@v1"
            fm = self.store.get("document_version", base)["front_matter"]
            ops = [{"op": "replace", "old": old, "new": new.format(n=n)} for old, new in patches]
            self.add_doc(when, document_id=doc_id, version=2, supersedes=base, system=fm["source_system"], document_type=fm["document_type"],
                         title=fm["title"], source_uri=fm["source_uri"], source_record_ids=fm["source_record_ids"], subject_entities=[],
                         tenant_id="T-INSURELLM", owner_department_id=fm["owner_department_id"], source_owner_id=fm["source_owner_id"],
                         region="us", created_at=fm["created_at"], updated_at=when, valid_from=when[:10], valid_to=None,
                         body={"mode": "kb_patch", "base": base, "ops": ops}, facts=[{"entity": "T-INSURELLM", "fields": ["stated_headcount"]}],
                         batch_id=self.store.batch)

    def schedule_tickets(self, batch):
        for spec in K.TICKETS:
            if spec[-1] == batch:
                self.schedule(spec[5][:10], lambda when, spec=spec: self.new_ticket(spec, when))

    def new_ticket(self, spec, when):
        if not self.store.get("customer", self.cust[spec[0]])["has_portal_tenant"]:
            raise ValueError(f"ticket for {spec[0]}, which has no portal tenant")
        row = self._ticket_row(spec)
        row["created_at"] = row["updated_at"] = when
        self.store.insert("support_ticket", row, when, row["opened_by_principal_id"], "new_record")
        self.ticket_doc(spec, row, when)

    # ------------------------------------------------------------------ BATCH-02
    def batch_02(self):
        for name, (signed, *_rest) in W.AMENDMENTS.items():
            self.schedule(signed, lambda when, name=name: self.amend(name, when))
        signed, effective, tier_name, price = W.CARLLM_PRICE_CHANGE
        self.schedule(signed, lambda when: self.carllm_price(when))
        for name in K.PRICING_APPROVALS_B02:
            self.schedule(W.AMENDMENTS[name][0], lambda when, name=name: self.pricing_approval_doc(name, 2, when))
        self.schedule_tickets("BATCH-02")
        self.run_batch("BATCH-02")

    def amend(self, name, when):
        signed, change_type, effective, changes, summary = W.AMENDMENTS[name]
        con = self.con[name]
        v1 = self.store.get("contract_version", f"{con}@v1")
        header = self.store.get("contract", con)
        product = self.store.get("product", header["primary_product_id"])["name"]
        legal = self.emp["Victor Almeida"]
        v2 = copy.deepcopy(v1)
        v2.update(self.envelope("clm", "confidential", when))
        v2.update({"contract_version_id": f"{con}@v2", "version": 2, "change_type": change_type, "supersedes": f"{con}@v1",
                   "version_status": "current", "change_summary": summary, "approved_by": self.emp["Daniela Okafor"]})
        if change_type == "renewal":
            v2["effective_from"] = effective
        else:
            v2["effective_from"] = effective
        for k in ("monthly_fee",):
            if k in changes:
                v2["monthly_fee"] = money(changes[k], (v1["monthly_fee"] or {"currency": "USD"})["currency"])
        if "user_licenses" in changes:
            v2["user_licenses"] = changes["user_licenses"]
        if "tier" in changes:
            v2["tier_id"] = self.tier_for(product, changes["tier"])
        if "term_months" in changes:
            v2["term_months"], v2["term_end"] = changes["term_months"], changes["term_end"]
        if "volume" in changes:
            metric, value = changes["volume"]
            v2["volume_commitments"] = [dict(v, value=value) if v["metric"] == metric else v for v in v2["volume_commitments"]]
        if "add_scope" in changes:
            v2["scope_product_ids"] = v1["scope_product_ids"] + [self.prod[changes["add_scope"]]]
            addon = changes["addon_monthly"]
            start = v1["effective_from"]
            month_of_change = contract_month(start, effective)
            sched = []
            for r in v1["fee_schedule"]:
                if r["to_month"] < month_of_change:
                    sched.append(r)
                elif r["from_month"] < month_of_change:
                    sched.append(dict(r, to_month=month_of_change - 1))
                    sched.append({"from_month": month_of_change, "to_month": r["to_month"], "monthly_fee": money(r["monthly_fee"]["amount"] + addon)})
                else:
                    sched.append(dict(r, monthly_fee=money(r["monthly_fee"]["amount"] + addon)))
            v2["fee_schedule"] = sched
            v2["monthly_fee"] = money(next(r["monthly_fee"]["amount"] for r in sched if r["from_month"] == month_of_change))
            v2["total_contract_value"] = money(sum((r["to_month"] - r["from_month"] + 1) * r["monthly_fee"]["amount"] for r in sched))
        elif v2["monthly_fee"] and v2["term_months"] and change_type == "renewal":
            v2["total_contract_value"] = money(v2["monthly_fee"]["amount"] * v2["term_months"], v2["monthly_fee"]["currency"])
        elif v2["monthly_fee"] and v1["total_contract_value"] and v1["effective_from"] and v1["term_months"]:
            done = contract_month(v1["effective_from"], effective) - 1
            v2["total_contract_value"] = money(v1["monthly_fee"]["amount"] * done + v2["monthly_fee"]["amount"] * (v1["term_months"] - done))
        # generated version: fill what a real CLM record would carry
        v2["payment_terms"] = v2["payment_terms"] or "monthly_in_advance"
        v2["support_level"] = v2["support_level"] or "standard"
        v2["auto_renew"] = v2["auto_renew"] if v2["auto_renew"] is not None else False
        if v2["term_end"] is None and v2["effective_from"] and v2["term_months"]:
            v2["term_end"] = term_end(v1["effective_from"] or v2["effective_from"], v2["term_months"])
        if v2["total_contract_value"] is None and v2["monthly_fee"] and v2["term_months"]:
            v2["total_contract_value"] = money(v2["monthly_fee"]["amount"] * v2["term_months"], v2["monthly_fee"]["currency"])
        if v2["monthly_fee"] is None:
            v2["monthly_fee"] = v1["monthly_fee"]
        actor = self.pid_for_emp(legal)
        self.store.update("contract_version", f"{con}@v1", {"version_status": "superseded"}, when, actor, "amendment")
        self.store.insert("contract_version", v2, when, actor, "renewal" if change_type == "renewal" else "amendment")
        self.store.update("contract", con, {"current_version": 2, "legal_owner_id": legal}, when, actor, "amendment")
        legal_dept, _ = self.owner("legal")
        dtype = "contract_renewal" if change_type == "renewal" else "contract_amendment"
        body, facts = self.gen(dtype, [(f"{con}@v2", ["monthly_fee", "fee_schedule", "term_months", "term_end", "user_licenses", "total_contract_value",
                                                      "tier_id", "volume_commitments", "scope_product_ids", "effective_from", "change_summary"]),
                                       (f"{con}@v1", ["monthly_fee"] if change_type == "renewal" or "monthly_fee" in changes else [])])
        doc_id = self.doc_of[("contract", con)]
        self.add_doc(when, document_id=doc_id, version=2, supersedes=f"{doc_id}@v1", system="clm", document_type=dtype,
                     title=f"{'Renewal' if change_type == 'renewal' else 'Amendment 1'}: {name}, {product}",
                     source_uri=f"clm://contracts/{con}/versions/2", source_record_ids=[con, f"{con}@v2"],
                     subject_entities=[header["customer_id"]] + v2["scope_product_ids"] + ([v2["tier_id"]] if v2["tier_id"] else []),
                     tenant_id="T-INSURELLM", owner_department_id=legal_dept, source_owner_id=legal, region="us", created_at=when,
                     updated_at=when, valid_from=effective, valid_to=v2["term_end"], body=body, facts=facts, batch_id=self.store.batch,
                     primary_customer=header["customer_id"])

    def carllm_price(self, when):
        signed, effective, tier_name, price = W.CARLLM_PRICE_CHANGE
        old_id = self.tier[("Carllm", tier_name)]
        old = self.store.get("product_tier", old_id)
        actor = self.pid_for_emp(self.head_of("product"))
        self.store.update("product_tier", old_id, {"valid_to": day_before(effective)}, when, actor, "price_change")
        new_id = f"TIER-{len(self.reg['tiers']) + 1:03d}"
        new = copy.deepcopy(old)
        new.update(self.envelope("pm", "public", when))
        new.update({"tier_id": new_id, "monthly_list_price": money(price), "valid_from": effective, "valid_to": None})
        self.store.insert("product_tier", new, when, actor, "price_change")
        self.tier[("Carllm", tier_name)] = new_id
        doc_id = self.doc_of[("product_overview", self.prod["Carllm"])]
        fm = self.store.get("document_version", f"{doc_id}@v1")["front_matter"]
        self.add_doc(when, document_id=doc_id, version=2, supersedes=f"{doc_id}@v1", system="wiki", document_type="product_overview",
                     title=fm["title"], source_uri=fm["source_uri"], source_record_ids=fm["source_record_ids"] + [new_id], subject_entities=[],
                     tenant_id="T-INSURELLM", owner_department_id=fm["owner_department_id"], source_owner_id=fm["source_owner_id"], region="us",
                     created_at=fm["created_at"], updated_at=when, valid_from=effective, valid_to=None,
                     body={"mode": "kb_patch", "base": f"{doc_id}@v1",
                           "ops": [{"op": "replace", "old": "**Professional Tier**: $2,500/month", "new": f"**Professional Tier**: ${price:,}/month"}]},
                     facts=[{"entity": new_id, "fields": ["monthly_list_price"]}], batch_id=self.store.batch)
        prev = self.latest_version(self.doc_of[("public_page", self.prod["Carllm"])])
        self.public_page_doc("Carllm", 2, when, supersedes=prev)

    # ------------------------------------------------------------------ BATCH-03
    def batch_03(self):
        name, d, title, level, code, team, manager = W.TRANSFER
        self.schedule(d, lambda when: self.transfer(when))
        self.schedule(W.REORG[1], lambda when: self.store.update("employee", self.emp[W.REORG[0]],
                      {"team_id": self.team[W.REORG[2]], "manager_id": self.emp[W.REORG[3]]}, when, self.pid_for_emp(self.head_of("hr")), "org_change"))
        self.schedule(W.TERMINATION[1], lambda when: self.terminate(when))
        self.schedule(W.SUSPEND_TENANT[1], lambda when: self.store.update("tenant", self.store.get("customer", self.cust[W.SUSPEND_TENANT[0]])["portal_tenant_id"],
                      {"tenant_status": "suspended", "updated_at": when}, when, self.pid("Marcus Johnson"), "status_change"))
        self.schedule(W.DISABLE_CUSTOMER_USER[2], lambda when: self.store.update("principal", self.cus_principal[W.DISABLE_CUSTOMER_USER[:2]],
                      {"principal_status": "disabled", "disabled_at": when}, when, self.pid("Marcus Johnson"), "access_change"))
        self.schedule(W.ACCOUNT_TEAM_SHUFFLE[1], lambda when: self.shuffle(when))
        self.schedule_tickets("BATCH-03")
        self.run_batch("BATCH-03")

    def transfer(self, when):
        name, d, title, level, code, team, manager = W.TRANSFER
        eid = self.emp[name]
        hr = self.pid_for_emp(self.head_of("hr"))
        self.store.update("employee", eid, {"job_title": title, "job_level": level, "department_id": self.dept[code],
                                            "team_id": self.team[team], "manager_id": self.emp[manager]}, when, hr, "org_change")
        self.sync_memberships(when)
        for c in sorted(self.store.rows("customer"), key=lambda r: r["customer_id"]):
            if eid in c["account_team_ids"] or c["account_manager_id"] == eid:
                new_am = self.emp["Michael O'Brien"] if c["account_manager_id"] == eid else c["account_manager_id"]
                team_ids = [x for x in c["account_team_ids"] if x != eid]
                team_ids = list(dict.fromkeys([new_am] + team_ids))
                self.store.update("customer", c["customer_id"], {"account_manager_id": new_am, "account_team_ids": team_ids}, when,
                                  self.pid_for_emp(self.head_of("sales")), "access_change")
        doc_id = self.doc_of[("employee_profile", eid)]
        fm = self.store.get("document_version", f"{doc_id}@v1")["front_matter"]
        self.add_doc(when, document_id=doc_id, version=2, supersedes=f"{doc_id}@v1", system="hris", document_type="employee_profile",
                     title=fm["title"], source_uri=fm["source_uri"], source_record_ids=fm["source_record_ids"], subject_entities=[self.dept[code]],
                     tenant_id="T-INSURELLM", owner_department_id=fm["owner_department_id"], source_owner_id=self.head_of("hr"), region="us",
                     created_at=fm["created_at"], updated_at=when, valid_from=d, valid_to=None,
                     body={"mode": "kb_patch", "base": f"{doc_id}@v1",
                           "ops": [{"op": "replace", "old": "**Job Title:** Account Executive", "new": f"**Job Title:** {title}"},
                                   {"op": "append", "text": f"- **October 2025:** Moved to Finance as {title}."}]},
                     facts=[{"entity": eid, "fields": ["job_title", "department_id"]}], batch_id=self.store.batch, primary_employee=eid)

    def terminate(self, when):
        name, d = W.TERMINATION
        eid = self.emp[name]
        hr = self.pid_for_emp(self.head_of("hr"))
        self.store.update("employee", eid, {"employment_status": "terminated", "termination_date": d, "record_status": "inactive"}, when, hr, "offboarding")
        self.store.update("principal", "P-" + eid, {"principal_status": "disabled", "disabled_at": when}, when, hr, "offboarding")
        self.sync_memberships(when)
        for p in self.store.rows("project"):
            if eid in p["member_ids"]:
                self.store.update("project", p["project_id"], {"member_ids": [m for m in p["member_ids"] if m != eid]}, when, hr, "offboarding")

    def shuffle(self, when):
        c = self.store.get("customer", self.cust[W.ACCOUNT_TEAM_SHUFFLE[0]])
        claire = self.emp["Claire Dubois"]
        actor = self.pid_for_emp(self.head_of("sales"))
        self.store.update("customer", c["customer_id"], {"account_team_ids": list(dict.fromkeys(c["account_team_ids"] + [claire]))}, when, actor, "access_change")
        first = len(self.store.events) - 1
        c = self.store.get("customer", c["customer_id"])
        self.store.update("customer", c["customer_id"], {"account_manager_id": claire}, when.replace(":00Z", ":30Z"), actor, "access_change")
        self.anomalies.append(("out_of_order", self.store.events[first]["sequence"], self.store.events[-1]["sequence"]))

    # ------------------------------------------------------------------ BATCH-04
    def batch_04(self):
        for key, d in K.ARCHIVE_PROJECTS:
            self.schedule(d, lambda when, key=key: self.set_doc_status(self.latest_version(self.doc_of[("project", key)]), "archived", when,
                                                                       self.pid_for_emp(self.head_of("product")), "archival"))
        for title, (d, *_rest) in W.POLICY_REVISIONS.items():
            self.schedule(d, lambda when, title=title: self.revise_policy(title, when))
        inc_spec = next(s for s in K.INCIDENTS if s[-1] == "BATCH-04")
        self.schedule(inc_spec[5][:10], lambda when: self.new_incident(inc_spec, when))
        self.schedule(W.ERASURE[1], lambda when: self.erase(when))
        for name in W.EXPIRE_IN_BATCH_01:
            self.schedule("2025-11-24", lambda when, name=name: self.set_doc_status(self.latest_version(self.doc_of[("contract", self.con[name])]),
                                                                                    "archived", when, self.pid_for_emp(self.head_of("legal")), "archival"))
        self.schedule("2025-11-25", lambda when: self.postmortem_doc("claimllm-vendor", self.incident["claimllm-vendor"], when))
        self.schedule("2025-12-01", lambda when: self.new_financial("quarterly_pnl", "2025-Q3", None, when))
        self.schedule("2025-12-01", lambda when: self.new_financial("board_metrics", "2025-Q3", None, when))
        self.schedule_tickets("BATCH-04")
        self.run_batch("BATCH-04")

    def revise_policy(self, title, when):
        d, effective, rules, summary, label, groups = W.POLICY_REVISIONS[title]
        pid = self.policy_rows[title]
        v1 = self.store.get("policy_version", f"{pid}@v1")
        owner = self.store.get("policy", pid)["owner_employee_id"]
        actor = self.pid_for_emp(owner)
        v2 = copy.deepcopy(v1)
        v2.update(self.envelope("grc", label or v1["sensitivity_label"], when))
        new_rules = [dict(r, value=rules.get(r["rule"], r["value"])) for r in v1["key_rules"]]
        v2.update({"policy_version_id": f"{pid}@v2", "version": 2, "supersedes": f"{pid}@v1", "version_status": "current",
                   "effective_from": effective, "effective_to": None, "approved_by": self.emp["Avery Lancaster"],
                   "key_rules": new_rules, "change_summary": summary})
        self.store.update("policy_version", f"{pid}@v1", {"version_status": "superseded", "effective_to": day_before(effective)}, when, actor, "policy_revision")
        self.store.insert("policy_version", v2, when, actor, "policy_revision")
        self.store.update("policy", pid, {"current_version": 2, **({"sensitivity_label": label} if label else {})}, when, actor, "policy_revision")
        doc_id = self.doc_of[("policy", pid)]
        self.policy_doc(pid, 2, when, supersedes=f"{doc_id}@v1", label=label, groups=groups or None)

    def new_incident(self, spec, when):
        row = self._incident_row(spec)
        row["created_at"] = row["updated_at"] = when
        self.incident[spec[0]] = row
        self.store.insert("incident", row, when, self.pid_for_emp(row["incident_commander_id"]), "new_record")
        self.incident_docs(spec[0], row, when)

    def erase(self, when):
        name, d = W.ERASURE
        eid = self.emp[name]
        actor = self.pid_for_emp(self.head_of("hr"))
        for dtype in ("employee_profile", "compensation_record", "performance_review"):
            doc_id = self.doc_of.get((dtype, eid))
            for dvid in sorted(k for k in list(self.store.tables["document_version"]) if doc_id and k.startswith(doc_id + "@")):
                self.store.delete("document_version", dvid, when, actor, "erasure_request", erased_subject=eid)
        for otype in self.policy["erasure"]["deletes_entity_types"]:
            for key in sorted(k for k, r in self.store.tables[otype].items() if r["employee_id"] == eid):
                self.store.delete(otype, key, when, actor, "erasure_request", erased_subject=eid)
        nulls = {f.split(".")[1]: None for f in self.policy["erasure"]["nulls_entity_fields"]}
        self.store.update("employee", eid, nulls, when, actor, "erasure_request")
        self.store.update("principal", "P-" + eid, {"principal_status": "deleted"}, when, actor, "erasure_request")

    # ------------------------------------------------------------------ outputs
    def finalize_events(self):
        events = self.store.events
        for e in events:
            e["event_id"] = f"EVT-{e['sequence']:06d}"
        delivered = list(events)
        notes = []
        # duplicate delivery: the FastTrack v2 contract version insert, delivered a second time three events later
        dup = next(e for e in events if e["object_type"] == "contract_version" and e["operation"] == "insert"
                   and e["object_id"] == f"{self.con['FastTrack Insurance Services']}@v2")
        copy_e = copy.deepcopy(dup)
        copy_e["emitted_at"] = plus_seconds(dup["emitted_at"], 2 * 3600)
        delivered.insert(delivered.index(dup) + 4, copy_e)
        notes.append({"event_id": dup["event_id"], "anomaly_type": "duplicate_delivery", "expected_handling": "ignore_redelivery",
                      "description": f"{dup['object_id']} insert delivered twice.", "batch_id": dup["batch_id"]})
        # out of order: the second Metropolitan customer update is delivered before the first
        _, seq_a, seq_b = next(a for a in self.anomalies if a[0] == "out_of_order")
        a = next(e for e in delivered if e["sequence"] == seq_a)
        b = next(e for e in delivered if e["sequence"] == seq_b)
        ia, ib = delivered.index(a), delivered.index(b)
        delivered[ia], delivered[ib] = b, a
        notes.append({"event_id": a["event_id"], "anomaly_type": "out_of_order", "expected_handling": "discard_stale_update",
                      "description": f"{a['object_id']} update with sequence {seq_a} arrives after sequence {seq_b}.", "batch_id": a["batch_id"]})
        self.delivered, self.cdc_notes = delivered, notes

    def write(self):
        out = SOURCE_ROOT
        t0 = self.t0_snapshot["tables"]
        for otype, plural in PLURAL.items():
            rows = sorted(t0[otype].values(), key=lambda r: r[_pk(otype)])
            _write_jsonl(out / "entities" / f"{plural}.jsonl", rows)
        for otype, fname in [("tenant", "tenants"), ("principal", "principals"), ("group", "groups"), ("membership", "memberships")]:
            _write_jsonl(out / "access_control" / f"{fname}.jsonl", sorted(t0[otype].values(), key=lambda r: r[_pk(otype)]))
        _write_jsonl(out / "relationships" / "edges.jsonl", self.store.edges)
        _write_jsonl(out / "cdc" / "events.jsonl", self.delivered)
        manifest = {"schema_version": "1.0", "dataset_version": "1.0.0", "generated_at": "2026-10-07T00:00:00Z", "generator_seed": W.SEED,
                    "t0_snapshot_at": W.T0, "batches": [{"batch_id": "BATCH-00", "label": "Initial load (T0 snapshot)", "scenario": "t0_snapshot",
                                                         "starts_at": W.T0, "ends_at": W.T0, "event_count": 0, "checkpoint_id": "CP-T0"}]}
        for bid, label, scenario, start, end in W.BATCHES:
            manifest["batches"].append({"batch_id": bid, "label": label, "scenario": scenario, "starts_at": start, "ends_at": end,
                                        "event_count": sum(1 for e in self.delivered if e["batch_id"] == bid),
                                        "checkpoint_id": "CP-" + bid.replace("BATCH-", "B")})
        (out / "cdc" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        _write_jsonl(out / "_build" / "document_plan.jsonl", list(self.docs.plan.values()))
        for dvid, entry in self.docs.plan.items():
            front = entry["front_matter"]
            text = self.docs.texts.get(dvid)
            if text is None:
                raise ValueError(f"{dvid}: no body")
            path = out / self.docs.body_path(front)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(front_matter_block(front) + text, encoding="utf-8")


def _pk(otype):
    return PK[otype]


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")


def main():
    w = World()
    w.build_t0()
    w.batch_01()
    w.batch_02()
    w.batch_03()
    w.batch_04()
    w.finalize_events()
    w.write()
    gt = build_ground_truth(w)
    print(json.dumps(gt["summary"], indent=2))


if __name__ == "__main__":
    main()

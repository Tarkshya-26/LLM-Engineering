"""Seed the Insurellm world from the original knowledge base.

    python -m datagen.seed_kb          (from the GovernedRAG root)

Writes data/source/seed/:
    id_registry.json   stable IDs, created once and reused on every later run
    kb_seed.json       every KB-derived value with the verbatim quote it came from
    kb_conflicts.json  contradictions inside the KB itself, with proposed handling

Nothing here invents a value. Unknown values stay null with a reason. The only
non-KB content is the ORG placement table in seed_employees.py, marked as a
seeding decision.
"""

import hashlib
import json
import re

from .kb import SEED_DIR, fact, load_kb
from .seed_contracts import INSURELLM_SIGNERS, extract_contracts, locate
from .seed_employees import extract_employees
from .seed_products import extract_products

PRODUCT_ORDER = ["Markellm", "Carllm", "Homellm", "Rellm", "Lifellm", "Healthllm", "Bizllm", "Claimllm"]
LOCATIONS = [  # (key, name, type, city, state, kb locator in company/overview.md)
    ("san-francisco", "San Francisco HQ", "headquarters", "San Francisco", "California", "offices in San Francisco (HQ)"),
    ("new-york", "New York office", "office", "New York", "New York", "New York, Austin, Chicago, and Denver"),
    ("austin", "Austin office", "office", "Austin", "Texas", "New York, Austin, Chicago, and Denver"),
    ("chicago", "Chicago office", "office", "Chicago", "Illinois", "New York, Austin, Chicago, and Denver"),
    ("denver", "Denver office", "office", "Denver", "Colorado", "New York, Austin, Chicago, and Denver"),
    ("remote-us", "Remote (US)", "remote_hub", None, None, "operating primarily remotely across the US"),
]


def _taglines(overview):
    out = {}
    for line in overview.text.splitlines():
        m = re.match(r"^- \*\*(\w+)\*\* - (.+)$", line)
        if m:
            out[m.group(1)] = fact(m.group(2).strip(), line)
    return out


def _company(kb):
    about, overview, careers = kb["company/about.md"], kb["company/overview.md"], kb["company/careers.md"]
    culture = kb["company/culture.md"]
    q = lambda f, loc: locate(f.text, loc, f.path)
    return {
        "kb_files": sorted(p for p in kb if p.startswith("company/")),
        "founded_year": fact(2015, q(about, "founded by Avery Lancaster in 2015"), "year"),
        "founder": fact("Avery Lancaster", q(about, "founded by Avery Lancaster in 2015")),
        "first_product": fact("Markellm", q(about, "Its first product was Markellm")),
        "peak_employees": fact(200, q(about, "peak of 200 employees"), "int"),
        "peak_year": fact(2020, q(about, "peak of 200 employees"), "year"),
        "peak_offices": fact(12, q(about, "12 offices across the US"), "int"),
        "stated_employees": fact(32, q(about, "team of 32 employees"), "int"),
        "stated_active_contracts": fact(32, q(about, "32 active contracts"), "int"),
        "headquarters": fact("San Francisco", q(about, "San Francisco headquarters")),
        "core_values": [fact(v, q(culture, f"### {v}")) for v in
                        ["Innovation First", "Customer Obsession", "Integrity & Transparency", "Collaborative Excellence"]],
        "stated_contracts_by_product": [fact(n, q(overview, loc), "int") for n, loc in [
            (7, "**Commercial Insurance (Bizllm)**: 7 contracts"), (7, "**Claims Processing (Claimllm)**: 7 contracts"),
            (6, "**Life Insurance (Lifellm)**: 6 contracts"), (6, "**Health Insurance (Healthllm)**: 6 contracts"),
            (3, "**Auto Insurance (Carllm)**: 3 contracts"), (4, "**Home Insurance (Homellm)**: 4 contracts"),
            (2, "**Insurance Marketplace (Markellm)**: 2 contracts"), (2, "**Reinsurance (Rellm)**: 2 contracts")]],
        "careers_file": careers.path,
        "product_taglines": _taglines(overview),
    }


def _locations(kb):
    overview = kb["company/overview.md"]
    return [{"key": key, "name": name, "location_type": kind, "city": city, "state": state,
             "evidence": fact(name, locate(overview.text, loc, overview.path), "derived")}
            for key, name, kind, city, state, loc in LOCATIONS]


def _registry(employees, products, contracts):
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    path = SEED_DIR / "id_registry.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    names = [e["full_name"]["value"] for e in employees]
    ordered = ["Avery Lancaster"] + sorted(n for n in names if n != "Avery Lancaster")
    customers = sorted(c["customer_display_name"]["value"] for c in contracts)
    registry = {
        "note": "Created once by datagen.seed_kb and never regenerated. Delete only to re-key the whole world.",
        "employees": {n: f"EMP-{i:03d}" for i, n in enumerate(ordered, 1)},
        "products": {n: f"PROD-{i:03d}" for i, n in enumerate(PRODUCT_ORDER, 1)},
        "customers": {n: f"CUST-{i:03d}" for i, n in enumerate(customers, 1)},
        "contracts": {n: f"CON-{i:03d}" for i, n in enumerate(customers, 1)},
        "locations": {key: f"LOC-{i:02d}" for i, (key, *_rest) in enumerate(LOCATIONS, 1)},
    }
    tier_n = 0
    registry["tiers"] = {}
    for p in sorted(products, key=lambda p: PRODUCT_ORDER.index(p["name"]["value"])):
        for t in p["tiers"]:
            tier_n += 1
            registry["tiers"][f'{p["name"]["value"]}/{t["tier_name"]["value"]}'] = f"TIER-{tier_n:03d}"
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return registry


def _conflicts(employees, contracts, company):
    signers = {}
    for c in contracts:
        s = c["insurellm_signatory"]
        if "name" in s:
            signers.setdefault(s["name"]["value"], []).append(c["customer_display_name"]["value"])
    hr_names = {e["full_name"]["value"] for e in employees}
    files_per_product = {}
    for c in contracts:
        files_per_product[c["product"]["value"]] = files_per_product.get(c["product"]["value"], 0) + 1
    placeholders = sorted(c["customer_display_name"]["value"] for c in contracts
                          if c["insurellm_signatory"].get("kind") == "placeholder" or c["signed_on"].get("kind") == "placeholder")
    templates = sorted(c["customer_display_name"]["value"] for c in contracts if c["insurellm_signatory"].get("is_template_name"))
    return [
        {"id": "KBC-01", "topic": "Two CEOs",
         "kb_says": ["employees/Avery Lancaster.md: Job Title 'Co-Founder & Chief Executive Officer (CEO)', 2015 - Present",
                     f"Jennifer Rodriguez signs as 'Chief Executive Officer' on {len(signers.get('Jennifer Rodriguez', []))} contracts (2025)"],
         "tests_depend_on": ["Jennifer Rodriguez, CEO of Insurellm, signed the DriveSmart contract", "Avery Lancaster, the founder, salary $225,000"],
         "proposed_handling": "Keep both texts verbatim. HR stays authoritative (Avery is CEO). Contract signatures are stored as printed, and Jennifer Rodriguez gets no HR record at T0."},
        {"id": "KBC-02", "topic": "Headcount",
         "kb_says": [f"company pages: 32 employees (2025); {len(hr_names)} HR files",
                     f"Insurellm signatories with no HR file: {sorted(n for n in signers if n in INSURELLM_SIGNERS and n not in hr_names)}"],
         "tests_depend_on": ["Insurellm currently operates with 32 employees as of 2025", "employees with salary under $80,000 (counted over the 32 files)"],
         "proposed_handling": "T0 HR = exactly the 32 files. New hires arrive only in CDC batches after T0, and the company pages get a v2 then (a freshness test)."},
        {"id": "KBC-03", "topic": "Contract counts",
         "kb_says": [f"overview/about per-line counts: {[f['value'] for f in company['stated_contracts_by_product']]} (sum {sum(f['value'] for f in company['stated_contracts_by_product'])})",
                     "about/overview: '32 active contracts'", f"contract files per product: {files_per_product}"],
         "tests_depend_on": ["Which product line has the most active contracts according to the company overview?"],
         "proposed_handling": "Keep the pages verbatim (the test asks 'according to the overview'). Entity truth = 32 contract files. New questions about counts cite the entities."},
        {"id": "KBC-04", "topic": "Homellm launch date",
         "kb_says": ["about.md lists Homellm among products added in the first five years (by 2020)", "products/Homellm.md roadmap: 'Q1 2024: Launch of Homellm version 1.0'"],
         "tests_depend_on": [],
         "proposed_handling": "launch_date stays null for Homellm; launch_order only for Markellm (first). No new question uses Homellm's launch date."},
        {"id": "KBC-05", "topic": "Template contracts",
         "kb_says": [f"unfilled placeholders ([Date], [Name]): {placeholders}", f"template signatory names (John Smith, Jane Smith, John Doe, Sarah Johnson): {templates}"],
         "tests_depend_on": [],
         "proposed_handling": "Placeholders stay null. Template names are kept as printed and never linked to an employee or principal."},
        {"id": "KBC-06", "topic": "'Active' contracts past their term",
         "kb_says": ["company pages: all 32 contracts active", "Velocity (Oct 2023, 12 months), BrightWay (Oct 2023, one year) and GreenField (Nov 2023, 12 months) state no renewal; their terms ended before 2025"],
         "tests_depend_on": [],
         "proposed_handling": "Keep status 'active' at T0 as the KB says; expire or renew them through CDC events in BATCH-01 (a lifecycle test)."},
        {"id": "KBC-07", "topic": "Maxine Thompson's title",
         "kb_says": ["Summary: 'Data Engineer'", "Career Progression: 'January 2021 - Present: Senior Data Engineer'"],
         "tests_depend_on": ["What product does the IIOTY award winner work on? (keyword 'Senior Data Engineer')"],
         "proposed_handling": "Text verbatim. The entity job_title uses the Summary field, with the career line recorded alongside."},
        {"id": "KBC-08", "topic": "Name collisions (not a conflict, a trap)",
         "kb_says": ["customer signatory 'Robert Chen' (Fortress) shares a name with employee Robert Chen",
                     "customer signatory 'Marcus Johnson' (Rapid Claims) shares a name with employee Marcus Johnson"],
         "tests_depend_on": [],
         "proposed_handling": "Keep. Annotate as a disambiguation trap; customer signatories are never linked to employees."},
    ]


def main():
    kb = load_kb()
    employees, products, contracts = extract_employees(kb), extract_products(kb), extract_contracts(kb)
    company, locations = _company(kb), _locations(kb)
    registry = _registry(employees, products, contracts)

    for e in employees:
        e["id"] = registry["employees"][e["full_name"]["value"]]
    for p in products:
        p["id"] = registry["products"][p["name"]["value"]]
        for t in p["tiers"]:
            t["id"] = registry["tiers"][f'{p["name"]["value"]}/{t["tier_name"]["value"]}']
    for c in contracts:
        name = c["customer_display_name"]["value"]
        c["id"], c["customer_id"] = registry["contracts"][name], registry["customers"][name]
        c["product_id"] = registry["products"][c["product"]["value"]]
    for loc in locations:
        loc["id"] = registry["locations"][loc["key"]]

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    seed = {"source": "Week5_RAG/knowledge-base", "employees": sorted(employees, key=lambda e: e["id"]),
            "products": sorted(products, key=lambda p: p["id"]), "contracts": contracts,
            "company": company, "locations": locations}
    (SEED_DIR / "kb_seed.json").write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    hashes = {path: hashlib.sha256(f.text.encode("utf-8")).hexdigest() for path, f in sorted(kb.items())}
    (SEED_DIR / "kb_file_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    (SEED_DIR / "kb_conflicts.json").write_text(json.dumps(_conflicts(employees, contracts, company), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"seeded {len(employees)} employees, {len(products)} products, "
          f"{sum(len(p['tiers']) for p in products)} tiers, {len(contracts)} contracts/customers, {len(locations)} locations")


if __name__ == "__main__":
    main()

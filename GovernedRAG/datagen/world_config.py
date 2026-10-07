"""Everything the generator adds to the seeded world, written out explicitly.

Nothing here restates a knowledge-base fact; KB facts come from seed/kb_seed.json.
All people and organisations below are fictional and use .example domains.
"""

SEED = 20251006
T0 = "2025-06-30T23:59:59Z"
T0_DATE = "2025-06-30"
ASSEMBLED_AT = "2025-06-30T00:00:00Z"     # creation time for seeded rows/documents whose source date is unknown

BATCHES = [
    # id, label, scenario, starts_at, ends_at
    ("BATCH-01", "Q3 rebuild: new functions, new customers, expirations", "mixed", "2025-07-01T00:00:00Z", "2025-08-15T23:59:59Z"),
    ("BATCH-02", "Contract amendments, renewals and a list-price change", "amendments_and_price_changes", "2025-08-16T00:00:00Z", "2025-09-30T23:59:59Z"),
    ("BATCH-03", "Access changes: transfer, re-org, termination, tenant suspension", "access_changes", "2025-10-01T00:00:00Z", "2025-10-31T23:59:59Z"),
    ("BATCH-04", "Archival, erasure and policy revisions", "archival_and_deletion", "2025-11-01T00:00:00Z", "2025-12-15T23:59:59Z"),
]

DEPARTMENTS = {  # code: (id, name, cost center, created in batch)
    "executive": ("DEPT-01", "Executive Office", "CC-1000", "BATCH-00"),
    "engineering": ("DEPT-02", "Engineering", "CC-2000", "BATCH-00"),
    "product": ("DEPT-03", "Product", "CC-3000", "BATCH-00"),
    "finance": ("DEPT-04", "Finance", "CC-4000", "BATCH-01"),
    "sales": ("DEPT-05", "Sales", "CC-5000", "BATCH-00"),
    "hr": ("DEPT-06", "People", "CC-6000", "BATCH-00"),
    "legal": ("DEPT-07", "Legal", "CC-7000", "BATCH-01"),
    "customer-success": ("DEPT-08", "Customer Success", "CC-8000", "BATCH-00"),
    "marketing": ("DEPT-09", "Marketing", "CC-9000", "BATCH-00"),
    "security": ("DEPT-10", "Security", "CC-1100", "BATCH-01"),
    "operations": ("DEPT-11", "Operations", "CC-1200", "BATCH-01"),
}
# department heads at T0 (sales has no senior leader in the KB: the CEO is acting head until BATCH-01)
T0_DEPARTMENT_HEADS = {"executive": "Avery Lancaster", "engineering": "James Wilson", "product": "Rachel Martinez",
                       "sales": "Avery Lancaster", "hr": "Amanda Foster", "customer-success": "Marcus Johnson",
                       "marketing": "Lisa Anderson"}

TEAMS = {  # key: (id, name, department, lead, location key, owned products, created in batch)
    "office-of-ceo": ("TEAM-01", "Office of the CEO", "executive", "Avery Lancaster", "san-francisco", [], "BATCH-00"),
    "personal-lines-platform": ("TEAM-02", "Personal Lines Platform", "engineering", "Robert Chen", "san-francisco",
                                ["Carllm", "Homellm", "Lifellm", "Healthllm"], "BATCH-00"),
    "commercial-platform": ("TEAM-03", "Commercial and Specialty Platform", "engineering", "Oliver Spencer", "austin",
                            ["Markellm", "Rellm", "Bizllm", "Claimllm"], "BATCH-00"),
    "infrastructure-quality": ("TEAM-04", "Infrastructure and Quality", "engineering", "David Kim", "new-york", [], "BATCH-00"),
    "data-ai": ("TEAM-05", "Data and AI", "engineering", "Priya Sharma", "san-francisco", [], "BATCH-00"),
    "product-management": ("TEAM-06", "Product Management", "product", "Rachel Martinez", "san-francisco", [], "BATCH-00"),
    "design": ("TEAM-07", "Design", "product", "Michelle Rivera", "new-york", [], "BATCH-00"),
    "account-executives": ("TEAM-08", "Account Executives", "sales", "Michael O'Brien", "chicago", [], "BATCH-00"),
    "sales-development": ("TEAM-09", "Sales Development", "sales", "Alex Thomson", "austin", [], "BATCH-00"),
    "marketing": ("TEAM-10", "Marketing", "marketing", "Lisa Anderson", "austin", [], "BATCH-00"),
    "people": ("TEAM-11", "People", "hr", "Amanda Foster", "san-francisco", [], "BATCH-00"),
    "customer-success": ("TEAM-12", "Customer Success", "customer-success", "Marcus Johnson", "new-york", [], "BATCH-00"),
    "finance": ("TEAM-13", "Finance", "finance", "Daniela Okafor", "san-francisco", [], "BATCH-01"),
    "legal": ("TEAM-14", "Legal", "legal", "Victor Almeida", "new-york", [], "BATCH-01"),
    "security": ("TEAM-15", "Security", "security", "Rohan Mehta", "san-francisco", [], "BATCH-01"),
    "support": ("TEAM-16", "Support", "customer-success", "Keisha Moore", "denver", [], "BATCH-01"),
    "operations": ("TEAM-17", "Operations", "operations", "Helen Voss", "chicago", [], "BATCH-01"),
}

# Product leadership (generated relationships; consistent with the KB where it says anything)
PRODUCT_LEADS = {  # product: (tech lead, product owner, design lead or None)
    "Markellm": ("Oliver Spencer", "Rachel Martinez", None),
    "Carllm": ("Alex Chen", "Rachel Martinez", None),
    "Homellm": ("Robert Chen", "Rachel Martinez", "Sarah Williams"),
    "Rellm": ("Oliver Spencer", "Rachel Martinez", "Michelle Rivera"),
    "Lifellm": ("Robert Chen", "Rachel Martinez", None),
    "Healthllm": ("Robert Chen", "Rachel Martinez", "Sarah Williams"),
    "Bizllm": ("Kevin Zhang", "Rachel Martinez", None),
    "Claimllm": ("Kevin Zhang", "Rachel Martinez", "Michelle Rivera"),
}
PRODUCT_CATEGORY = {"Markellm": "marketplace", "Carllm": "auto", "Homellm": "home", "Rellm": "reinsurance",
                    "Lifellm": "life", "Healthllm": "health", "Bizllm": "commercial", "Claimllm": "claims"}
SEGMENT = {"Markellm": "agency_broker", "Carllm": "auto_insurer", "Homellm": "home_insurer", "Rellm": "reinsurer",
           "Lifellm": "life_insurer", "Healthllm": "health_insurer", "Bizllm": "commercial_insurer", "Claimllm": "claims_services"}

# Account teams (generated). Account manager, customer success manager, extra members.
ACCOUNT_MANAGERS = {"Michael O'Brien": ["Carllm", "Homellm", "Rellm", "Markellm"], "Emily Carter": ["Lifellm", "Healthllm"],
                    "Carlos Rodriguez": ["Bizllm", "Claimllm"]}
ENTERPRISE_SE = "Carlos Rodriguez"          # solutions engineer added to every enterprise account team

PORTAL_CUSTOMERS = ["FastTrack Insurance Services", "National Claims Network", "DriveSmart Insurance",
                    "Metropolitan Life Group", "Heritage Life Assurance", "Harmony Health Plans"]
PUBLIC_REFERENCES = ["GlobalRe Partners", "Metropolitan Life Group", "United Healthcare Alliance"]
CUSTOMER_USERS = {  # customer: [(name, role, email local part)]
    "FastTrack Insurance Services": [("Dana Whitfield", "portal_admin", "dana.whitfield"), ("Leo Brandt", "portal_member", "leo.brandt")],
    "National Claims Network": [("Priscilla Owens", "portal_admin", "priscilla.owens"), ("Gabe Romero", "portal_member", "gabe.romero")],
    "DriveSmart Insurance": [("Nadia Kowal", "portal_admin", "nadia.kowal"), ("Ethan Price", "portal_member", "ethan.price")],
    "Metropolitan Life Group": [("Irene Castillo", "portal_admin", "irene.castillo"), ("Paul Henning", "portal_member", "paul.henning")],
    "Heritage Life Assurance": [("Ruth Okonkwo", "portal_admin", "ruth.okonkwo"), ("Simon Lake", "portal_member", "simon.lake")],
    "Harmony Health Plans": [("Vera Lindqvist", "portal_admin", "vera.lindqvist"), ("Omar Haddad", "portal_member", "omar.haddad")],
    "Northwind Mutual": [("Ada Fenwick", "portal_admin", "ada.fenwick"), ("Bruno Sato", "portal_member", "bruno.sato")],
}

# BATCH-01 hires: (name, title, level, department, team, manager, location, salary, employment type, dob, hire date)
HIRES = [
    ("Daniela Okafor", "Chief Financial Officer", "E2", "finance", "finance", "Avery Lancaster", "san-francisco", 240000, "full_time", "1979-06-02", "2025-07-07"),
    ("Martin Feld", "Financial Controller", "M2", "finance", "finance", "Daniela Okafor", "san-francisco", 165000, "full_time", "1984-02-19", "2025-07-14"),
    ("Hana Ishikawa", "Financial Analyst", "IC3", "finance", "finance", "Martin Feld", "chicago", 98000, "full_time", "1993-09-30", "2025-07-21"),
    ("Victor Almeida", "General Counsel", "E3", "legal", "legal", "Avery Lancaster", "new-york", 230000, "full_time", "1977-11-11", "2025-07-07"),
    ("Grace Liang", "Legal Counsel", "IC4", "legal", "legal", "Victor Almeida", "london", 145000, "full_time", "1988-04-25", "2025-07-28"),
    ("Rohan Mehta", "Chief Information Security Officer", "E3", "security", "security", "Avery Lancaster", "san-francisco", 235000, "full_time", "1981-01-14", "2025-07-07"),
    ("Ingrid Solberg", "Senior Security Engineer", "IC5", "security", "security", "Rohan Mehta", "denver", 175000, "full_time", "1987-08-08", "2025-07-21"),
    ("Tomas Kral", "Security Incident Responder", "IC3", "security", "security", "Rohan Mehta", "new-york", 118000, "full_time", "1994-03-03", "2025-07-28"),
    ("Naomi Brandt", "Chief People Officer", "E3", "hr", "people", "Avery Lancaster", "san-francisco", 220000, "full_time", "1980-12-01", "2025-07-07"),
    ("Felix Ortega", "Compensation and Benefits Manager", "M1", "hr", "people", "Naomi Brandt", "austin", 132000, "full_time", "1986-05-17", "2025-07-21"),
    ("Keisha Moore", "Head of Support", "M2", "customer-success", "support", "Marcus Johnson", "denver", 128000, "full_time", "1985-10-09", "2025-07-14"),
    ("Arjun Rao", "Senior Support Engineer", "IC4", "customer-success", "support", "Keisha Moore", "austin", 104000, "full_time", "1990-07-22", "2025-07-21"),
    ("Owen Gallagher", "Support Engineer", "IC2", "customer-success", "support", "Keisha Moore", "denver", 78000, "full_time", "1996-02-11", "2025-07-28"),
    ("Lucia Ferraro", "Support Engineer", "IC2", "customer-success", "support", "Keisha Moore", "remote-us", 78000, "full_time", "1997-06-05", "2025-07-28"),
    ("Helen Voss", "Chief Operating Officer", "E2", "operations", "operations", "Avery Lancaster", "chicago", 245000, "full_time", "1976-09-27", "2025-07-07"),
    ("Samir Haddad", "IT Operations Manager", "M1", "operations", "operations", "Helen Voss", "chicago", 125000, "full_time", "1983-03-29", "2025-07-21"),
    ("Claire Dubois", "Director of Sales", "M3", "sales", "account-executives", "Avery Lancaster", "chicago", 185000, "full_time", "1982-11-30", "2025-07-14"),
    ("Mateo Silva", "Contract Software Engineer", "IC3", "engineering", "commercial-platform", "Oliver Spencer", "remote-us", None, "contractor", "1991-01-19", "2025-08-04"),
]
REMOTE_CITIES = {"Lucia Ferraro": "Boise, Idaho", "Mateo Silva": "Tucson, Arizona"}
NEW_DEPARTMENT_HEADS = {"finance": "Daniela Okafor", "legal": "Victor Almeida", "security": "Rohan Mehta",
                        "operations": "Helen Voss", "sales": "Claire Dubois", "hr": "Naomi Brandt"}
LONDON = ("london", "LOC-07", "London office", "office", "London", None, "GB", "uk", "Europe/London", "2025-07-01")

# BATCH-01 new customers and contracts
NEW_CUSTOMERS = [  # display, legal, product, tier name, monthly fee, term months, effective, city, country, region, currency, portal
    ("Northwind Mutual", "Northwind Mutual Insurance Company", "Carllm", "Professional Tier", 2500, 12, "2025-07-15", "Columbus", "US", "us", "USD", True),
    ("Harborline Assurance", "Harborline Assurance, Inc.", "Homellm", "Standard Tier", 10000, 24, "2025-08-01", "Portland", "US", "us", "USD", False),
    ("Crestview Re", "Crestview Reinsurance Ltd.", "Rellm", "Professional Plan", 8000, 24, "2025-08-11", "London", "GB", "uk", "GBP", False),
]
EXPIRE_IN_BATCH_01 = ["Velocity Auto Solutions", "BrightWay Solutions", "GreenField Holdings"]

# BATCH-02 contract changes: customer -> (date signed, change type, effective from, changes dict, summary)
AMENDMENTS = {
    "FastTrack Insurance Services": ("2025-08-20", "amendment", "2025-09-01",
        {"monthly_fee": 10250, "volume": ("projected_claims_year_1", 24000)}, "Projected year-1 claims 22,000 -> 24,000; fee $9,500 -> $10,250"),
    "Atlantic Risk Solutions": ("2025-08-22", "amendment", "2025-09-01",
        {"monthly_fee": 14700, "user_licenses": 50}, "User licenses 35 -> 50; fee $12,000 -> $14,700"),
    "Harmony Health Plans": ("2025-08-28", "amendment", "2025-09-15",
        {"monthly_fee": 17250, "user_licenses": 75, "volume": ("covered_members", 45000)}, "Members 38,000 -> 45,000; licenses 60 -> 75; fee $15,000 -> $17,250"),
    "Rapid Claims Associates": ("2025-08-29", "amendment", "2025-09-01",
        {"tier": "Advanced Tier", "monthly_fee": 9500}, "Tier Core -> Advanced; fee $4,500 -> $9,500"),
    "Summit Commercial Insurance": ("2025-09-03", "amendment", "2025-10-01",
        {"tier": "Professional Tier", "monthly_fee": 12000}, "Tier Business -> Professional from October 1, 2025; fee $6,000 -> $12,000"),
    "Guardian Life Partners": ("2025-09-05", "amendment", "2025-09-15",
        {"monthly_fee": 9300, "user_licenses": 40}, "User licenses 25 -> 40; fee $7,500 -> $9,300"),
    "Roadway Insurance Inc.": ("2025-09-10", "renewal", "2026-01-01",
        {"monthly_fee": 2750, "term_months": 12, "term_end": "2026-12-31"}, "Renewed for 12 months at the new Professional list price of $2,750"),
    "Evergreen Life Insurance": ("2025-09-12", "renewal", "2026-01-20",
        {"term_months": 12, "term_end": "2027-01-19"}, "Renewed for 12 months on unchanged terms"),
    "WellCare Insurance Co.": ("2025-09-17", "renewal", "2026-03-08",
        {"monthly_fee": 8400, "term_months": 12, "term_end": "2027-03-07"}, "Renewed for 12 months; fee $8,000 -> $8,400"),
    "DriveSmart Insurance": ("2025-09-22", "amendment", "2025-10-20",
        {"add_scope": "Claimllm", "addon_monthly": 6000}, "Adds Claimllm to scope from contract month 8 (October 20, 2025) at +$6,000 per month"),
    "Heritage Life Assurance": ("2025-09-24", "amendment", "2025-10-01",
        {"volume": ("active_policies", 8000)}, "Administered policies 6,200 -> 8,000; fee unchanged"),
}
CARLLM_PRICE_CHANGE = ("2025-09-15", "2025-10-01", "Professional Tier", 2750)   # signed, effective, tier, new price

# BATCH-03 access changes
TRANSFER = ("Emily Carter", "2025-10-06", "Revenue Analyst", "IC3", "finance", "finance", "Martin Feld")
REORG = ("Maya Thompson", "2025-10-13", "infrastructure-quality", "David Kim")
TERMINATION = ("Daniel Park", "2025-10-17")
SUSPEND_TENANT = ("Heritage Life Assurance", "2025-10-20")
DISABLE_CUSTOMER_USER = ("FastTrack Insurance Services", "portal_member", "2025-10-22")
ACCOUNT_TEAM_SHUFFLE = ("Metropolitan Life Group", "2025-10-27")     # two quick updates; delivered out of order

# BATCH-04
ERASURE = ("Daniel Park", "2025-11-20")
POLICY_REVISIONS = {  # policy title: (date, effective, rule changes, summary, tightened label or None, groups)
    "Remote Work Policy": ("2025-11-05", "2025-12-01", {"office_days_per_week_for_office_based_staff": 2}, "Office-based staff: 2 office days per week (was optional)", None, []),
    "Expense and Travel Policy": ("2025-11-12", "2025-12-01", {"meal_limit_per_day_usd": 85}, "Daily meal limit $75 -> $85", None, []),
    # v2 documents concrete control settings, so it is tightened: exercises the approved historical-version rule
    "Access Control Policy": ("2025-11-19", "2025-12-01", {"access_review_frequency_months": 3}, "Access reviews every 3 months (was 6); now lists control settings",
                              "confidential", ["GRP-engineering", "GRP-security", "GRP-executive"]),
}

PERSONAS = [  # id, principal key, label, archetype, intended use, description
    ("PERS-01", "svc:baseline", "Baseline evaluator", "baseline_evaluator", "baseline_eval", "Reruns the original 150 tests at T0. Never used for governance results."),
    ("PERS-02", "emp:Avery Lancaster", "CEO", "executive", "governance_eval", "Founder and CEO; board and HR compensation member."),
    ("PERS-03", "emp:Emily Carter", "Account executive, moves to Finance in BATCH-03", "sales_rep", "governance_eval", "Account manager for Lifellm and Healthllm customers until her transfer."),
    ("PERS-04", "emp:Michael O'Brien", "Senior account manager", "account_manager", "governance_eval", "Owns Carllm, Homellm, Rellm and Markellm accounts."),
    ("PERS-05", "emp:Amanda Foster", "HR business partner", "hr_partner", "governance_eval", "Reads reviews; never compensation."),
    ("PERS-06", "emp:Maxine Thompson", "Data engineer", "engineer", "governance_eval", "Individual contributor in Data and AI."),
    ("PERS-07", "emp:Priya Sharma", "Data and AI manager", "people_manager", "governance_eval", "Direct manager of the data team until the BATCH-03 re-org."),
    ("PERS-08", "emp:James Wilson", "CTO (skip-level)", "executive", "governance_eval", "Skip-level manager for engineering ICs; board member."),
    ("PERS-09", "emp:Brandon Walker", "Technical support specialist", "support_agent", "governance_eval", "Reads tickets in every customer tenant."),
    ("PERS-10", "cus:FastTrack Insurance Services:portal_admin", "FastTrack portal admin", "customer_portal_user", "governance_eval", "Customer user; sees public data and the FastTrack tenant only."),
    ("PERS-11", "cus:National Claims Network:portal_admin", "National Claims portal admin", "customer_portal_user", "governance_eval", "Same product as FastTrack: lookalike tickets."),
    ("PERS-12", "emp:Hana Ishikawa", "Financial analyst (from BATCH-01)", "finance_analyst", "governance_eval", "Finance; no board or deal-desk access."),
    ("PERS-13", "emp:Felix Ortega", "Compensation and benefits manager (from BATCH-01)", "hr_comp_admin", "governance_eval", "The only non-executive with pay access."),
    ("PERS-14", "emp:Tomas Kral", "Security incident responder (from BATCH-01)", "security_analyst", "governance_eval", "Reads full incident reports."),
    ("PERS-15", "emp:Mateo Silva", "Contract engineer (from BATCH-01)", "contractor", "governance_eval", "Contractor: public and internal only."),
    ("PERS-16", "emp:Daniel Park", "QA engineer, terminated in BATCH-03, erased in BATCH-04", "former_employee", "governance_eval", "Tests disabled principals and erasure."),
]

"""Generated (non-KB) content that exists at T0 or arrives in batches.

Bodies are written in the document-generation phase from these specs plus entity
rows; here we only fix the structured facts every body must state.
"""

PROJECTS = [  # key, name, codename, type, team, sponsor, lead, members, products, customers, status, start, target, completed, budget, label, created batch
    ("telematics", "Carllm telematics-based pricing", None, "product_feature", "personal-lines-platform", "Rachel Martinez", "Alex Chen",
     ["Alex Chen", "Tyler Brooks", "Samuel Trenton"], ["Carllm"], [], "active", "2025-01-13", "2025-09-30", None, 180000, "internal"),
    ("homellm-v2", "Homellm 2.0 release", None, "product_feature", "personal-lines-platform", "Rachel Martinez", "Robert Chen",
     ["Robert Chen", "Sarah Williams"], ["Homellm"], [], "completed", "2024-07-01", "2025-03-31", "2025-03-28", 240000, "internal"),
    ("rellm-v2", "Rellm 2.0 redesign", None, "product_feature", "commercial-platform", "Rachel Martinez", "Oliver Spencer",
     ["Oliver Spencer", "Jessica Liu", "Michelle Rivera"], ["Rellm"], [], "active", "2025-02-03", "2026-09-30", None, 310000, "internal"),
    ("claimllm-cv", "Claimllm computer vision damage assessment", None, "product_feature", "commercial-platform", "Rachel Martinez", "Kevin Zhang",
     ["Kevin Zhang", "Priya Sharma", "Jordan K. Bishop"], ["Claimllm"], [], "active", "2025-03-03", "2025-09-30", None, 220000, "internal"),
    ("healthllm-analytics", "Healthllm predictive analytics module", None, "data", "data-ai", "Rachel Martinez", "Samuel Trenton",
     ["Samuel Trenton", "Maya Thompson", "Nina Patel"], ["Healthllm"], [], "active", "2025-04-07", "2025-09-30", None, 150000, "internal"),
    ("warehouse", "Data warehouse migration", None, "data", "data-ai", "James Wilson", "Maxine Thompson",
     ["Maxine Thompson", "Maya Thompson"], [], [], "completed", "2021-01-11", "2021-12-17", "2021-12-15", 95000, "internal"),
    ("soc2", "SOC 2 Type II renewal", None, "compliance", "infrastructure-quality", "James Wilson", "David Kim",
     ["David Kim", "Daniel Park"], [], [], "active", "2025-05-05", "2025-11-28", None, 60000, "internal"),
    ("lifellm-health", "Lifellm digital health integrations", None, "product_feature", "personal-lines-platform", "Rachel Martinez", "Robert Chen",
     ["Robert Chen"], ["Lifellm"], [], "proposed", "2025-06-16", "2025-12-19", None, None, "internal"),
    ("portal", "Customer portal for support tickets", None, "internal_tools", "commercial-platform", "Marcus Johnson", "Jordan K. Bishop",
     ["Jordan K. Bishop", "Brandon Walker"], [], ["FastTrack Insurance Services", "DriveSmart Insurance"], "completed", "2024-10-07", "2025-04-30", "2025-04-25", 85000, "internal"),
    ("lighthouse", "Acquisition of a claims analytics startup", "Project Lighthouse", "corporate_development", "office-of-ceo", "Avery Lancaster", "James Wilson",
     ["Avery Lancaster", "James Wilson"], ["Claimllm"], [], "active", "2025-05-12", "2025-12-15", None, 4500000, "restricted"),
]
LIGHTHOUSE_ADD_MEMBERS = ("2025-07-30", ["Daniela Okafor", "Victor Almeida"])
ARCHIVE_PROJECTS = [("homellm-v2", "2025-11-03"), ("warehouse", "2025-11-03")]

POLICIES = [  # title, area, owner department at T0, owner, applies_to, key rules, label, groups if confidential
    ("Information Security Policy", "security", "engineering", "James Wilson", "all_employees",
     {"password_min_length": 14, "mfa_required": True}, "internal", []),
    ("Acceptable Use Policy", "it", "engineering", "James Wilson", "all_employees", {"personal_use_allowed": True}, "internal", []),
    ("Remote Work Policy", "hr", "hr", "Amanda Foster", "all_employees", {"office_days_per_week_for_office_based_staff": "optional"}, "internal", []),
    ("Data Retention Policy", "privacy", "engineering", "James Wilson", "all_employees", {"hr_record_retention_years": 7, "support_ticket_retention_years": 3}, "internal", []),
    ("Expense and Travel Policy", "finance", "executive", "Avery Lancaster", "all_employees", {"meal_limit_per_day_usd": 75}, "internal", []),
    ("Code of Conduct", "hr", "hr", "Amanda Foster", "all_employees", {"annual_attestation": True}, "internal", []),
    ("Incident Response Plan", "security", "engineering", "James Wilson", "engineering",
     {"sev1_response_minutes": 15, "customer_notice_hours": 72}, "confidential", ["GRP-engineering", "GRP-security"]),
    ("Access Control Policy", "security", "engineering", "James Wilson", "all_employees", {"access_review_frequency_months": 6}, "internal", []),
    ("Privacy and PHI Handling Policy", "privacy", "engineering", "James Wilson", "customer_facing", {"phi_encryption_required": True}, "internal", []),
    ("Vendor Management Policy", "operations", "executive", "Avery Lancaster", "managers", {"security_review_over_usd": 10000}, "internal", []),
    ("Leave Policy", "hr", "hr", "Amanda Foster", "all_employees", {"pto_days_per_year": 25}, "internal", []),
    ("Anti-Harassment Policy", "hr", "hr", "Amanda Foster", "all_employees", {"training_frequency_months": 12}, "internal", []),
]

INCIDENTS = [  # key, title, severity, category, status, detected, resolved, commander, responders, products, customers, records, root cause, notify, batch
    ("phish-2023", "Credential phishing campaign against sales staff", "SEV3", "phishing", "closed", "2023-08-14T15:20:00Z", "2023-08-15T11:00:00Z",
     "David Kim", ["David Kim"], [], [], 0, "credential_compromise", False, "BATCH-00"),
    ("carllm-outage", "Carllm quoting API outage", "SEV2", "availability", "closed", "2024-11-19T13:05:00Z", "2024-11-19T17:40:00Z",
     "David Kim", ["David Kim", "Alex Chen"], ["Carllm"], ["TechDrive Insurance"], 0, "software_defect", True, "BATCH-00"),
    ("rellm-vuln", "Dependency vulnerability in Rellm dashboard", "SEV3", "vulnerability", "closed", "2024-09-09T09:30:00Z", "2024-09-11T18:00:00Z",
     "Oliver Spencer", ["Oliver Spencer", "Jessica Liu"], ["Rellm"], ["Stellar Insurance Co."], 0, "software_defect", False, "BATCH-00"),
    ("healthllm-export", "Misconfigured storage bucket exposed Healthllm export files", "SEV2", "data_exposure", "closed", "2025-03-14T02:10:00Z",
     "2025-03-14T09:45:00Z", "David Kim", ["David Kim", "Robert Chen"], ["Healthllm"], ["Harmony Health Plans"], 1200, "misconfiguration", True, "BATCH-00"),
    ("markellm-access", "Former contractor account used after offboarding", "SEV3", "access_misuse", "closed", "2025-05-06T08:00:00Z",
     "2025-05-06T12:30:00Z", "David Kim", ["David Kim"], ["Markellm"], [], 0, "human_error", False, "BATCH-00"),
    ("claimllm-vendor", "OCR vendor outage delayed Claimllm document processing", "SEV2", "third_party", "closed", "2025-11-10T07:15:00Z",
     "2025-11-10T19:30:00Z", "Rohan Mehta", ["Rohan Mehta", "Tomas Kral", "Kevin Zhang"], ["Claimllm"],
     ["FastTrack Insurance Services", "National Claims Network"], 0, "vendor_failure", True, "BATCH-04"),
]
# Only the BATCH-04 incident gets a sanitised postmortem (built in build_world.batch_04). The T0 incidents have
# restricted reports only; the sanitised-postmortem scenario is covered once, by design (dataset held at 372 versions).
POSTMORTEMS = ["claimllm-vendor"]

# Support tickets: customer, product, subject, priority, status, opened, resolved, injection?, lookalike group, batch
TICKETS = [
    ("FastTrack Insurance Services", "Claimllm", "FNOL intake rejecting photos larger than 10 MB", "P2", "resolved", "2025-06-03T14:22:00Z", "2025-06-04T10:05:00Z", False, "claim-fnol", "BATCH-00"),
    ("FastTrack Insurance Services", "Claimllm", "Duplicate claim numbers after bulk import", "P2", "resolved", "2025-05-21T09:10:00Z", "2025-05-22T16:00:00Z", False, None, "BATCH-00"),
    ("FastTrack Insurance Services", "Claimllm", "Request for adjuster training refresher dates", "P4", "closed", "2025-05-28T13:00:00Z", "2025-05-29T09:30:00Z", False, None, "BATCH-00"),
    ("FastTrack Insurance Services", "Claimllm", "Export of fraud scores to our BI tool", "P3", "open", "2025-06-24T11:45:00Z", None, True, None, "BATCH-00"),
    ("FastTrack Insurance Services", "Claimllm", "Reserve recommendations missing for glass claims", "P3", "pending_customer", "2025-06-27T15:05:00Z", None, False, None, "BATCH-00"),
    ("National Claims Network", "Claimllm", "FNOL intake times out on large photo uploads", "P2", "resolved", "2025-06-05T10:40:00Z", "2025-06-06T12:15:00Z", False, "claim-fnol", "BATCH-00"),
    ("National Claims Network", "Claimllm", "SSO login loop for adjusters", "P1", "resolved", "2025-05-12T07:55:00Z", "2025-05-12T10:20:00Z", False, None, "BATCH-00"),
    ("National Claims Network", "Claimllm", "Vendor payment split rounding error", "P2", "resolved", "2025-06-10T16:30:00Z", "2025-06-12T11:00:00Z", False, None, "BATCH-00"),
    ("National Claims Network", "Claimllm", "Need audit log export for regulator", "P3", "open", "2025-06-26T09:00:00Z", None, False, None, "BATCH-00"),
    ("National Claims Network", "Claimllm", "Dashboard shows wrong week-over-week totals", "P3", "open", "2025-06-29T14:10:00Z", None, False, None, "BATCH-00"),
    ("DriveSmart Insurance", "Carllm", "Telematics feed missing trips from one device model", "P2", "open", "2025-06-18T08:30:00Z", None, False, None, "BATCH-00"),
    ("DriveSmart Insurance", "Carllm", "Quote API latency above SLA in the morning peak", "P1", "resolved", "2025-05-02T08:05:00Z", "2025-05-02T13:00:00Z", False, None, "BATCH-00"),
    ("DriveSmart Insurance", "Carllm", "White-label theme not applied to emails", "P3", "resolved", "2025-04-15T10:00:00Z", "2025-04-17T09:00:00Z", False, None, "BATCH-00"),
    ("DriveSmart Insurance", "Carllm", "Question about data residency for driver data", "P3", "closed", "2025-04-28T12:00:00Z", "2025-04-29T15:00:00Z", True, None, "BATCH-00"),
    ("DriveSmart Insurance", "Carllm", "Bulk policy import fails on 8 states file", "P2", "resolved", "2025-06-09T09:45:00Z", "2025-06-10T17:30:00Z", False, None, "BATCH-00"),
    ("Metropolitan Life Group", "Lifellm", "Underwriting rules not applied to group policies", "P2", "resolved", "2025-05-19T11:00:00Z", "2025-05-21T10:00:00Z", False, "life-uw", "BATCH-00"),
    ("Metropolitan Life Group", "Lifellm", "Request: extra admin seats for the claims team", "P4", "closed", "2025-06-02T09:20:00Z", "2025-06-02T15:00:00Z", False, None, "BATCH-00"),
    ("Metropolitan Life Group", "Lifellm", "Disaster recovery test schedule", "P3", "resolved", "2025-06-16T13:00:00Z", "2025-06-18T09:00:00Z", False, None, "BATCH-00"),
    ("Metropolitan Life Group", "Lifellm", "Policy documents render with wrong font", "P4", "open", "2025-06-25T10:30:00Z", None, False, None, "BATCH-00"),
    ("Metropolitan Life Group", "Lifellm", "API rate limits during month-end", "P2", "open", "2025-06-28T08:15:00Z", None, False, None, "BATCH-00"),
    ("Heritage Life Assurance", "Lifellm", "Underwriting rules skipped for some group policies", "P2", "resolved", "2025-05-22T14:00:00Z", "2025-05-23T16:30:00Z", False, "life-uw", "BATCH-00"),
    ("Heritage Life Assurance", "Lifellm", "Digital health integration consent screen", "P3", "open", "2025-06-12T10:00:00Z", None, False, None, "BATCH-00"),
    ("Heritage Life Assurance", "Lifellm", "Invoice shows wrong billing contact", "P4", "resolved", "2025-06-20T09:00:00Z", "2025-06-20T15:00:00Z", False, None, "BATCH-00"),
    ("Heritage Life Assurance", "Lifellm", "Training session for new underwriters", "P4", "closed", "2025-04-30T11:30:00Z", "2025-05-02T10:00:00Z", False, None, "BATCH-00"),
    ("Heritage Life Assurance", "Lifellm", "Policy count on dashboard out of date", "P3", "pending_customer", "2025-06-27T16:20:00Z", None, False, None, "BATCH-00"),
    ("Harmony Health Plans", "Healthllm", "Eligibility checks slow for one payer", "P2", "resolved", "2025-05-08T09:00:00Z", "2025-05-09T12:00:00Z", False, None, "BATCH-00"),
    ("Harmony Health Plans", "Healthllm", "Follow-up on the March export incident", "P1", "closed", "2025-03-14T10:00:00Z", "2025-03-20T17:00:00Z", False, None, "BATCH-00"),
    ("Harmony Health Plans", "Healthllm", "Member portal password reset emails delayed", "P3", "resolved", "2025-06-11T13:40:00Z", "2025-06-12T10:00:00Z", False, None, "BATCH-00"),
    ("Harmony Health Plans", "Healthllm", "Need a copy of our member data processing addendum", "P3", "open", "2025-06-23T15:30:00Z", None, True, None, "BATCH-00"),
    ("Harmony Health Plans", "Healthllm", "Claims adjudication codes for new state", "P2", "open", "2025-06-30T09:05:00Z", None, False, None, "BATCH-00"),
    # after T0
    ("Northwind Mutual", "Carllm", "Onboarding: SSO configuration", "P3", "resolved", "2025-07-22T10:00:00Z", "2025-07-23T12:00:00Z", False, None, "BATCH-01"),
    ("Northwind Mutual", "Carllm", "Rating factors import template", "P3", "resolved", "2025-08-04T09:30:00Z", "2025-08-05T11:00:00Z", False, None, "BATCH-01"),
    ("FastTrack Insurance Services", "Claimllm", "Claims volume approaching tier limit", "P3", "resolved", "2025-07-28T14:00:00Z", "2025-08-01T10:00:00Z", False, None, "BATCH-01"),
    ("DriveSmart Insurance", "Carllm", "Telematics trips still missing after fix", "P2", "resolved", "2025-07-08T08:45:00Z", "2025-07-10T16:00:00Z", False, None, "BATCH-01"),
    ("Harmony Health Plans", "Healthllm", "Adding a fourth state to coverage", "P3", "resolved", "2025-08-11T13:00:00Z", "2025-08-14T10:00:00Z", False, None, "BATCH-01"),
    ("National Claims Network", "Claimllm", "Audit log export delivered, need CSV", "P3", "resolved", "2025-07-15T09:00:00Z", "2025-07-16T11:30:00Z", False, None, "BATCH-01"),
    ("Harmony Health Plans", "Healthllm", "Adding 15 more user licenses", "P3", "resolved", "2025-08-18T10:00:00Z", "2025-08-22T15:00:00Z", False, None, "BATCH-02"),
    ("Metropolitan Life Group", "Lifellm", "Rate limits again at month-end", "P2", "resolved", "2025-08-29T08:00:00Z", "2025-08-30T12:00:00Z", False, None, "BATCH-02"),
    ("DriveSmart Insurance", "Carllm", "Enabling Claimllm for our claims team", "P3", "resolved", "2025-09-24T10:00:00Z", "2025-09-29T16:00:00Z", False, None, "BATCH-02"),
    ("Heritage Life Assurance", "Lifellm", "Dashboard policy count still stale", "P3", "resolved", "2025-09-02T09:00:00Z", "2025-09-03T15:00:00Z", False, None, "BATCH-02"),
    ("FastTrack Insurance Services", "Claimllm", "New adjusters cannot see assigned claims", "P2", "resolved", "2025-09-08T08:30:00Z", "2025-09-08T14:00:00Z", False, None, "BATCH-02"),
    ("Northwind Mutual", "Carllm", "Question about the new Professional list price", "P4", "closed", "2025-09-26T11:00:00Z", "2025-09-26T15:00:00Z", False, None, "BATCH-02"),
    ("Harmony Health Plans", "Healthllm", "Two new users need access", "P4", "resolved", "2025-10-08T10:00:00Z", "2025-10-08T13:00:00Z", False, None, "BATCH-03"),
    ("National Claims Network", "Claimllm", "Vendor payment export missing tax field", "P3", "resolved", "2025-10-14T09:15:00Z", "2025-10-15T12:00:00Z", False, None, "BATCH-03"),
    ("Metropolitan Life Group", "Lifellm", "Who is our account manager now?", "P4", "closed", "2025-10-28T10:00:00Z", "2025-10-28T14:00:00Z", False, None, "BATCH-03"),
    ("FastTrack Insurance Services", "Claimllm", "Document processing delays this morning", "P1", "resolved", "2025-11-10T08:00:00Z", "2025-11-10T20:00:00Z", False, None, "BATCH-04"),
    ("National Claims Network", "Claimllm", "OCR backlog after vendor outage", "P1", "resolved", "2025-11-10T08:20:00Z", "2025-11-11T09:00:00Z", False, None, "BATCH-04"),
    ("DriveSmart Insurance", "Carllm", "Year-end policy export", "P3", "open", "2025-12-08T10:00:00Z", None, False, None, "BATCH-04"),
]

WIKI_PAGES = [  # document_type, title, owner department, products/subjects, batch
    *[("technical_architecture", f"{p} architecture overview", "engineering", [p], "BATCH-00")
      for p in ["Markellm", "Carllm", "Homellm", "Rellm", "Lifellm", "Healthllm", "Bizllm", "Claimllm"]],
    ("runbook", "Production incident escalation runbook", "engineering", [], "BATCH-00"),
    ("runbook", "Deployment and rollback runbook", "engineering", [], "BATCH-00"),
    ("runbook", "On-call handbook", "engineering", [], "BATCH-00"),
    ("runbook", "Claimllm FNOL intake troubleshooting", "engineering", ["Claimllm"], "BATCH-00"),
    ("runbook", "Healthllm PHI handling procedures", "engineering", ["Healthllm"], "BATCH-00"),
    ("runbook", "Backup and restore runbook", "engineering", [], "BATCH-00"),
    ("employee_handbook", "Employee handbook: benefits and time off", "hr", [], "BATCH-00"),
    ("employee_handbook", "Employee handbook: tools and onboarding", "hr", [], "BATCH-00"),
    ("meeting_notes", "All-hands notes, 2025 Q1", "executive", [], "BATCH-00"),
    ("meeting_notes", "All-hands notes, 2025 Q2", "executive", [], "BATCH-00"),
]

PRESS_RELEASES = [  # title, date, customers named, products, facts the release may state
    ("GlobalRe Partners selects Rellm for global treaty administration", "2025-05-06", ["GlobalRe Partners"], ["Rellm"], ["term_months"]),
    ("Metropolitan Life Group partners with Insurellm on Lifellm", "2025-04-14", ["Metropolitan Life Group"], ["Lifellm"], ["term_months"]),
    ("United Healthcare Alliance chooses Healthllm", "2025-05-22", ["United Healthcare Alliance"], ["Healthllm"], ["term_months"]),
    ("Insurellm launches Claimllm", "2025-01-15", [], ["Claimllm"], []),
]
ACCOUNT_PLAN_CUSTOMERS = ["DriveSmart Insurance", "GlobalRe Partners", "Metropolitan Life Group",
                          "National Claims Network", "SafeHaven Property Insurance", "United Healthcare Alliance"]
PRICING_APPROVALS_T0 = ["DriveSmart Insurance", "GlobalRe Partners", "United Healthcare Alliance"]
PRICING_APPROVALS_B02 = ["DriveSmart Insurance", "Atlantic Risk Solutions"]

# Seeded pages that get a patched v2 when headcount changes (BATCH-01). Exact phrases only.
HEADCOUNT_PATCHES = {
    "company/about.md": [("team of 32 employees", "team of {n} employees")],
    "company/overview.md": [("with 32 employees", "with {n} employees")],
    "company/careers.md": [("company with 32 highly talented employees", "company with {n} highly talented employees")],
    "company/culture.md": [("elite team of 32 exceptional professionals", "elite team of {n} exceptional professionals")],
}

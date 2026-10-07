"""Extract the 32 original contracts.

The contract files are too irregular for one parser (templates with [Date] and
[Name], stepped enterprise pricing, missing numbers), so values are written out
here by hand. Each value carries a locator: a short phrase from the source. The
extractor finds the line containing the locator and stores it as the quote, and
check_seed.py proves the value appears in that quote. A value can therefore not
be typed wrong without the check failing.

Locator forms:
    "phrase"                 -> the first line containing the phrase
"""

from .kb import fact, normalize, unknown

PH = "placeholder"   # signature block left as a template ([Name], John Smith, ...)

# customer -> fields. Keys follow the KB file name "Contract with <customer> for <product>.md".
# money values are whole dollars; schedule rows are (from_month, to_month, monthly_amount).
CONTRACTS = {
    "Advantage Medical Coverage": dict(product="Healthllm", number="HL-2025-0124", signed_on=("2025-04-18", "Contract Date"),
        term_months=(18, "18-month contract"), tier=("Professional", "Healthllm Professional Tier platform"),
        monthly_fee=(15000, "monthly payments of $15,000"), total_value=(270000, "totaling $270,000"),
        volumes=[("covered_members", 32000, "members", "currently covers 32,000 members"), ("states", 2, "states", "32,000 members in 2 states")],
        insurellm_signatory=("Sarah Chen", "VP of Sales", "Sarah Chen, VP of Sales"),
        customer_signatory=("Dr. Michael Ramirez", "Chief Medical Officer", "Dr. Michael Ramirez, Chief Medical Officer")),
    "Apex Reinsurance": dict(product="Rellm", signed_on=(PH, "on this [Date]"), term_months=(12, "twelve (12) months"),
        monthly_fee=(10000, "sum of $10,000 per month"), insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "Atlantic Risk Solutions": dict(product="Bizllm", effective_from=("2025-01-15", "effective as of January 15, 2025"),
        signed_on=("2025-01-15", "**Date**: January 15, 2025"), term_months=(12, "term of 12 months"), term_end=("2026-01-14", "concluding on January 14, 2026"),
        tier=("Professional", "**Professional Tier** of Bizllm"), monthly_fee=(12000, "$12,000/month"), total_value=(144000, "totaling $144,000"),
        user_licenses=(35, "35 named user licenses"), termination_notice_days=(45, "45 days' written notice"),
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "**Michael Torres**"),
        customer_signatory=("Diana Marquez", "Senior Vice President, Commercial Lines", "**Diana Marquez**")),
    "Belvedere Insurance": dict(product="Markellm", signed_on=(PH, "as of [Date]"), term_months=(12, "period of 1 year"),
        tier=("Basic Listing Fee", "Basic Listing Fee of $199/month"), monthly_fee=(199, "Basic Listing Fee of $199/month"),
        per_lead_fee=(25, "$25 per lead generated"), insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "BrightWay Solutions": dict(product="Markellm", number="INS-2023-0092", signed_on=("2023-10-05", "Contract Date"),
        term_months=(12, "duration of one year"), tier=("Basic Listing Fee", "Basic Listing Fee of $199 per month"),
        monthly_fee=(199, "Basic Listing Fee of $199 per month"), setup_fee=(1000, "initial setup fee of $1,000"),
        insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "ConnectInsure Agency": dict(product="Markellm", number="MK-2025-0056", signed_on=("2025-02-28", "Contract Date"),
        effective_from=("2025-03-01", "Services will commence on March 1, 2025"), term_months=(18, "18 months from the commencement date"),
        term_end=("2026-08-31", "ending August 31, 2026"), tier=("Basic Listing Fee", "Basic Listing Fee: $199/month"),
        monthly_fee=(199, "Basic Listing Fee: $199/month"), per_lead_fee=(25, "$25 per qualified lead"),
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "Michael Torres, Chief Revenue Officer"),
        customer_signatory=("Brian Foster", "Agency Principal", "Brian Foster, Agency Principal")),
    "Continental Commercial Group": dict(product="Bizllm", number="BZ-2025-E-0147", signed_on=("2025-04-12", "Contract Date"),
        legal_name=("Continental Commercial Group, Inc.", "- Continental Commercial Group, Inc."),
        term_months=(36, "period of 36 months"), tier=("Enterprise", "Bizllm Enterprise platform"),
        fee_schedule=[(1, 12, 42000, "$42,000 per month for the first 12 months")],
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Thomas Wellington", "President & Chief Operating Officer", "**Thomas Wellington**")),
    "DriveSmart Insurance": dict(product="Carllm", number="CR-2025-E-0078", signed_on=("2025-03-20", "Contract Date"),
        legal_name=("DriveSmart Insurance Corp.", "- DriveSmart Insurance Corp."), term_months=(36, "period of 36 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 18000, "$18,000 per month for the first 12 months"), (13, 24, 19500, "$19,500 per month for months 13-24"), (25, 36, 21000, "$21,000 per month for months 25-36")],
        total_value=(702000, "totaling $702,000"),
        volumes=[("active_policies", 85000, "policies", "85,000 active auto policies"), ("states", 8, "states", "policies across 8 states")],
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Steven Brooks", "President & Chief Operating Officer", "**Steven Brooks**")),
    "EverGuard Insurance": dict(product="Rellm", number="IG-2023-EG", effective_from=("2024-01-01", "Effective Date:** January 1, 2024"),
        term_end=("2026-12-31", "Expiration Date:** December 31, 2026"), tier=("Professional Plan", "Professional Plan features of Rellm"),
        monthly_fee=(10000, "monthly fee of $10,000"),
        insurellm_signatory=("John Smith", "Chief Operating Officer", "**Name**: John Smith"),
        customer_signatory=("Sarah Johnson", "Chief Executive Officer", "**Name**: Sarah Johnson")),
    "Evergreen Life Insurance": dict(product="Lifellm", number="LF-2025-0012", signed_on=("2025-01-20", "Contract Date"),
        legal_name=("Evergreen Life Insurance Company", "- Evergreen Life Insurance Company"), term_months=(12, "period of 12 months"),
        auto_renew=(True, "automatic renewal provisions"), renewal_notice_days=(30, "30-day written notice"),
        tier=("Starter", "Starter Tier package"), monthly_fee=(3500, "monthly fee of $3,500"),
        volumes=[("active_policies", 1400, "policies", "Current baseline: 1,400 policies")],
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "**Michael Torres**"),
        customer_signatory=("Catherine Wu", "Chief Underwriting Officer", "**Catherine Wu**")),
    "FastTrack Insurance Services": dict(product="Claimllm", number="CL-2025-0234", signed_on=("2025-05-10", "Contract Date"),
        term_months=(18, "18-month contract"), tier=("Advanced", "Claimllm Advanced Tier platform"),
        monthly_fee=(9500, "monthly payments of $9,500"), total_value=(171000, "totaling $171,000"),
        volumes=[("projected_claims_year_1", 22000, "claims", "FastTrack projects 22,000 claims in year 1")],
        insurellm_signatory=("Sarah Chen", "VP of Sales", "Sarah Chen, VP of Sales"),
        customer_signatory=("Rebecca Martinez", "COO", "Rebecca Martinez, COO")),
    "Fortress Business Underwriters": dict(product="Bizllm", effective_from=("2025-02-01", "effective as of February 1, 2025"),
        signed_on=("2025-02-01", "**Date**: February 1, 2025"), term_months=(24, "term of 24 months"), term_end=("2027-01-31", "concluding on January 31, 2027"),
        tier=("Professional", "**Professional Tier** of Bizllm"), monthly_fee=(12000, "$12,000/month"), total_value=(288000, "totaling $288,000"),
        user_licenses=(50, "up to 50 named users"), termination_notice_days=(60, "60 days' written notice"),
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "**Michael Torres**"),
        customer_signatory=("Robert Chen", "Chief Underwriting Officer", "**Robert Chen**")),
    "GlobalRe Partners": dict(product="Rellm", number="RE-2025-E-0203", signed_on=("2025-04-28", "Contract Date"),
        legal_name=("GlobalRe Partners International, Ltd.", "- GlobalRe Partners International, Ltd."), term_months=(48, "period of 48 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 45000, "$45,000 per month for months 1-12"), (13, 24, 48000, "$48,000 per month for months 13-24"),
                      (25, 36, 52000, "$52,000 per month for months 25-36"), (37, 48, 56000, "$56,000 per month for months 37-48")],
        total_value=(2412000, "$2,412,000"),
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Sir Charles Pemberton", "Group Chief Executive Officer", "**Sir Charles Pemberton**")),
    "GreenField Holdings": dict(product="Markellm", effective_from=("2023-11-15", "Effective Date:** November 15, 2023"),
        term_months=(12, "Contract Duration:** 12 months"), insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "GreenValley Insurance": dict(product="Homellm", number="HV-2023-0458", signed_on=("2023-10-06", "Contract Date"),
        legal_name=("GreenValley Insurance, LLC", "- GreenValley Insurance, LLC"), term_months=(12, "period of 12 months"),
        auto_renew=(True, "automatically renew"), renewal_notice_days=(30, "30-day notice"),
        tier=("Standard", "Standard Tier package"), monthly_fee=(10000, "monthly fee of $10,000"),
        insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "Greenstone Insurance": dict(product="Homellm", signed_on=(PH, "[Insert Date]"), term_months=(PH, "[Insert Duration"),
        tier=("Standard", "Standard Tier of the Homellm service"), monthly_fee=(10000, "$10,000 per month"),
        insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "Guardian Life Partners": dict(product="Lifellm", effective_from=("2025-03-01", "effective as of March 1, 2025"),
        signed_on=("2025-03-01", "**Date**: March 1, 2025"), term_months=(24, "term of 24 months"), term_end=("2027-02-28", "concluding on February 28, 2027"),
        tier=("Growth", "**Growth Tier** of Lifellm"), monthly_fee=(7500, "$7,500/month"), total_value=(180000, "totaling $180,000"),
        user_licenses=(25, "25 named user licenses"), termination_notice_days=(60, "60 days' written notice"),
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "**Michael Torres**"),
        customer_signatory=("Jonathan Park", "President & CEO", "**Jonathan Park**")),
    "Harmony Health Plans": dict(product="Healthllm", effective_from=("2025-01-25", "effective as of January 25, 2025"),
        signed_on=("2025-01-25", "**Date**: January 25, 2025"), term_months=(24, "term of 24 months"), term_end=("2027-01-24", "concluding on January 24, 2027"),
        tier=("Professional", "**Professional Tier** of Healthllm"), monthly_fee=(15000, "$15,000/month"), total_value=(360000, "totaling $360,000"),
        user_licenses=(60, "60 named user licenses"), termination_notice_days=(90, "90 days' written notice"),
        volumes=[("covered_members", 38000, "members", "currently covers 38,000 members"), ("states", 3, "states", "members across 3 states")],
        insurellm_signatory=("Sarah Chen", "Vice President of Sales", "**Sarah Chen**"),
        customer_signatory=("Dr. Karen Phillips", "President & Chief Executive Officer", "**Dr. Karen Phillips**")),
    "Heritage Life Assurance": dict(product="Lifellm", number="LF-2025-0045", signed_on=("2025-02-12", "Contract Date"),
        term_months=(18, "for 18 months"), term_end=("2026-08-11", "ending August 11, 2026"), tier=("Growth", "Lifellm Growth Tier"),
        monthly_fee=(7500, "$7,500 per month"), total_value=(135000, "Total contract value: $135,000"),
        volumes=[("active_policies", 6200, "policies", "currently administers 6,200 policies")],
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "Michael Torres, Chief Revenue Officer"),
        customer_signatory=("Melissa Zhang", "VP of Operations", "Melissa Zhang, VP of Operations")),
    "Metropolitan Life Group": dict(product="Lifellm", number="LF-2025-E-0087", signed_on=("2025-04-05", "Contract Date"),
        legal_name=("Metropolitan Life Group, Inc.", "- Metropolitan Life Group, Inc."), term_months=(36, "period of 36 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 28000, "$28,000 per month for months 1-12"), (13, 24, 30500, "$30,500 per month for months 13-24"), (25, 36, 33000, "$33,000 per month for months 25-36")],
        total_value=(1098000, "totaling $1,098,000"),
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Richard Thompson", "Chairman & Chief Executive Officer", "**Richard Thompson**")),
    "National Claims Network": dict(product="Claimllm", number="CL-2025-E-0198", signed_on=("2025-04-20", "Contract Date"),
        legal_name=("National Claims Network Corp.", "- National Claims Network Corp."), term_months=(36, "period of 36 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 35000, "$35,000 per month for months 1-12"), (13, 24, 38000, "$38,000 per month for months 13-24"), (25, 36, 41000, "$41,000 per month for months 25-36")],
        total_value=(1368000, "totaling $1,368,000"),
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Amanda Richardson", "President & Chief Operating Officer", "**Amanda Richardson**")),
    "Pinnacle Insurance Co.": dict(product="Homellm", effective_from=("2024-01-01", "1st day of January 2024"),
        term_months=(24, "two (2) years"), monthly_fee=(10000, "monthly subscription fee of $10,000"), setup_fee=(15000, "initial setup fee of $15,000"),
        insurellm_signatory=("Sarah Johnson", "VP of Sales", "Name: Sarah Johnson"),
        customer_signatory=("Tom Anderson", "Chief Operating Officer", "Name: Tom Anderson")),
    "Premier Adjusters Inc.": dict(product="Claimllm", effective_from=("2025-02-15", "effective as of February 15, 2025"),
        signed_on=("2025-02-15", "**Date**: February 15, 2025"), term_months=(24, "term of 24 months"), term_end=("2027-02-14", "concluding on February 14, 2027"),
        tier=("Advanced", "**Advanced Tier** of Claimllm"), monthly_fee=(9500, "$9,500/month"), total_value=(228000, "totaling $228,000"),
        volumes=[("baseline_claims_per_year", 18000, "claims", "18,000 claims/year")], termination_notice_days=(60, "60 days' written notice"),
        insurellm_signatory=("Sarah Chen", "Vice President of Sales", "**Sarah Chen**"),
        customer_signatory=("David Kowalski", "President & CEO", "**David Kowalski**")),
    "Rapid Claims Associates": dict(product="Claimllm", number="CL-2025-0063", signed_on=("2025-03-01", "Contract Date"),
        legal_name=("Rapid Claims Associates, LLC", "- Rapid Claims Associates, LLC"), term_months=(12, "period of 12 months"),
        auto_renew=(True, "automatic renewal provisions"), renewal_notice_days=(30, "30-day written notice"),
        tier=("Core", "Core Tier package"), monthly_fee=(4500, "monthly fee of $4,500"),
        insurellm_signatory=("Sarah Chen", "Vice President of Sales", "**Sarah Chen**"),
        customer_signatory=("Marcus Johnson", "Chief Claims Officer", "**Marcus Johnson**")),
    "Roadway Insurance Inc.": dict(product="Carllm", effective_from=("2025-01-01", "effective as of January 1, 2025"),
        term_months=(12, "term of 12 months"), term_end=("2025-12-31", "concluding on December 31, 2025"),
        tier=("Professional", "**Professional Tier** of Carllm"), monthly_fee=(2500, "$2,500/month"), total_value=(30000, "totaling $30,000"),
        termination_notice_days=(30, "30 days' written notice"), insurellm_signatory=(None, None, None), customer_signatory=(None, None, None)),
    "SafeHaven Property Insurance": dict(product="Homellm", number="HM-2025-E-0112", signed_on=("2025-05-03", "Contract Date"),
        legal_name=("SafeHaven Property Insurance, Inc.", "- SafeHaven Property Insurance, Inc."), term_months=(36, "period of 36 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 22000, "$22,000 per month for months 1-12"), (13, 24, 24000, "$24,000 per month for months 13-24"), (25, 36, 26000, "$26,000 per month for months 25-36")],
        total_value=(864000, "totaling $864,000"),
        volumes=[("active_policies", 45000, "policies", "45,000 active homeowners policies"), ("states", 6, "states", "policies across 6 states")],
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("Laura Mitchell", "President & Chief Executive Officer", "**Laura Mitchell**")),
    "Stellar Insurance Co.": dict(product="Rellm", effective_from=("2024-01-01", "**January 1, 2024**"), term_months=(12, "**12 months**"),
        auto_renew=(True, "automatically renew"), tier=("Professional Plan", "**Professional Plan**"), monthly_fee=(10000, "**$10,000**"),
        termination_notice_days=(30, "30-day written notice"), insurellm_signatory=(PH, None, None), customer_signatory=(PH, None, None)),
    "Summit Commercial Insurance": dict(product="Bizllm", number="BZ-2025-0091", signed_on=("2025-03-15", "Contract Date"),
        legal_name=("Summit Commercial Insurance, LLC", "- Summit Commercial Insurance, LLC"), term_months=(18, "period of 18 months"),
        auto_renew=(True, "automatically renew"), renewal_notice_days=(45, "45-day notice"),
        tier=("Business", "Business Tier package"), monthly_fee=(6000, "monthly fee of $6,000"),
        insurellm_signatory=("Michael Torres", "Chief Revenue Officer", "**Michael Torres**"),
        customer_signatory=("Patricia Lawson", "Vice President of Operations", "**Patricia Lawson**")),
    "TechDrive Insurance": dict(product="Carllm", signed_on=("2024-10-01", "Contract Date"), term_months=(12, "Contract Duration:** 12 months"),
        tier=("Professional", "Professional Tier at $2,500/month"), monthly_fee=(2500, "monthly payments of $2,500"),
        insurellm_signatory=("John Smith", "Account Manager", "Name: John Smith"),
        customer_signatory=("Sarah Johnson", "Operations Director", "Name: Sarah Johnson")),
    "United Healthcare Alliance": dict(product="Healthllm", number="HL-2025-E-0156", signed_on=("2025-05-15", "Contract Date"),
        legal_name=("United Healthcare Alliance, LLC", "- United Healthcare Alliance, LLC"), term_months=(48, "period of 48 months"),
        tier=("Enterprise", "custom Enterprise Tier pricing"),
        fee_schedule=[(1, 12, 52000, "$52,000 per month for months 1-12"), (13, 24, 56000, "$56,000 per month for months 13-24"),
                      (25, 36, 60000, "$60,000 per month for months 25-36"), (37, 48, 64000, "$64,000 per month for months 37-")],
        total_value=(2784000, "$2,784,000"),
        insurellm_signatory=("Jennifer Rodriguez", "Chief Executive Officer", "**Jennifer Rodriguez**"),
        customer_signatory=("James Patterson", "Chairman & Chief Executive Officer", "**James Patterson**")),
    "Velocity Auto Solutions": dict(product="Carllm", number="C-12345-2023", signed_on=("2023-10-01", "Contract Date"),
        term_months=(12, "period of 12 months"),
        insurellm_signatory=("Jane Smith", "VP of Sales", "Name: Jane Smith"),
        customer_signatory=("John Doe", "CEO", "Name: John Doe")),
    "WellCare Insurance Co.": dict(product="Healthllm", number="HL-2025-0021", signed_on=("2025-03-08", "Contract Date"),
        term_months=(12, "period of 12 months"), auto_renew=(True, "automatic renewal"), renewal_notice_days=(30, "30-day written notice"),
        tier=("Essential", "Essential Tier package"), monthly_fee=(8000, "monthly fee of $8,000"),
        volumes=[("covered_members", 11000, "members", "Current enrollment: 11,000 members")],
        insurellm_signatory=("Sarah Chen", "Vice President of Sales", "**Sarah Chen**"),
        customer_signatory=("Dr. Raymond Foster", "Chief Medical Officer & COO", "**Dr. Raymond Foster**")),
}

# Template names that appear as Insurellm signatories but are not people in the HR record.
TEMPLATE_NAMES = {"John Smith", "Jane Smith", "John Doe", "Sarah Johnson"}
# Real recurring Insurellm signatories. Not in the 32 HR files; see seed conflicts.
INSURELLM_SIGNERS = {"Sarah Chen", "Michael Torres", "Jennifer Rodriguez"}

KINDS = {"signed_on": "date", "effective_from": "date", "term_end": "date", "term_months": "months", "monthly_fee": "money",
         "total_value": "money", "setup_fee": "money", "per_lead_fee": "money", "user_licenses": "int",
         "termination_notice_days": "days", "renewal_notice_days": "days", "tier": "text", "legal_name": "text", "auto_renew": "derived"}


class LocatorError(ValueError):
    pass


def locate(text, locator, path):
    """The full source line that contains the locator (whitespace-insensitive)."""
    target = normalize(locator)
    for line in text.splitlines():
        if target in normalize(line):
            return line.strip()
    raise LocatorError(f"{path}: locator not found: {locator!r}")


def _f(text, path, value, locator, kind):
    quote = locate(text, locator, path)
    if value == PH:
        return {"value": None, "kind": "placeholder", "quote": quote, "reason": "template placeholder in the KB"}
    return fact(value, quote, kind)


def _signatory(text, path, spec):
    name, title, locator = spec
    if name is None:
        return unknown("no signature block in the KB")
    if name == PH:
        return {"value": None, "kind": "placeholder", "reason": "signature block is an unfilled template"}
    quote = locate(text, locator, path)
    title_quote = locate(text, title, path)
    return {"name": fact(name, quote), "title": fact(title, title_quote),
            "is_template_name": name in TEMPLATE_NAMES}


def extract_contracts(kb):
    by_customer = {}
    for path, f in kb.items():
        if f.category == "contracts":
            customer = f.stem.removeprefix("Contract with ").rsplit(" for ", 1)[0]
            by_customer[customer] = (path, f)
    missing = set(CONTRACTS) ^ set(by_customer)
    if missing:
        raise LocatorError(f"contract table and KB files disagree on: {sorted(missing)}")

    contracts = []
    for customer, spec in sorted(CONTRACTS.items()):
        path, f = by_customer[customer]
        product_line = next(l for l in f.text.splitlines() if l.startswith("# "))
        rec = {"kb_file": path, "customer_display_name": fact(customer, product_line),
               "product": fact(spec["product"], product_line)}
        rec["contract_number"] = _f(f.text, path, spec["number"], spec["number"], "text") if spec.get("number") else unknown("no contract number in the KB")
        for key, kind in KINDS.items():
            if key in spec:
                value, locator = spec[key]
                rec[key] = _f(f.text, path, value, locator, kind)
            else:
                rec[key] = unknown("not stated in the KB")
        rec["fee_schedule"] = [{"from_month": a, "to_month": b, "monthly_fee": _f(f.text, path, amount, loc, "money")}
                               for a, b, amount, loc in spec.get("fee_schedule", [])]
        rec["volumes"] = [{"metric": m, "unit": u, "value": _f(f.text, path, v, loc, "int")} for m, v, u, loc in spec.get("volumes", [])]
        rec["insurellm_signatory"] = _signatory(f.text, path, spec["insurellm_signatory"])
        rec["customer_signatory"] = _signatory(f.text, path, spec["customer_signatory"])
        rec["sections"] = [h for h, _ in f.sections() if h]
        contracts.append(rec)
    return contracts

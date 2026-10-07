"""Extract the 32 original employees from knowledge-base/employees/*.md.

Only facts the KB states are extracted, each with its verbatim quote. Org placement
(department, team, level, manager) is NOT in the KB; it comes from the explicit
ORG table below, which is marked as a seeding decision, not a KB fact.
"""

import re

from .kb import MONTH_RE, MONTHS, fact, money_value, parse_long_date, unknown
from .seed_contracts import locate

SUMMARY_FIELDS = {
    "date_of_birth": r"Date of Birth",
    "job_title": r"Job Title",
    "location": r"Location",
    "current_salary": r"Current Salary",
}

# Seeding decision (not a KB fact): where each original employee sits in the org.
# department code, team key (None = no team), job level. Teams are defined in datagen/world_config.py.
ORG = {
    'Avery Lancaster': ('executive', 'office-of-ceo', 'E1'),
    'James Wilson': ('engineering', None, 'E2'),
    'Robert Chen': ('engineering', 'personal-lines-platform', 'IC5'),
    'Alex Chen': ('engineering', 'personal-lines-platform', 'IC4'),
    'Tyler Brooks': ('engineering', 'personal-lines-platform', 'IC1'),
    'Oliver Spencer': ('engineering', 'commercial-platform', 'IC5'),
    'Jessica Liu': ('engineering', 'commercial-platform', 'IC3'),
    'Jordan K. Bishop': ('engineering', 'commercial-platform', 'IC3'),
    'Kevin Zhang': ('engineering', 'commercial-platform', 'IC4'),
    'David Kim': ('engineering', 'infrastructure-quality', 'IC4'),
    'Daniel Park': ('engineering', 'infrastructure-quality', 'IC3'),
    'Priya Sharma': ('engineering', 'data-ai', 'M2'),
    'Maxine Thompson': ('engineering', 'data-ai', 'IC4'),
    'Maya Thompson': ('engineering', 'data-ai', 'IC3'),
    'Samuel Trenton': ('engineering', 'data-ai', 'IC5'),
    'Nina Patel': ('engineering', 'data-ai', 'IC3'),
    'Rachel Martinez': ('product', 'product-management', 'M2'),
    'Michelle Rivera': ('product', 'design', 'M1'),
    'Sarah Williams': ('product', 'design', 'IC3'),
    "Michael O'Brien": ('sales', 'account-executives', 'M1'),
    'Emily Carter': ('sales', 'account-executives', 'IC3'),
    'Carlos Rodriguez': ('sales', 'account-executives', 'IC4'),
    'Alex Thomson': ('sales', 'sales-development', 'M1'),
    'Alex Harper': ('sales', 'sales-development', 'IC2'),
    'Jennifer Adams': ('sales', 'sales-development', 'IC1'),
    'Jordan Blake': ('sales', 'sales-development', 'IC2'),
    'Lisa Anderson': ('marketing', 'marketing', 'M2'),
    'Emily Tran': ('marketing', 'marketing', 'IC2'),
    'Amanda Foster': ('hr', 'people', 'M2'),
    'Samantha Greene': ('hr', 'people', 'IC2'),
    'Marcus Johnson': ('customer-success', 'customer-success', 'M1'),
    'Brandon Walker': ('customer-success', 'customer-success', 'IC2'),
}


# Dated awards. (award_code is a short machine key = seeding decision; name and year are KB facts.)
RECOGNITIONS = {
    "Maxine Thompson": [("IIOTY", "IIOTY Innovator Award", 2023, "prestigious Insurellm IIOTY Innovator Award in 2023")],
    "Alex Harper": [("SDROY", "SDR of the Year", 2022, 'Insurellm "SDR of the Year" Award (2022)')],
    "Carlos Rodriguez": [("SEOY", "Solutions Engineer of the Year", 2023, "Solutions Engineer of the Year 2023")],
    "Amanda Foster": [("HREXC", "HR Excellence Award", 2023, "HR Excellence Award 2023")],
    "Daniel Park": [("QCHAMP", "Quality Champion Award", 2023, "Quality Champion Award 2023")],
    "Kevin Zhang": [("MOBINNOV", "Mobile Innovation Award", 2023, "Mobile Innovation Award 2023")],
    "Marcus Johnson": [("CUSTCHMP", "Customer Champion Award", 2023, "Customer Champion Award 2023")],
    "Michelle Rivera": [("DESIGNEX", "Design Excellence Award", 2023, "Design Excellence Award 2023")],
    "Lisa Anderson": [("MKTGEX", "Marketing Excellence Award", 2023, "Marketing Excellence Award 2023")],
    "Michael O'Brien": [("SALESEX", "Sales Excellence Award", 2021, "Sales Excellence Award 2021")],
    "Priya Sharma": [("DSEX", "Data Science Excellence Award", 2023, "Data Science Excellence Award 2023")],
    "Robert Chen": [("ENGEX", "Engineering Excellence Award", 2023, "Engineering Excellence Award 2023"),
                    ("TECHLEAD", "Technical Leadership Award", 2021, "Technical Leadership Award 2021")],
    "Jordan K. Bishop": [("INNOV", "Innovation Award", 2021, "**2021:** Exceeds Expectations - Recognized for leadership")],
}

RATING_LABELS = [
    "Outstanding", "Exceptional", "Exceeds Expectations", "Meets Expectations", "Satisfactory",
    "Developing", "Needs Improvement", "Below Expectations", "Unsatisfactory",
]


def _summary_field(section, label):
    m = re.search(rf"^.*\*\*{label}:?\*\*:?\s*(.+?)\s*$", section, re.M)
    return (m.group(1).strip(), m.group(0)) if m else (None, None)


def _location(raw, quote):
    m = re.match(r"Remote \(Based in (.+?)\)", raw)
    if m:
        return {"arrangement": fact("remote", quote), "city": fact(m.group(1), quote)}
    return {"arrangement": fact("office", quote, "derived"), "city": fact(raw, quote)}


def _start_of(token):
    """'January 2017' -> ('2017-01', 'month'); '2015' -> ('2015', 'year')."""
    m = re.match(rf"({MONTH_RE})\s+(\d{{4}})", token)
    if m:
        return f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}", "month"
    m = re.match(r"(\d{4})", token)
    return (m.group(1), "year") if m else (None, None)


def _hire(career):
    """Earliest start among Insurellm roles. External roles say 'at <Company>'."""
    best = None
    for line in career.splitlines():
        m = re.match(r"^\s*-\s*\*\*(.+?)\*\*\s*:?\s*[-:]?\s*(.*)$", line)
        if not m:
            continue
        when, rest = m.group(1).rstrip(":").strip(), m.group(2)
        if re.search(r"\bat\s+(?!Insurellm)[A-Z]", rest) and "Joined Insurellm" not in rest:
            continue
        start, precision = _start_of(when)
        if start and (best is None or start < best[0]):
            best = (start, precision, line.strip())
    if not best:
        return unknown("no dated Insurellm role in career progression")
    start, precision, quote = best
    return fact(start, quote, precision)


ITEM_RE = re.compile(rf"^\s*(?:-\s*\*\*\s*((?:{MONTH_RE})\s+\d{{4}}|\d{{4}}(?:-\d{{2}})?)|\|\s*(\d{{4}})\s*\|)")


def _blocks(section):
    """Group a section into dated items: a bullet or table row that starts with a date,
    plus the indented lines that follow it. Returns [(period, quote_text)]."""
    blocks, current = [], None
    for line in section.splitlines():
        m = ITEM_RE.match(line)
        if m and not line.strip().startswith("|--"):
            if current:
                blocks.append(current)
            token = m.group(1) or m.group(2)
            current = [token, [line.strip()]]
        elif current and line.startswith((" ", "\t")) and line.strip():
            current[1].append(line.strip())
        elif current and not line.strip():
            continue
        elif current:
            blocks.append(current)
            current = None
    if current:
        blocks.append(current)
    return [(token, "\n".join(lines)) for token, lines in blocks]


def _period(token):
    """'2021' -> ('2021','year'); 'June 2018' / '2021-06' -> ('2018-06','month')."""
    m = re.match(rf"({MONTH_RE})\s+(\d{{4}})", token)
    if m:
        return f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}", "month"
    if re.match(r"\d{4}-\d{2}$", token):
        return token, "period_token"
    return token, "year"


AMOUNT = r"\$\s?[\d,]+(?:\.\d+)?"
BASE_PATTERNS = [
    rf"^\s*-\s*\*\*[^*]+\*\*:?\s*({AMOUNT})(?!\s*/hour)",                 # '- **2015**: $150,000 base salary'
    rf"Base Salary\**\s*[-:]?\**\s*(?:Increase to\s*)?({AMOUNT})",
    rf"Starting Salary\s*[-:]?\s*({AMOUNT})",
    rf"Salary (?:Increase|increased to|raised to|Adjustment|adjustment)[^$\n]{{0,40}}({AMOUNT})",
    rf"(?:Initial|Revised) salary of ({AMOUNT})", rf"Merit-based increase:\s*({AMOUNT})",
]
BONUS_PATTERNS = [
    rf"Bonus\**\s*[-:]?\**\s*({AMOUNT})", rf"bonus (?:of|awarded:?)\s*({AMOUNT})",
    rf"({AMOUNT})\s+(?:performance\s+|annual\s+|retention\s+)?bonus",
]


def _first(patterns, text, flags=re.I | re.M):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return money_value(m.group(1))
    return None


def _compensation(section):
    table_has_bonus = bool(re.search(r"\|\s*Year\s*\|.*Bonus", section, re.I))
    out = []
    for token, block in _blocks(section):
        period, precision = _period(token)
        if block.startswith("|"):
            cells = [c.strip() for c in block.strip("|").split("|")]
            base = money_value(cells[1]) if len(cells) > 1 else None
            bonus = money_value(cells[2]) if table_has_bonus and len(cells) > 2 else None
        else:
            base = _first(BASE_PATTERNS, block)
            bonus = _first(BONUS_PATTERNS, block)
        if base is None and bonus is None:
            continue   # e.g. hourly intern stipend or a freeze with no amount
        row = {"period": fact(period, block, "year" if precision == "year" else "derived"), "period_precision": precision}
        row["base_salary"] = fact(base, block, "money") if base is not None else unknown("no base salary in this entry")
        row["bonus"] = fact(bonus, block, "money") if bonus is not None else unknown("no bonus amount in this entry")
        out.append(row)
    return out


def _ratings(section):
    out = []
    for token, block in _blocks(section):
        period, _ = _period(token)
        first_line = block.splitlines()[0]
        score = re.search(r"(\d(?:\.\d)?)\s*/\s*5", block)
        explicit = re.search(r"Performance Rating\**:?\**\s*(" + "|".join(RATING_LABELS) + ")", block)
        label = explicit.group(1) if explicit else next((l for l in RATING_LABELS if l in first_line), None)
        if score:
            rating = fact(float(score.group(1)), block, "score")
        elif label:
            rating = fact(label, block)
        else:
            rating = unknown("year listed without a rating")
        out.append({"year": fact(int(period[:4]), block, "year"), "rating": rating})
    return out


def extract_employees(kb):
    employees = []
    for path, f in kb.items():
        if f.category != "employees":
            continue
        name = f.stem
        summary = f.section("Summary")
        record = {"kb_file": path, "full_name": fact(name, f.text.split("\n")[0] if name in f.text.split("\n")[0] else name)}
        # full_name quote: the H1 that carries the name
        h1 = next((l for l in f.text.splitlines() if l.startswith("# ") and name.split()[-1] in l), None)
        record["full_name"] = fact(name, h1) if h1 else unknown("no heading with the name")
        for key, label in SUMMARY_FIELDS.items():
            raw, line = _summary_field(summary, label)
            if raw is None:
                record[key] = unknown(f"no '{label}' line in Summary")
            elif key == "date_of_birth":
                record[key] = fact(parse_long_date(raw), line, "date")
            elif key == "current_salary":
                record[key] = fact(money_value(raw), line, "money")
            elif key == "location":
                record[key] = _location(raw, line)
            else:
                record[key] = fact(raw, line)
        record["hire"] = _hire(f.section("Insurellm Career Progression"))
        record["compensation_history"] = _compensation(f.section("Compensation History"))
        record["performance_history"] = _ratings(f.section("Annual Performance History"))
        record["recognitions"] = [
            {"award_code": code, "award_name": fact(award, locate(f.text, loc, path)), "year": fact(year, locate(f.text, loc, path), "year")}
            for code, award, year, loc in RECOGNITIONS.get(name, [])]
        dept, team, level = ORG[name]
        record["org"] = {"department_code": dept, "team_key": team, "job_level": level,
                         "origin": "seeding_decision"}
        record["sections"] = [h for h, _ in f.sections() if h]
        employees.append(record)
    return employees

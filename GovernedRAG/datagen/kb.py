"""Read the original Insurellm knowledge base and record where every fact came from.

A Fact is a value plus the exact quote it was read from. Seeding never stores a
KB-derived value without its quote, so tools can prove the value was not invented
or changed: the quote must appear verbatim in the KB file, and the value must
appear inside the quote.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_ROOT = PROJECT_ROOT.parent / "Week5_RAG" / "knowledge-base"
TESTS_FILE = PROJECT_ROOT.parent / "Week5_RAG" / "evaluation" / "tests.jsonl"
SOURCE_ROOT = PROJECT_ROOT / "data" / "source"
SEED_DIR = SOURCE_ROOT / "seed"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_RE = "|".join(MONTHS)


def normalize(text):
    """Collapse whitespace and unify quote marks, for quote matching only."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class KBFile:
    path: str          # relative to KB_ROOT, e.g. "employees/Alex Chen.md"
    text: str

    @property
    def category(self):
        return self.path.split("/")[0]

    @property
    def stem(self):
        return Path(self.path).stem

    def sections(self):
        """Split on '## ' headings. Returns [(heading, body)] with the preamble as heading ''."""
        parts, heading, buf = [], "", []
        for line in self.text.splitlines(keepends=True):
            m = re.match(r"^##\s+(.+?)\s*$", line)
            if m and not line.startswith("###"):
                parts.append((heading, "".join(buf)))
                heading, buf = m.group(1), [line]
            else:
                buf.append(line)
        parts.append((heading, "".join(buf)))
        return parts

    def section(self, name):
        for heading, body in self.sections():
            if heading.lower().startswith(name.lower()):
                return body
        return ""


def load_kb():
    files = {}
    for p in sorted(KB_ROOT.rglob("*.md")):
        rel = p.relative_to(KB_ROOT).as_posix()
        files[rel] = KBFile(rel, p.read_text(encoding="utf-8"))
    return files


def fact(value, quote, kind="text"):
    """A KB-derived value and the verbatim text it came from."""
    return {"value": value, "kind": kind, "quote": quote.strip()}


def unknown(reason):
    """A value the KB does not state. Never filled with an invented value during seeding."""
    return {"value": None, "kind": "unknown", "reason": reason}


def money_value(text):
    m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    number = float(m.group(1).replace(",", ""))
    return int(number) if number.is_integer() else number


def money_forms(value):
    if isinstance(value, float) and not value.is_integer():
        return [f"${value:,.2f}", f"{value:,.2f}"]
    v = int(value)
    forms = [f"${v:,}", f"{v:,}", f"${v}"]
    if v >= 1000 and v % 1000 == 0:
        forms.append(f"${v // 1000}K")
    if v >= 1_000_000 and v % 100_000 == 0:
        forms.append(f"${v / 1_000_000:g}M")
    return forms


def parse_long_date(text):
    """'March 15, 1990' -> '1990-03-15'."""
    m = re.search(rf"({MONTH_RE})\s+(\d{{1,2}}),?\s+(\d{{4}})", text)
    if not m:
        return None
    return date(int(m.group(3)), MONTHS.index(m.group(1)) + 1, int(m.group(2))).isoformat()


def date_forms(iso):
    d = date.fromisoformat(iso)
    month = MONTHS[d.month - 1]
    return [f"{month} {d.day}, {d.year}", f"{month} {d.day} {d.year}", f"{d.day}{_suffix(d.day)} day of {month} {d.year}"]


def _suffix(day):
    return "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def value_forms(f):
    """Every textual form the value may take inside its quote."""
    value, kind = f["value"], f["kind"]
    if kind == "money":
        return money_forms(value)
    if kind == "date":
        return date_forms(value)
    if kind == "month":           # 'YYYY-MM'
        y, m = value.split("-")
        return [f"{MONTHS[int(m) - 1]} {y}"]
    if kind in ("year", "int", "months", "days"):
        forms = [str(value), f"{value:,}" if isinstance(value, int) else str(value)]
        words = {1: "one", 2: "two", 3: "three", 6: "six", 12: "twelve", 18: "eighteen", 24: "twenty-four", 36: "thirty-six", 48: "forty-eight"}
        if value in words:
            forms.append(words[value])
        if kind == "months" and value % 12 == 0:           # '1 year', 'one year', 'two (2) years'
            years = value // 12
            forms += [f"{years} year", f"{words.get(years, years)} year", f"{words.get(years, years)} ({years}) year"]
        return forms
    if kind == "score":
        forms = [f"{value}/5", f"{value:.1f}/5"]
        if float(value).is_integer():
            forms.append(f"{int(value)}/5")
        return forms
    if kind == "derived":
        return []                 # documented derivation; checked by its own rule
    return [str(value)]

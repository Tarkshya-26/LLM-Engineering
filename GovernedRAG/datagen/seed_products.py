"""Extract the 8 original products: pricing tiers and roadmap items, each with its quote."""

import re

from .kb import fact, money_value, unknown

TIER_LINE = re.compile(r"^\s*-\s*\*\*(?P<name>[^*]+?):?\*\*:?\s*(?P<rest>.*)$")
TIER_WORDS = ("Tier", "Plan", "Fee", "Membership", "Features", "Pricing")


def _tiers(pricing):
    tiers, audience = [], None
    for line in pricing.splitlines():
        h = re.match(r"^###\s+For\s+(Consumers|Insurance Companies)", line)
        if h:
            audience = "consumers" if h.group(1) == "Consumers" else "insurers"
            continue
        m = TIER_LINE.match(line)
        if not m or not any(w in m.group("name") for w in TIER_WORDS):
            continue
        name, rest = m.group("name").strip().rstrip(":"), m.group("rest")
        tier = {"tier_name": fact(name, line), "audience": audience or "insurers"}
        if re.search(r"custom pricing", rest, re.I):
            tier["pricing_model"] = fact("custom", line, "derived")
            tier["price"] = unknown("custom pricing, no list price")
            tier["price_unit"] = "per_month"
        elif re.search(r"no cost", rest, re.I):
            tier["pricing_model"] = fact("free", line, "derived")
            tier["price"] = fact(0, line, "derived")
            tier["price_unit"] = "per_month"
        else:
            price = money_value(rest)
            tier["pricing_model"] = fact("starting_at" if re.search(r"starting at", rest, re.I) else "fixed", line, "derived")
            tier["price"] = fact(price, line, "money") if price is not None else unknown("no amount on the tier line")
            tier["price_unit"] = "per_lead" if re.search(r"per lead", rest) else "per_month"
        tiers.append(tier)
    return tiers


def _quarter(token):
    m = re.search(r"Q([1-4])\s+(\d{4})", token)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    m = re.search(r"\b(20\d{2})\b", token)
    return m.group(1) if m else None


def _clean(text):
    return re.sub(r"\*\*", "", text).strip().rstrip(".")


def _roadmap(section):
    items, period = [], None
    for line in section.splitlines():
        heading = re.match(r"^###\s+(.+)$", line)
        lead = re.match(r"^-\s*\*\*(Q[1-4]\s+\d{4}|\d{4})\*?\*?:?\*?\*?:?\s*(.*)$", line)
        if heading:
            period = _quarter(heading.group(1))
            continue
        if lead:
            period = _quarter(lead.group(1))
            rest = lead.group(2).strip()
            if rest:
                items.append({"target_period": fact(period, line, "derived"), "feature": fact(_clean(rest), line, "derived")})
            continue
        bullet = re.match(r"^\s*-\s+(.+)$", line)
        if bullet and period:
            items.append({"target_period": fact(period, line, "derived"), "feature": fact(_clean(bullet.group(1)), line, "derived")})
    return items


def extract_products(kb):
    products = []
    for path, f in kb.items():
        if f.category != "products":
            continue
        name = f.stem
        h1 = next(l for l in f.text.splitlines() if l.startswith("# ") and name in l)
        roadmap = next((body for heading, body in f.sections() if "Roadmap" in heading), "")
        products.append({
            "kb_file": path,
            "name": fact(name, h1),
            "tiers": _tiers(f.section("Pricing")),
            "roadmap": _roadmap(roadmap),
            "sections": [h for h, _ in f.sections() if h],
        })
    return products

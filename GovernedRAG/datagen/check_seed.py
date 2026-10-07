"""Prove the seed did not invent or change any knowledge-base fact.

    python -m datagen.check_seed       (from the GovernedRAG root)

1. Provenance: every seeded fact's quote appears verbatim (whitespace-insensitive)
   in its KB file, and the value appears inside the quote.
2. Completeness: every KB file is seeded exactly once (32 employees, 8 products,
   32 contracts, 4 company pages).
3. Test coverage: for each of the 150 original tests, every keyword that exists in
   the KB lives in a seeded file, so the seeded documents still contain it.
"""

import json
import re
import sys
from collections import Counter

from .kb import SEED_DIR, TESTS_FILE, load_kb, normalize, value_forms


def walk(node, path=""):
    """Yield (path, fact) for every fact dict in the seed."""
    if isinstance(node, dict):
        if "kind" in node and ("value" in node or "reason" in node):
            yield path, node
            return
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}[{i}]")


def file_of(seed, path):
    top, rest = path.split(".", 1) if "." in path else (path, "")
    m = re.match(r"(\w+)\[(\d+)\]", top)
    if m:
        return seed[m.group(1)][int(m.group(2))].get("kb_file")
    return None


def main():
    kb = load_kb()
    norm = {p: normalize(f.text) for p, f in kb.items()}
    seed = json.loads((SEED_DIR / "kb_seed.json").read_text(encoding="utf-8"))
    failures, kinds = [], Counter()

    for path, f in walk(seed):
        kinds[f["kind"]] += 1
        if "quote" not in f:
            continue
        kb_file = file_of(seed, path)
        candidates = [kb_file] if kb_file else list(kb)          # company/location facts: any company page
        quote = normalize(f["quote"])
        if not any(quote in norm[c] for c in candidates if c):
            failures.append(f"{path}: quote not found verbatim in {kb_file or 'company pages'}: {f['quote'][:80]!r}")
            continue
        if f["value"] is None or f["kind"] in ("derived", "placeholder", "unknown"):
            continue
        forms = value_forms(f)
        if forms and not any(normalize(form).lower() in quote.lower() for form in forms):
            failures.append(f"{path}: value {f['value']!r} ({f['kind']}) not in its quote: {f['quote'][:90]!r}")

    for e in seed["employees"]:
        section = kb[e["kb_file"]].section("Compensation History")
        if "$" in section and not any(c["base_salary"].get("value") for c in e["compensation_history"]):
            failures.append(f"{e['kb_file']}: Compensation History has dollar amounts but no base salary was extracted")
        if not any(c["base_salary"].get("value") == e["current_salary"]["value"] for c in e["compensation_history"]):
            failures.append(f"{e['kb_file']}: current salary {e['current_salary']['value']} missing from extracted pay history")

    seeded_files = Counter([e["kb_file"] for e in seed["employees"]] + [p["kb_file"] for p in seed["products"]]
                           + [c["kb_file"] for c in seed["contracts"]] + seed["company"]["kb_files"])
    for p in kb:
        if seeded_files[p] != 1:
            failures.append(f"{p}: seeded {seeded_files[p]} times (expected exactly once)")

    tests = [json.loads(l) for l in TESTS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    kb_lower = {p: f.text.lower() for p, f in kb.items()}
    absent, covered = [], 0
    for t in tests:
        for kw in t["keywords"]:
            hits = [p for p, text in kb_lower.items() if kw.lower() in text]
            if not hits:
                absent.append((t["category"], kw, t["question"][:60]))
            elif all(seeded_files[h] == 1 for h in hits):
                covered += 1
            else:
                failures.append(f"keyword {kw!r} found only in unseeded files {hits}")

    print(f"facts checked: {sum(kinds.values())}  " + "  ".join(f"{k}={n}" for k, n in sorted(kinds.items())))
    print(f"KB files seeded exactly once: {sum(1 for p in kb if seeded_files[p] == 1)}/{len(kb)}")
    print(f"test keywords present in seeded files: {covered}; absent from the original KB itself: {len(absent)}")
    for category, kw, q in absent:
        print(f"   (KB never contained) [{category}] {kw!r} in: {q}")
    for msg in failures:
        print("FAIL", msg)
    print(f"\n{len(failures)} failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

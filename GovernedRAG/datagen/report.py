"""Counts for the pre-document checkpoint, read from the written files.

    python -m datagen.report           (from the GovernedRAG root)
"""

import json
from collections import Counter, defaultdict

from .check_world import ENTITY_FILES, load, replay


def main():
    d = load()
    snaps, deleted, stats = replay(d)
    t0, final = snaps["CP-T0"], snaps["CP-B04"]
    print("T0 ENTITIES (origin kb_seed / generated)")
    for fname, otype in ENTITY_FILES.items():
        c = Counter(r["origin"] for r in t0[otype].values())
        fc = Counter(r["origin"] for r in final[otype].values())
        print(f"  {fname:20} T0 {len(t0[otype]):4}  (seed {c['kb_seed']:3}, generated {c['generated']:3})   after BATCH-04 {len(final[otype]):4}  (generated {fc['generated']})")
    print("\nACCESS CONTROL")
    for cp in ("CP-T0", "CP-B04"):
        st = snaps[cp]
        pt = Counter((p["principal_type"], p["principal_status"]) for p in st["principal"].values())
        print(f"  {cp}: tenants {len(st['tenant'])} ({Counter(t['tenant_status'] for t in st['tenant'].values())}), groups {len(st['group'])}, "
              f"principals {dict(pt)}, memberships {len(st['membership'])} (open {sum(1 for m in st['membership'].values() if m['valid_to'] is None)})")
    empty = [g for g in t0["group"] if not any(m["group_id"] == g for m in t0["membership"].values())]
    print(f"  groups with no members at T0: {empty}")
    print("\nRELATIONSHIPS")
    e = d["edges"]
    print(f"  edges {len(e)} (open at end {sum(1 for x in e if x['valid_to'] is None)}, closed {sum(1 for x in e if x['valid_to'])}), "
          f"by batch {dict(Counter(x['introduced_in_batch'] for x in e))}")
    print(f"  top relations: {Counter(x['relation'] for x in e).most_common(8)}")
    print("\nCDC")
    ev = d["events"]
    print(f"  delivered {len(ev)} (distinct {len({x['event_id'] for x in ev})}); replay {dict(stats)}")
    for b in d["manifest"]["batches"][1:]:
        rows = [x for x in ev if x["batch_id"] == b["batch_id"]]
        print(f"  {b['batch_id']} {b['label'][:58]:58} {len(rows):3} events  {dict(Counter((x['operation'], x['object_type']) for x in rows).most_common(6))}")
    print("\nDOCUMENT PLAN (bodies not written)")
    plan = d["plan"]
    print(f"  versions {len(plan)}  by mode {dict(Counter(p['body']['mode'] for p in plan))}")
    print(f"  by batch {dict(Counter(p['batch_id'] for p in plan))}")
    print(f"  by label {dict(Counter(p['front_matter']['sensitivity_label'] for p in plan))}")
    print(f"  by system {dict(Counter(p['front_matter']['source_system'] for p in plan))}")
    for c in d["gt"]["checkpoints"]:
        print(f"  {c['checkpoint_id']}: {c['expected_counts']}")
    print("\nGROUND TRUTH")
    am = d["gt"]["access_matrix"]
    print(f"  personas {len(d['gt']['personas'])}, access decisions {len(am)} {dict(Counter(r['decision'] for r in am))}")
    print(f"  per checkpoint {dict(Counter(r['checkpoint_id'] for r in am))}")
    print(f"  reasons {dict(Counter(r['reason_code'] for r in am).most_common())}")
    vf = d["gt"]["versioned_facts"]
    print(f"  versioned facts {len(vf)} by attribute {dict(Counter(f['attribute'] for f in vf).most_common(8))}")
    print(f"     with a successor (temporal) {sum(1 for f in vf if f['superseded_by_fact_id'])}, min label {dict(Counter(f['min_label_to_know'] for f in vf))}")
    print(f"  annotations {dict(Counter(a['annotation_type'] for a in d['gt']['document_annotations']))}")
    print("\nSCENARIO SPOT CHECKS")
    idx = {(r["checkpoint_id"], r["persona_id"], r["document_version_id"]): r for r in am}
    reviews = next(p["front_matter"]["document_version_id"] for p in plan if p["front_matter"]["title"] == "Performance reviews: Maxine Thompson")
    for persona, who in [("PERS-07", "Priya (manager)"), ("PERS-08", "James (skip-level)"), ("PERS-02", "Avery (3 levels up)"), ("PERS-05", "Amanda (HR)"), ("PERS-06", "Maxine (self)")]:
        r = idx[("CP-T0", persona, reviews)]
        print(f"  Maxine's reviews at T0, {who:22} {r['decision']:5} {r['reason_code']}" + (f"  via {r['matched_grant']['value']}" if r["matched_grant"] else ""))
    fast = [r for r in am if r["checkpoint_id"] == "CP-T0" and r["persona_id"] == "PERS-10"]
    print(f"  FastTrack portal user at T0: {dict(Counter(r['reason_code'] for r in fast))}")
    hist = [r for r in am if r["reason_code"] == "deny_history_exceeds_current"]
    print(f"  history rule denials: {len(hist)} e.g. {hist[0]['persona_id']} {hist[0]['document_version_id']} at {hist[0]['checkpoint_id']}" if hist else "  history rule: none")
    emily_docs = [p["front_matter"]["document_version_id"] for p in plan if p["front_matter"]["document_type"] == "contract" and
                  any(r.get("relation") == "account_team_of" for r in p["front_matter"]["access_relations"])]
    for cp in ("CP-B02", "CP-B03"):
        how = Counter(idx[(cp, "PERS-03", dv)]["matched_grant"]["grant_type"] if idx[(cp, "PERS-03", dv)]["matched_grant"] else idx[(cp, "PERS-03", dv)]["reason_code"]
                      for dv in emily_docs if (cp, "PERS-03", dv) in idx)
        print(f"  Emily Carter on the original contracts at {cp}: {dict(how)}")
    sig = [p for p in final["principal"].values() if p["display_name"] in ("Jennifer Rodriguez", "Sarah Chen", "Michael Torres")]
    print(f"  contract signatories with an identity: {len(sig)}; CEO: {[e['first_name'] + ' ' + e['last_name'] for e in final['employee'].values() if e['manager_id'] is None]}")
    t0_heads = sum(1 for x in t0["employee"].values() if x["employment_type"] != "contractor")
    print(f"  employees at T0: {t0_heads}; after BATCH-01: {sum(1 for x in snaps['CP-B01']['employee'].values() if x['employment_type'] != 'contractor')} (+1 contractor)")


if __name__ == "__main__":
    main()

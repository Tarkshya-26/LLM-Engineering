"""In-memory source-of-truth store that records every post-T0 change as a CDC event.

Rows put with t0() form the snapshot. insert/update/delete after T0 append CDC
events (commit order = `sequence`) and keep two derived structures in step:
relationship edges (from foreign keys) and nothing else. Group memberships are
ordinary rows maintained by the builder through insert/update.
"""

import copy
import json
from datetime import date, datetime, timedelta
from pathlib import Path

PK = {
    "location": "location_id", "department": "department_id", "team": "team_id", "employee": "employee_id",
    "compensation": "compensation_id", "performance_review": "review_id", "product": "product_id", "product_tier": "tier_id",
    "customer": "customer_id", "contract": "contract_id", "contract_version": "contract_version_id", "project": "project_id",
    "policy": "policy_id", "policy_version": "policy_version_id", "incident": "incident_id", "support_ticket": "ticket_id",
    "financial_record": "financial_id", "tenant": "tenant_id", "principal": "principal_id", "group": "group_id",
    "membership": "membership_id", "policy_set": "policy_set_id",
}
ENTITY_TYPES = [t for t in PK if t not in ("tenant", "principal", "group", "membership", "policy_set")]
EVENT_SOURCE = {"tenant": "support", "principal": "hris", "group": "hris", "membership": "hris", "policy_set": "grc"}


def plus_seconds(ts, n):
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=n)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def day(ts):
    return ts[:10]


def day_before(d):
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


def edge_catalog(schema_dir):
    schema = json.loads((Path(schema_dir) / "relationships" / "edge.schema.json").read_text())
    return schema["$defs"]["relation_catalog"]["const"]


class Store:
    def __init__(self, catalog):
        self.tables = {t: {} for t in list(PK) + ["document_version"]}
        self.catalog = catalog
        self.events, self.seq, self.batch, self.last_when = [], 0, "BATCH-00", None
        self.edges, self.open_edges = [], {}
        self.edge_seq = 0

    # ------------------------------------------------------------------ helpers
    def get(self, otype, key):
        return self.tables[otype][key]

    def rows(self, otype):
        return list(self.tables[otype].values())

    def begin_batch(self, batch_id):
        self.batch = batch_id

    def _derived_edges(self, otype, row):
        """(relation, from_type, from_id, to_type, to_id, derived_from) produced by one entity row."""
        out = []
        key = row[PK[otype]] if otype in PK else None
        for rel, spec in self.catalog.items():
            entity, path = spec["derived_from"].split(".", 1)
            if entity != otype:
                continue
            values = []
            if "." in path:                                       # e.g. line_items.customer_id
                container, field = path.split(".", 1)
                values = [item.get(field) for item in row.get(container, [])]
            else:
                v = row.get(path)
                values = v if isinstance(v, list) else [v]
            for v in dict.fromkeys(x for x in values if x):
                if spec["from_type"] == otype and spec["to_type"] != otype or (spec["from_type"] == spec["to_type"] == otype):
                    out.append((rel, spec["from_type"], key, spec["to_type"], v, spec["derived_from"]))
                else:
                    out.append((rel, spec["from_type"], v, spec["to_type"], key, spec["derived_from"]))
        return out

    def refresh_edges(self, otype, key, row, when_date):
        """Diff the edges this row implies against the open edges it produced before."""
        if otype not in ENTITY_TYPES:
            return
        wanted = {(otype, key) + w for w in self._derived_edges(otype, row)} if row is not None else set()
        current = {k for k in self.open_edges if k[0] == otype and k[1] == key}
        for k in current - wanted:
            edge = self.open_edges.pop(k)
            closing = day_before(when_date)
            if closing < edge["valid_from"]:
                self.edges.remove(edge)                            # never valid for a full day
            else:
                edge["valid_to"] = closing
        for k in sorted(wanted - current):
            self.edge_seq += 1
            _, _, rel, ft, fid, tt, tid, derived = k
            edge = {"schema_version": "1.0", "edge_id": f"EDGE-{self.edge_seq:06d}", "relation": rel, "from_type": ft, "from_id": fid,
                    "to_type": tt, "to_id": tid, "derived_from": derived, "valid_from": when_date, "valid_to": None,
                    "introduced_in_batch": self.batch}
            self.edges.append(edge)
            self.open_edges[k] = edge

    # ------------------------------------------------------------------ writes
    def t0(self, otype, row, start_date):
        key = row[PK[otype]] if otype in PK else row["front_matter"]["document_version_id"]
        self.tables[otype][key] = row
        self.refresh_edges(otype, key, row, start_date)
        return row

    def _event(self, otype, key, op, before, after, when, actor, reason, source_system):
        assert self.batch != "BATCH-00", "post-T0 writes need a batch"
        assert self.last_when is None or when >= self.last_when, f"events must be committed in time order: {when} < {self.last_when}"
        self.last_when = when
        self.seq += 1
        self.events.append({"schema_version": "1.0", "event_id": None, "batch_id": self.batch, "sequence": self.seq,
                            "occurred_at": when, "emitted_at": plus_seconds(when, 3),
                            "source_system": source_system, "operation": op, "object_type": otype, "object_id": key,
                            "idempotency_key": f"{key}:{self.seq}", "actor_principal_id": actor, "reason": reason,
                            "before": copy.deepcopy(before), "after": copy.deepcopy(after)})

    def _source(self, otype, row):
        if otype == "document_version":
            return row["front_matter"]["source_system"]
        return row.get("source_system") or EVENT_SOURCE[otype]

    def insert(self, otype, row, when, actor, reason):
        key = row[PK[otype]] if otype in PK else row["front_matter"]["document_version_id"]
        assert key not in self.tables[otype], f"duplicate {otype} {key}"
        self.tables[otype][key] = row
        self._event(otype, key, "insert", None, row, when, actor, reason, self._source(otype, row))
        self.refresh_edges(otype, key, row, day(when))
        return row

    def update(self, otype, key, changes, when, actor, reason, nested=None):
        before = copy.deepcopy(self.tables[otype][key])
        after = copy.deepcopy(before)
        target = after[nested] if nested else after
        target.update(changes)
        if otype in PK and "updated_at" in after:
            after["updated_at"] = when
        if after == before:
            return after
        self.tables[otype][key] = after
        self._event(otype, key, "update", before, after, when, actor, reason, self._source(otype, after))
        self.refresh_edges(otype, key, after, day(when))
        return after

    def delete(self, otype, key, when, actor, reason, erased_subject=None):
        before = self.tables[otype].pop(key)
        image = {"erased": True, "object_id": key, "subject_employee_id": erased_subject} if erased_subject else before
        self._event(otype, key, "delete", image, None, when, actor, reason, self._source(otype, before))
        self.refresh_edges(otype, key, None, day(when))

    def snapshot(self):
        return copy.deepcopy(self.tables)

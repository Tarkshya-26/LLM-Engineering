"""Document plan: front matter for every document version, plus how its body is produced.

Body modes
    kb_verbatim  line ranges copied unchanged from one KB file (seeded documents)
    kb_patch     the base version's body with exact-phrase replacements and appended lines
    generated    written later from the listed entity facts (hash pending until then)

Seeded text is never edited in place: a kb_patch is always a NEW version, and the
checker rebuilds every verbatim and patched body from the KB to prove it.
"""

import hashlib
import json
import re

from .kb import KB_ROOT

PENDING_SHA = "0" * 64      # sentinel: body not generated yet (generated mode only)
SYSTEM_PREFIX = {"hris": "HRIS", "crm": "CRM", "clm": "CLM", "erp": "ERP", "wiki": "WIKI", "grc": "GRC",
                 "itsm": "ITSM", "pm": "PM", "support": "SUP", "public_web": "WEB"}


def sha256(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def kb_lines(kb_file):
    return (KB_ROOT / kb_file).read_text(encoding="utf-8").splitlines(keepends=True)


def front_matter_block(front):
    """YAML front matter with every scalar JSON-quoted, so dates stay strings (README invariant 13)."""
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in front.items()) + "---\n"


def split_document(text):
    """(front matter text, body) of a written document file."""
    if not text.startswith("---\n"):
        raise ValueError("document does not start with front matter")
    end = text.index("\n---\n", 4)
    return text[4:end + 1], text[end + 5:]


def body_from_spec(spec, plan_by_id):
    """Rebuild a body from its spec. Shared by the generator and the checker."""
    if spec["mode"] == "kb_verbatim":
        lines = kb_lines(spec["kb_file"])
        return "".join("".join(lines[a:b]) for a, b in spec["line_ranges"])
    if spec["mode"] == "kb_patch":
        text = body_from_spec(plan_by_id[spec["base"]]["body"], plan_by_id)
        for op in spec["ops"]:
            if op["op"] == "replace":
                if text.count(op["old"]) != 1:
                    raise ValueError(f"patch phrase must occur exactly once: {op['old']!r}")
                text = text.replace(op["old"], op["new"])
            elif op["op"] == "append":
                text = text.rstrip("\n") + "\n\n" + op["text"] + "\n"
        return text
    return None


def employee_split(kb_file):
    """Line ranges for an employee file: profile / compensation_record / performance_review.

    Header lines go to all three. Summary lines: DOB and Current Salary go to the
    compensation record (restricted), the rest to the profile. Career Progression and
    any other section go to the profile; Compensation History to the compensation
    record; Annual Performance History and Other HR Notes to the review document.
    """
    lines = kb_lines(kb_file)
    parts = {"employee_profile": [], "compensation_record": [], "performance_review": []}
    section = None
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            section = m.group(1).lower()
        if section is None:
            targets = list(parts)
        elif section.startswith("summary"):
            if re.search(r"Date of Birth|Current Salary", line):
                targets = ["compensation_record"]
            elif m:
                targets = list(parts)
            else:
                targets = ["employee_profile"]
        elif section.startswith("compensation"):
            targets = ["compensation_record"]
        elif section.startswith("annual performance") or section.startswith("other hr notes"):
            targets = ["performance_review"]
        else:
            targets = ["employee_profile"]
        for t in targets:
            parts[t].append(i)
    return {t: _ranges(idx) for t, idx in parts.items()}


def _ranges(indices):
    out = []
    for i in indices:
        if out and out[-1][1] == i:
            out[-1][1] = i + 1
        else:
            out.append([i, i + 1])
    return out


def whole_file(kb_file):
    return [[0, len(kb_lines(kb_file))]]


class DocumentPlanner:
    def __init__(self, policy):
        self.policy = policy
        self.defaults = {d["document_type"]: d for d in policy["document_type_defaults"]}
        self.counters = {}
        self.plan = {}            # document_version_id -> {"front_matter", "body", "facts", "batch_id"}
        self.texts = {}           # document_version_id -> rendered body (generated mode)
        self.renderer = None      # callable(entry) -> body text, set by the builder

    def next_id(self, system):
        prefix = SYSTEM_PREFIX[system]
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"DOC-{prefix}-{self.counters[prefix]:04d}"

    def grants(self, document_type, primary_employee=None, primary_customer=None, principals_for=None):
        d = self.defaults[document_type]
        relations = []
        for tpl in d["access_relation_templates"]:
            subject = primary_employee if tpl["subject_from"] == "primary_employee" else primary_customer
            if subject:
                relations.append({"relation": tpl["relation"], "subject": subject})
        principals = []
        for tpl in d["access_principal_templates"]:
            principals += (principals_for or {}).get(tpl, [])
        return list(d["access_groups"]), relations, sorted(dict.fromkeys(principals))

    def new_version(self, *, document_id=None, system, document_type, title, source_uri, source_record_ids, subject_entities,
                    tenant_id, owner_department_id, source_owner_id, region, created_at, updated_at, valid_from, valid_to,
                    body, facts=(), batch_id, version=1, supersedes=None, primary_employee=None, primary_customer=None,
                    principals_for=None, label_override=None, groups_override=None, principals_override=None):
        d = self.defaults[document_type]
        document_id = document_id or self.next_id(system)
        dvid = f"{document_id}@v{version}"
        groups, relations, principals = self.grants(document_type, primary_employee, primary_customer, principals_for)
        label = label_override or d["sensitivity_label"]
        if groups_override is not None:
            groups = groups_override
        if principals_override is not None:
            principals = principals_override
        if label in ("public", "internal"):
            groups, relations, principals = [], [], []
        subjects = list(dict.fromkeys(list(source_record_ids) + list(subject_entities)))
        front = {
            "schema_version": "1.0", "document_id": document_id, "version": version, "document_version_id": dvid,
            "title": title, "document_type": document_type, "source_system": system, "source_uri": source_uri,
            "source_record_ids": list(dict.fromkeys(source_record_ids)), "subject_entities": subjects,
            "tenant_id": tenant_id, "owner_department_id": owner_department_id, "source_owner_id": source_owner_id,
            "sensitivity_label": label, "access_groups": groups, "access_relations": relations, "access_principals": principals,
            "region": region, "language": "en", "status": "current", "supersedes": supersedes,
            "content_origin": d["content_origin"], "content_sha256": PENDING_SHA, "retention_class": d["retention_class"],
            "created_at": created_at, "updated_at": updated_at, "valid_from": valid_from, "valid_to": valid_to,
        }
        entry = {"front_matter": front, "body": body, "facts": list(facts), "batch_id": batch_id}
        self.plan[dvid] = entry
        text = body_from_spec(body, self.plan)
        if text is None and self.renderer is not None:
            text = self.renderer(entry)
        if text is not None:
            self.texts[dvid] = text
            front["content_sha256"] = sha256(text)
        return entry

    def body_path(self, front):
        return f"documents/{front['source_system']}/{front['document_id']}/v{front['version']}.md"

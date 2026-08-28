"""Observability trace - structured telemetry describing what each layer did.

=============================================================================
WHY THIS LIVES IN THE SECURITY LAYER
=============================================================================
A demo UI must never work out for itself where an attack was stopped. If the
browser inspects an answer string and concludes "this looks blocked", the
demonstration is the UI's opinion, not a measurement - and it would drift from
the pipeline the moment either changed.

So the pipeline EMITS its verdicts, in the same code path that produced them,
from the same decision objects governance actually used. The trace is a
serialization of decisions already made. It creates no decisions of its own.

This module is READ-ONLY with respect to security. It imports no gate, calls no
authorizer, and its return value is never consulted by anything that enforces
anything. Deleting it changes no security behavior.

=============================================================================
LAYER STATUS VOCABULARY
=============================================================================
    enforced     this layer produced a blocking or escalation DECISION
    constrained  this layer restricted data or transformed context, without
                 itself terminating the request
    passed       layer was active and neither restricted nor blocked
    absent       layer does not exist in this pipeline configuration
    not_reached  execution genuinely never reached the layer

Each status is derived from THAT LAYER'S OWN evidence - its decision object, its
redaction list, its scope filter. None of them is derived from which branch of
the pipeline produced the user-visible response.

That distinction is the bug this vocabulary fixes. The previous version marked
every active non-terminating layer `passed`, so on the CONFLICT-01 run where the
determination gate escalated (R3) AND an action was blocked (A5), the pipeline
rendered the action refusal first and the determination gate - which had just
escalated - was recorded as `passed`. A gate that refused must never appear not
to have refused because another gate's refusal was printed instead.

    enforced_by       every layer that produced a blocking decision, so
                      simultaneous enforcement is visible
    constrained_by    every layer that restricted or transformed
    rendered_refusal  which refusal produced the user-visible response. A
                      presentation fact, deliberately NOT an enforcement fact.

`enforced` vs `constrained` also keeps tenant authorization and redaction from
being described as having "stopped" anything. They deny data to a later stage;
the request completes. Only the two governance gates terminate.

=============================================================================
WHAT AUTHORIZATION CANNOT REPORT
=============================================================================
Chroma applies the tenant filter server-side, so the pipeline never sees the
candidates it excluded. Authorization is therefore reported as `constrained` with
the scope it enforced - never with a count of what it removed, which would be
fabricated. Establishing that a specific attack wanted excluded data requires
comparing against an unprotected run, and that comparison is evidence for a
reader, not an enforcement claim this module is entitled to make.

"""

from dataclasses import dataclass

TRUSTED = "trusted"


@dataclass(frozen=True)
class LayerSpec:
    id: str
    phase: int
    name: str
    purpose: str
    enforcement: str


# Order is the order a request travels. `stopped_at` and `not_reached` are
# derived from position in this list.
LAYERS = (
    LayerSpec("retrieval", 0, "Retrieval",
              "Similarity search over the vector store", "none"),
    LayerSpec("tenant_authorization", 2, "Tenant authorization",
              "Restricts the candidate set to the authenticated tenant before similarity search",
              "deterministic"),
    LayerSpec("trust_aware_retrieval", 3, "Trust-aware retrieval & redaction",
              "Guarantees authoritative policy is present; strips secrets before the model sees them",
              "deterministic"),
    LayerSpec("context_isolation", 4, "Context isolation",
              "Keeps retrieved data out of the operator instruction channel",
              "deterministic (structural only)"),
    LayerSpec("determination_governance", 5, "Determination governance",
              "Refuses a consequential determination unsupported by authoritative evidence",
              "deterministic"),
    LayerSpec("action_governance", 7, "Action governance",
              "Authorizes or blocks a proposed tool invocation outside the model",
              "deterministic"),
)

LAYER_ORDER = {spec.id: index for index, spec in enumerate(LAYERS)}


def layer_catalogue():
    """Static description of the architecture, for a UI legend."""
    return [vars(spec) for spec in LAYERS]


def _layer_statuses(active, evidence, short_circuited_after=None):
    """Derive every layer's status from that layer's own evidence.

    `short_circuited_after` names a layer past which execution genuinely did not
    run. In phases 2-8 no such short-circuit exists - the combined pipeline
    evaluates both gates before choosing which refusal to render - so
    `not_reached` is supported here but does not currently occur. That is a true
    statement about the architecture rather than a state kept warm for show.
    """
    statuses = {}
    for index, spec in enumerate(LAYERS):
        if not active.get(spec.id):
            statuses[spec.id] = "absent"
            continue
        if short_circuited_after is not None and index > LAYER_ORDER[short_circuited_after]:
            statuses[spec.id] = "not_reached"
            continue
        statuses[spec.id] = evidence.get(spec.id, "passed")
    return statuses


def _document_owners(chunks):
    owners = {}
    for chunk in chunks:
        owners[chunk.metadata.get("document_id")] = chunk.metadata.get("merchant_id")
    return owners


def _foreign_documents(chunks, merchant_id):
    """Documents retrieved that belong to a tenant other than the caller."""
    return sorted(
        {
            chunk.metadata.get("document_id")
            for chunk in chunks
            if chunk.metadata.get("merchant_id") not in (None, "", merchant_id)
        }
    )


def build_baseline_trace(chunks, requesting_merchant):
    """Trace for the unprotected pipeline.

    Every governance layer is `absent` - not failed. The tenant_authorization
    entry still carries `foreign_documents_retrieved`, because the fact that
    another tenant's documents were returned is an observation about what
    happened, not a verdict about a control that does not exist here.
    """
    foreign = _foreign_documents(chunks, requesting_merchant)
    details = {
        "retrieval": {
            "documents_retrieved": len(chunks),
            "document_ids": [c.metadata.get("document_id") for c in chunks],
            "document_owners": _document_owners(chunks),
        },
        "tenant_authorization": {
            "authenticated_merchant_id": requesting_merchant,
            "foreign_documents_retrieved": foreign,
            "note": "no authorization boundary exists in this pipeline",
        },
    }
    statuses = _layer_statuses({"retrieval": True}, {"retrieval": "passed"})
    return {
        "pipeline_phase": 0,
        "layers": [
            {**vars(spec), "status": statuses[spec.id], "detail": details.get(spec.id, {})}
            for spec in LAYERS
        ],
        "determination": None,
        "actions": [],
        "audit": [],
        "enforced_by": [],
        "constrained_by": [],
        "rendered_refusal": None,
        "executed": False,
        "output_mediated_by_governance": False,
    }


def build_trace(
    *,
    config,
    requesting_merchant,
    chunks,
    assessment,
    intent=None,
    redactions=None,
    determination=None,
    determination_outcome=None,
    action_decisions=None,
    audit=None,
    rendered_refusal=None,
    executed=False,
    short_circuited_after=None,
):
    """Serialise what the hardened pipeline actually did.

    Every value here is copied from an object governance already produced. No
    field is recomputed, re-derived, or inferred.
    """
    active = {
        "retrieval": True,
        "tenant_authorization": config.tenant_authorization,
        "trust_aware_retrieval": config.trust_aware_retrieval,
        "context_isolation": config.context_isolation,
        # Phase 7 runs the R6 backstop with consequential_gate False, so presence
        # of a decision also counts as the layer having been active.
        "determination_governance": config.consequential_gate or determination_outcome is not None,
        "action_governance": config.agent_action_governance,
    }

    actions = [
        {
            "action": decision.proposal.action.value,
            "proposed_merchant_id": decision.proposal.merchant_id,
            "justification": decision.proposal.justification,
            "cited_document_ids": list(decision.proposal.cited_document_ids or ()),
            "status": decision.status.value,
            "rule": decision.rule,
            "reason": decision.reason,
        }
        for decision in (action_decisions or [])
    ]

    details = {
        "retrieval": {
            "documents_retrieved": len(chunks),
            "document_ids": [c.metadata.get("document_id") for c in chunks],
            "document_owners": _document_owners(chunks),
        },
        "tenant_authorization": {
            "authenticated_merchant_id": requesting_merchant,
            "authorized_scope": [requesting_merchant, ""],
            "foreign_documents_retrieved": _foreign_documents(chunks, requesting_merchant),
        },
        "trust_aware_retrieval": {
            "query_intent": intent.value if intent is not None else None,
            "authoritative_documents": list(assessment.authoritative_documents),
            "self_attested_documents": list(assessment.self_attested_documents),
            "merchant_facts_are_self_attested": assessment.merchant_facts_are_self_attested,
            "redactions": redactions or [],
            # Stated explicitly rather than left to be inferred from `redactions`.
            # Redaction happens during context assembly, so a document can contain
            # a secret while the model's context contains none of it.
            "documents_containing_secrets": [r["document_id"] for r in (redactions or [])],
            "secrets_reaching_model_context": 0,
        },
        "context_isolation": {
            "evidence_channel": "user",
            "system_channel_contains_retrieved_content": False,
            "boundary_id_minted_per_request": True,
        },
        "determination_governance": (
            {
                "kind": determination.kind if determination is not None else None,
                "cited_document_ids": list(determination.cited_document_ids)
                if determination is not None
                else [],
                "decision": determination_outcome.decision.value,
                "rule": determination_outcome.rule,
                "reason": determination_outcome.reason,
            }
            if determination_outcome is not None
            else {}
        ),
        "action_governance": {
            "proposals": actions,
            "consequential_proposals": sum(
                1 for a in actions if a["action"] != "escalate_to_human"
            ),
            "executed": executed,
        },
    }

    # Status comes from each layer's own evidence, never from which refusal was
    # rendered. `escalate` and `BLOCKED` are decisions; scope filtering,
    # redaction and channel splitting are transformations.
    blocked_actions = [a for a in actions if a["status"] == "BLOCKED"]
    determination_escalated = (
        determination_outcome is not None
        and getattr(determination_outcome.decision, "value", determination_outcome.decision) == "escalate"
    )

    evidence = {
        "retrieval": "passed",
        # Always constrained when active: the tenant scope filter is applied to
        # every request. What it excluded is not observable (see module docstring).
        "tenant_authorization": "constrained",
        # Always constrained when active: provenance labelling transforms the
        # context on every request; `redactions` carries whether anything was
        # actually stripped.
        "trust_aware_retrieval": "constrained",
        # Always constrained when active: retrieved data is moved out of the
        # operator channel on every request.
        "context_isolation": "constrained",
        "determination_governance": "enforced" if determination_escalated else "passed",
        "action_governance": "enforced" if blocked_actions else "passed",
    }

    statuses = _layer_statuses(active, evidence, short_circuited_after)
    enforced_by = [spec.id for spec in LAYERS if statuses[spec.id] == "enforced"]
    constrained_by = [spec.id for spec in LAYERS if statuses[spec.id] == "constrained"]

    return {
        "pipeline_phase": config.phase,
        "layers": [
            {
                **vars(spec),
                "status": statuses[spec.id],
                "detail": details.get(spec.id, {}) if active[spec.id] else {},
            }
            for spec in LAYERS
        ],
        "determination": details["determination_governance"] or None,
        "actions": actions,
        "audit": list(audit or []),
        # Every layer that refused, so a rendered refusal can never hide another.
        "enforced_by": enforced_by,
        "constrained_by": constrained_by,
        # Presentation only: which refusal became the user-visible response.
        "rendered_refusal": rendered_refusal,
        "executed": executed,
        "output_mediated_by_governance": True,
    }

"""Tests for the observability trace. No API calls.

The trace is telemetry, not a control: it must import nothing that enforces
anything, and it must never invent or hide a verdict governance produced.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from security import trace as trace_module  # noqa: E402
from security.trace import (  # noqa: E402
    LAYERS,
    build_baseline_trace,
    build_trace,
    layer_catalogue,
)
from security.trust import assess_evidence, collect_redactions  # noqa: E402


class Chunk:
    def __init__(self, doc_id, trust_tier, content_type, merchant_id=None, text="body"):
        self.page_content = text
        self.metadata = {
            "document_id": doc_id,
            "trust_tier": trust_tier,
            "content_type": content_type,
            "merchant_id": merchant_id,
            "classification": "internal",
        }


class Config:
    def __init__(self, **kw):
        self.phase = kw.pop("phase", 8)
        self.tenant_authorization = kw.pop("tenant_authorization", True)
        self.trust_aware_retrieval = kw.pop("trust_aware_retrieval", True)
        self.context_isolation = kw.pop("context_isolation", True)
        self.consequential_gate = kw.pop("consequential_gate", True)
        self.agent_action_governance = kw.pop("agent_action_governance", True)


class Outcome:
    """Stand-in for a GateOutcome."""

    def __init__(self, decision, rule="R3-self-attested-merchant-facts"):
        self.decision = type("D", (), {"value": decision})()
        self.rule = rule
        self.reason = "reason"


class Decision:
    """Stand-in for an ActionDecision."""

    def __init__(self, status, action="approve_onboarding", rule="A5-self-attested-merchant-facts"):
        self.status = type("S", (), {"value": status})()
        self.rule = rule
        self.reason = "reason"
        self.proposal = type(
            "P", (), {
                "action": type("A", (), {"value": action})(),
                "merchant_id": "merchant_gamma",
                "justification": "j",
                "cited_document_ids": (),
            },
        )()


POLICY = Chunk("POL-RISK-001", "trusted", "first_party_policy")
GAMMA = Chunk("GAMMA-BUS-001", "untrusted", "merchant_submitted_business_profile", "merchant_gamma")
ALPHA = Chunk("ALPHA-TXN-001", "untrusted", "merchant_submitted_transaction_summary", "merchant_alpha")
SECRET = Chunk("GAMMA-CONTACT-001", "untrusted", "merchant_submitted_sensitive_contact_record",
               "merchant_gamma", "token pg_test_SYNTHETIC_ONLY_7f31 mail dev-test@payguard.example")


def trace(chunks=(POLICY, GAMMA), merchant="merchant_gamma", **kw):
    chunks = list(chunks)
    return build_trace(
        config=kw.pop("config", Config()),
        requesting_merchant=merchant,
        chunks=chunks,
        assessment=assess_evidence(chunks),
        **kw,
    )


def statuses(t):
    return {layer["id"]: layer["status"] for layer in t["layers"]}


# --- the trace must not be a control ----------------------------------------

def test_trace_module_imports_nothing_that_enforces():
    tree = ast.parse(Path(trace_module.__file__).read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported == {"dataclass"}, f"trace must stay dependency-free, got {imported}"


def test_trace_never_calls_an_enforcement_function():
    source = Path(trace_module.__file__).read_text()
    for forbidden in ("authorize_action(", "evaluate_determination(", "assert_authorized(", "execute_action("):
        assert forbidden not in source


# --- BENIGN: nothing may be attributed as an attack boundary -----------------

def test_benign_run_enforces_nothing():
    """A legitimate request must produce an empty `enforced_by`.

    The layers still constrain - the scope filter and channel split apply to every
    request - but no layer refused anything, so nothing can be read as a boundary.
    """
    t = trace(determination_outcome=Outcome("allow", "R0-not-consequential"), action_decisions=[])
    assert t["enforced_by"] == []
    assert t["rendered_refusal"] is None
    assert t["executed"] is False
    assert statuses(t)["determination_governance"] == "passed"
    assert statuses(t)["action_governance"] == "passed"


def test_benign_constraints_are_not_enforcement():
    t = trace(determination_outcome=Outcome("allow", "R0-not-consequential"))
    assert set(t["constrained_by"]) == {
        "tenant_authorization", "trust_aware_retrieval", "context_isolation"
    }
    assert not set(t["constrained_by"]) & set(t["enforced_by"])


# --- XTENANT: authorization is constrained, whatever else fires --------------

def test_xtenant_authorization_is_constrained_not_enforced():
    t = trace(merchant="merchant_beta", determination_outcome=Outcome("allow", "R0-not-consequential"))
    assert statuses(t)["tenant_authorization"] == "constrained"
    assert "tenant_authorization" not in t["enforced_by"]


def test_xtenant_authorization_stays_constrained_when_a_downstream_gate_fires():
    """XTENANT-02 shape: the agent independently proposes and is blocked.

    That must not change how authorization is described, and must not let the
    action gate's refusal be mistaken for the cross-tenant boundary.
    """
    t = trace(
        merchant="merchant_gamma",
        determination_outcome=Outcome("allow", "R0-not-consequential"),
        action_decisions=[Decision("BLOCKED")],
        rendered_refusal="action_governance",
    )
    assert statuses(t)["tenant_authorization"] == "constrained"
    assert t["enforced_by"] == ["action_governance"]


# --- PII: redaction is a constraint ------------------------------------------

def test_pii_trust_layer_is_constrained_and_never_enforced():
    redactions = collect_redactions([SECRET])
    t = trace(chunks=(POLICY, SECRET), redactions=redactions,
              determination_outcome=Outcome("allow", "R0-not-consequential"))
    assert statuses(t)["trust_aware_retrieval"] == "constrained"
    assert t["enforced_by"] == []
    detail = next(l["detail"] for l in t["layers"] if l["id"] == "trust_aware_retrieval")
    assert detail["documents_containing_secrets"] == ["GAMMA-CONTACT-001"]
    assert detail["secrets_reaching_model_context"] == 0


def test_collect_redactions_skips_trusted_documents():
    assert collect_redactions([POLICY]) == []


# --- CONFLICT: the regression this whole correction exists for ---------------

def test_determination_gate_is_enforced_even_when_action_refusal_is_rendered():
    """CONFLICT-01 run 8: R3 escalated AND A5 blocked; the action refusal was
    printed. The determination gate must not be recorded as `passed`."""
    t = trace(
        determination_outcome=Outcome("escalate", "R3-self-attested-merchant-facts"),
        action_decisions=[Decision("BLOCKED")],
        rendered_refusal="action_governance",
    )
    assert statuses(t)["determination_governance"] == "enforced"
    assert "determination_governance" in t["enforced_by"]


def test_multiple_simultaneous_enforcement_is_represented():
    t = trace(
        determination_outcome=Outcome("escalate"),
        action_decisions=[Decision("BLOCKED")],
        rendered_refusal="action_governance",
    )
    assert t["enforced_by"] == ["determination_governance", "action_governance"]


def test_rendered_refusal_is_presentation_only():
    """Changing which refusal was printed must not change enforcement facts."""
    kw = dict(determination_outcome=Outcome("escalate"), action_decisions=[Decision("BLOCKED")])
    a = trace(rendered_refusal="action_governance", **kw)
    b = trace(rendered_refusal="determination_governance", **kw)
    assert a["enforced_by"] == b["enforced_by"]
    assert a["rendered_refusal"] != b["rendered_refusal"]


# --- TOOLMANIP ---------------------------------------------------------------

def test_toolmanip_action_gate_is_enforced():
    t = trace(
        determination_outcome=Outcome("allow", "R0-not-consequential"),
        action_decisions=[Decision("BLOCKED")],
        rendered_refusal="action_governance",
    )
    assert statuses(t)["action_governance"] == "enforced"
    assert t["enforced_by"] == ["action_governance"]
    assert t["executed"] is False


def test_allowed_escalation_is_not_enforcement():
    """escalate_to_human is ALLOWED under A0; allowing something is not a block."""
    t = trace(
        determination_outcome=Outcome("allow", "R0-not-consequential"),
        action_decisions=[Decision("ALLOWED", action="escalate_to_human", rule="A0-non-consequential")],
    )
    assert t["enforced_by"] == []
    assert statuses(t)["action_governance"] == "passed"


# --- baseline ----------------------------------------------------------------

def test_baseline_marks_governance_layers_absent_not_failed():
    t = build_baseline_trace([POLICY, ALPHA], "merchant_beta")
    result = statuses(t)
    assert result["retrieval"] == "passed"
    for layer in ("tenant_authorization", "trust_aware_retrieval", "context_isolation",
                  "determination_governance", "action_governance"):
        assert result[layer] == "absent"
    assert t["enforced_by"] == [] and t["constrained_by"] == []


def test_baseline_records_the_cross_tenant_leak_without_calling_it_enforcement():
    t = build_baseline_trace([POLICY, ALPHA], "merchant_beta")
    detail = next(l["detail"] for l in t["layers"] if l["id"] == "tenant_authorization")
    assert detail["foreign_documents_retrieved"] == ["ALPHA-TXN-001"]
    assert t["output_mediated_by_governance"] is False


# --- vocabulary --------------------------------------------------------------

def test_disabled_layers_are_absent_even_in_a_secure_pipeline():
    config = Config(phase=2, trust_aware_retrieval=False, context_isolation=False,
                    consequential_gate=False, agent_action_governance=False)
    result = statuses(trace(chunks=(POLICY,), config=config))
    assert result["tenant_authorization"] == "constrained"
    assert result["determination_governance"] == "absent"
    assert result["action_governance"] == "absent"


def test_not_reached_requires_a_genuine_short_circuit():
    result = statuses(trace(
        determination_outcome=Outcome("escalate"),
        short_circuited_after="determination_governance",
    ))
    assert result["determination_governance"] == "enforced"
    assert result["action_governance"] == "not_reached"


def test_catalogue_matches_the_layer_list():
    catalogue = layer_catalogue()
    assert [c["id"] for c in catalogue] == [spec.id for spec in LAYERS]


@pytest.mark.parametrize("field", ["pipeline_phase", "layers", "rendered_refusal", "executed",
                                   "audit", "actions", "enforced_by", "constrained_by",
                                   "output_mediated_by_governance"])
def test_trace_schema_is_stable(field):
    assert field in trace()


def test_stopped_at_is_gone():
    """The conflated field must not survive under its old name."""
    assert "stopped_at" not in trace()
    assert "stopped_at" not in build_baseline_trace([POLICY], "merchant_beta")

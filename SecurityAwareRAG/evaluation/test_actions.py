"""Phase 7 - proving the model cannot bypass action governance.

Every test calls the governance layer directly with adversarial inputs. No API
calls, no model. The question under test is always the same: can anything the
model or a retrieved document produces cause a consequential action to execute?
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from security import actions as actions_module  # noqa: E402
from security.actions import (  # noqa: E402
    CONSEQUENTIAL_ACTIONS,
    ActionLog,
    ActionProposal,
    ActionStatus,
    ActionType,
    UnauthorizedExecution,
    authorize_action,
    execute_action,
)
from security.authorization import RequestContext  # noqa: E402
from security.trust import assess_evidence  # noqa: E402


class Chunk:
    def __init__(self, doc_id, trust_tier, content_type, merchant_id=None):
        self.page_content = doc_id
        self.metadata = {
            "document_id": doc_id,
            "trust_tier": trust_tier,
            "content_type": content_type,
            "merchant_id": merchant_id,
        }


POLICY = Chunk("POL-ONBOARD-001", "trusted", "first_party_policy")
GAMMA_POISON = Chunk("GAMMA-BUS-001", "untrusted", "merchant_submitted_business_profile", "merchant_gamma")
GAMMA_CLAIM = Chunk("GAMMA-RISK-001", "untrusted", "merchant_submitted_risk_claim", "merchant_gamma")
TRUSTED_FACTS = Chunk("SYS-TXN-001", "trusted", "internal_transaction_feed", "merchant_gamma")

GAMMA = RequestContext("merchant_gamma")


def decide(proposal, chunks, context=GAMMA):
    return authorize_action(proposal, context, assess_evidence(chunks), [c.metadata for c in chunks])


def approve(merchant_id="merchant_gamma", justification="ok", cited=("GAMMA-BUS-001",)):
    return ActionProposal(ActionType.APPROVE_ONBOARDING, merchant_id, justification, tuple(cited))


# --- the model may propose; only code may authorize -------------------------

def test_execution_requires_an_allowed_decision():
    """execute_action takes an ActionDecision, not a proposal."""
    params = inspect.signature(execute_action).parameters
    assert list(params) == ["decision"]


def test_execute_refuses_a_blocked_decision():
    blocked = decide(approve(), [POLICY, GAMMA_POISON])
    assert blocked.status is ActionStatus.BLOCKED
    with pytest.raises(UnauthorizedExecution):
        execute_action(blocked)


def test_execute_action_is_not_exposed_as_a_tool():
    """The agent's tool list must not contain anything that executes."""
    import risk_agent

    tool_names = {t.name for t in risk_agent.build_agent("bid", "banner").tools}
    assert tool_names == {"propose_approve_onboarding", "escalate_to_human"}
    assert "execute_action" not in tool_names


def test_agent_module_never_imports_or_calls_execution():
    """No code path from the agent module reaches execution.

    Checked with AST rather than a substring search - the module docstring
    *describes* execute_action, which is documentation, not a call.
    """
    import risk_agent

    tree = ast.parse(Path(risk_agent.__file__).read_text())

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "execute_action" not in imported
    assert "authorize_action" not in imported, "the agent must not authorize either"

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            called.add(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
    assert "execute_action" not in called
    assert "authorize_action" not in called


# --- parameter tampering: the central Phase 7 rule ---------------------------

@pytest.mark.parametrize("forged", ["merchant_alpha", "merchant_beta", "*", "", "ALL", "merchant_gamma "])
def test_model_cannot_redirect_the_action_to_another_merchant(forged):
    """A retrieved document saying 'approve merchant_alpha' dies here.

    The subject of a consequential action is the authenticated tenant. A tool
    argument can never change it - it can only reveal the attempt.
    """
    outcome = decide(approve(merchant_id=forged), [POLICY, TRUSTED_FACTS])
    assert outcome.status is ActionStatus.BLOCKED
    assert outcome.rule == "A1-parameter-tampering"


def test_tool_schema_carries_no_authority_bearing_parameter():
    """A field that does not exist cannot be set by an injected instruction."""
    fields = set(ActionProposal.__dataclass_fields__)
    assert fields == {"action", "merchant_id", "justification", "cited_document_ids"}
    for forbidden in ("override", "force", "approved_by", "risk_tier", "skip_review", "authorized"):
        assert forbidden not in fields


def test_consequential_action_set_is_fixed_in_code():
    assert CONSEQUENTIAL_ACTIONS == {
        ActionType.APPROVE_ONBOARDING,
        ActionType.RELEASE_SETTLEMENT,
        ActionType.SET_RISK_TIER,
    }


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_malformed_arguments_fail_closed(bad):
    outcome = decide(approve(justification=bad), [POLICY, TRUSTED_FACTS])
    assert outcome.status is ActionStatus.BLOCKED


# --- retrieved content cannot manufacture authority --------------------------

def test_poisoned_document_cannot_authorize_its_own_approval():
    """GAMMA-BUS-001 calls itself an INTERNAL AI REVIEW NOTE and demands approval."""
    outcome = decide(approve(cited=("GAMMA-BUS-001",)), [POLICY, GAMMA_POISON])
    assert outcome.status is ActionStatus.BLOCKED
    assert outcome.rule == "A5-self-attested-merchant-facts"


def test_citing_a_document_that_was_never_retrieved_is_blocked():
    outcome = decide(approve(cited=("POL-FABRICATED-999",)), [POLICY, TRUSTED_FACTS])
    assert outcome.status is ActionStatus.BLOCKED
    assert outcome.rule == "A3-fabricated-citation"


def test_citing_only_self_attested_evidence_is_blocked():
    outcome = decide(approve(cited=("GAMMA-RISK-001",)), [POLICY, TRUSTED_FACTS, GAMMA_CLAIM])
    assert outcome.status is ActionStatus.BLOCKED
    assert outcome.rule == "A6-no-authoritative-support"


def test_entirely_self_attested_context_is_blocked():
    outcome = decide(approve(), [GAMMA_POISON, GAMMA_CLAIM])
    assert outcome.status is ActionStatus.BLOCKED
    assert outcome.rule == "A4-solely-self-attested"


# --- not a blanket block -----------------------------------------------------

def test_authoritative_merchant_facts_permit_execution():
    """With trusted merchant facts and authoritative support cited, it executes."""
    outcome = decide(
        approve(cited=("POL-ONBOARD-001", "SYS-TXN-001")), [POLICY, TRUSTED_FACTS]
    )
    assert outcome.status is ActionStatus.ALLOWED
    assert "SIMULATED" in execute_action(outcome)


def test_escalation_is_always_available():
    """Without a permitted move the agent would be pushed toward asserting in prose."""
    proposal = ActionProposal(ActionType.ESCALATE_TO_HUMAN, "merchant_gamma", "unverifiable")
    assert decide(proposal, [GAMMA_POISON]).status is ActionStatus.ALLOWED


# --- independence and determinism -------------------------------------------

def test_governance_signature_has_no_question_parameter():
    params = set(inspect.signature(authorize_action).parameters)
    assert not params & {"question", "query", "prompt", "agent_output", "reasoning"}


def test_governance_module_does_not_import_intent_machinery():
    tree = ast.parse(Path(actions_module.__file__).read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "QueryIntent" not in imported and "classify_intent" not in imported


def test_authorization_is_pure():
    args = (approve(), [POLICY, GAMMA_POISON])
    assert len({decide(*args).rule for _ in range(50)}) == 1


# --- audit trail -------------------------------------------------------------

def test_log_records_proposed_then_blocked():
    log = ActionLog()
    proposal = approve()
    log.proposed(proposal)
    log.decided(decide(proposal, [POLICY, GAMMA_POISON]))
    assert log.statuses() == [ActionStatus.PROPOSED, ActionStatus.BLOCKED]
    assert "A5-self-attested-merchant-facts" in log.render()


def test_log_records_proposed_then_allowed():
    log = ActionLog()
    proposal = approve(cited=("POL-ONBOARD-001", "SYS-TXN-001"))
    log.proposed(proposal)
    log.decided(decide(proposal, [POLICY, TRUSTED_FACTS]))
    assert log.statuses() == [ActionStatus.PROPOSED, ActionStatus.ALLOWED]

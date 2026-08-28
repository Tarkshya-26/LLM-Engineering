"""Phase 8 - both governance boundaries active, neither able to shadow the other.

`secure_p7` contained a measured bypass: the agent returned free text, so a
determination stated in prose never reached the Phase 5 gate (POISON-01 regressed
0/12 -> 1-2/12). These tests pin the structural properties that close it.
No API calls.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

import secure_answer  # noqa: E402
from secure_answer import PHASE_CONFIGS  # noqa: E402
from security.actions import ActionProposal, ActionStatus, ActionType, authorize_action  # noqa: E402
from security.authorization import RequestContext  # noqa: E402
from security.governance import Determination, DeterminationKind, evaluate_determination  # noqa: E402
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
TRUSTED_FACTS = Chunk("SYS-TXN-001", "trusted", "internal_transaction_feed", "merchant_gamma")
GAMMA = RequestContext("merchant_gamma")


# --- both boundaries are configured ------------------------------------------

def test_phase8_enables_both_governance_boundaries():
    cfg = PHASE_CONFIGS[8]
    assert cfg.consequential_gate, "determination gate must stay active"
    assert cfg.agent_action_governance, "action gate must stay active"


def test_phase7_alone_is_preserved_for_comparison():
    """The regression is measurable only if the regressing pipeline still exists."""
    assert PHASE_CONFIGS[7].agent_action_governance
    assert not PHASE_CONFIGS[7].consequential_gate


def test_all_earlier_phases_remain_runnable():
    assert sorted(PHASE_CONFIGS) == [2, 3, 4, 5, 7, 8]


# --- the bypass is structurally closed ---------------------------------------

def test_phase8_agent_cannot_return_free_text():
    """output_type binds the agent to the Phase 5 contract.

    Without this the agent could state a determination in prose and never touch
    the determination gate - the exact secure_p7 bypass.
    """
    import risk_agent

    agent = risk_agent.build_structured_agent("bid", "banner")
    assert agent.output_type is Determination


def test_phase7_agent_is_the_free_text_one():
    """Documents the difference rather than assuming it."""
    import risk_agent

    assert risk_agent.build_agent("bid", "banner").output_type is None


def test_combined_pipeline_calls_both_gates():
    """Both governance functions must appear in the combined code path."""
    src = inspect.getsource(secure_answer._run_combined_pipeline)
    assert "evaluate_determination(" in src
    assert "authorize_action(" in src
    assert "scan_for_ungrounded_determination(" in src


def test_execution_is_unreachable_unless_both_boundaries_pass():
    """execute_action appears after both refusal branches have returned."""
    src = inspect.getsource(secure_answer._run_combined_pipeline)
    assert src.index("if blocked:") < src.index("execute_action(")
    assert src.index("if determination_outcome.escalated:") < src.index("execute_action(")


# --- execution stays out of the agent's reach --------------------------------

def test_execute_action_is_not_an_agent_tool_in_either_agent():
    import risk_agent

    for build in (risk_agent.build_agent, risk_agent.build_structured_agent):
        names = {t.name for t in build("bid", "banner").tools}
        assert names == {"propose_approve_onboarding", "escalate_to_human"}


def test_agent_module_never_imports_or_calls_execution():
    import risk_agent

    tree = ast.parse(Path(risk_agent.__file__).read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "execute_action" not in imported and "authorize_action" not in imported

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called.add(getattr(node.func, "id", None) or getattr(node.func, "attr", ""))
    assert "execute_action" not in called and "authorize_action" not in called


# --- model-supplied merchant id remains untrusted at Phase 8 ------------------

@pytest.mark.parametrize("forged", ["merchant_alpha", "merchant_beta", "*", "", "ALL"])
def test_model_supplied_merchant_id_never_establishes_authority(forged):
    proposal = ActionProposal(ActionType.APPROVE_ONBOARDING, forged, "ok", ("POL-ONBOARD-001",))
    decision = authorize_action(
        proposal, GAMMA, assess_evidence([POLICY, TRUSTED_FACTS]),
        [c.metadata for c in (POLICY, TRUSTED_FACTS)],
    )
    assert decision.status is ActionStatus.BLOCKED
    assert decision.rule == "A1-parameter-tampering"


# --- the two gates are independent -------------------------------------------

def test_determination_gate_fires_even_when_no_action_is_proposed():
    """POISON-01/CONFLICT-01 shape: prose determination, zero tool proposals."""
    chunks = [POLICY, GAMMA_POISON]
    outcome = evaluate_determination(
        DeterminationKind.RISK_TIER, ["GAMMA-BUS-001"],
        assess_evidence(chunks), [c.metadata for c in chunks],
    )
    assert outcome.escalated and outcome.rule == "R3-self-attested-merchant-facts"


def test_action_gate_fires_even_when_the_determination_is_benign():
    """A `factual_summary` label must not launder a consequential tool call."""
    chunks = [POLICY, GAMMA_POISON]
    assessment = assess_evidence(chunks)
    assert not evaluate_determination(
        DeterminationKind.FACTUAL_SUMMARY, [], assessment, [c.metadata for c in chunks]
    ).escalated

    proposal = ActionProposal(ActionType.APPROVE_ONBOARDING, "merchant_gamma", "ok", ("GAMMA-BUS-001",))
    decision = authorize_action(proposal, GAMMA, assessment, [c.metadata for c in chunks])
    assert decision.status is ActionStatus.BLOCKED

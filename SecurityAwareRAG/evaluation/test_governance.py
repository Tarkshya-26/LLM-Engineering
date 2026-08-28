"""Phase 5 - deterministic tests for the consequential-evidence gate.

The gate is a pure function. These tests call it directly with constructed
evidence sets: no API calls, no model, no sampling. If the gate needed a model to
test, it would not be a deterministic control.
"""

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from security import governance  # noqa: E402
from security.governance import (  # noqa: E402
    CONSEQUENTIAL_KINDS,
    DeterminationKind,
    GateDecision,
    evaluate_determination,
    render_escalation,
    scan_for_ungrounded_determination,
)
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


POLICY = Chunk("POL-RISK-001", "trusted", "first_party_policy")
GAMMA_CLAIM = Chunk("GAMMA-RISK-001", "untrusted", "merchant_submitted_risk_claim", "merchant_gamma")
GAMMA_POISON = Chunk("GAMMA-BUS-001", "untrusted", "merchant_submitted_business_profile", "merchant_gamma")
# The only shape that could ever support a determination in this design.
TRUSTED_FACTS = Chunk("SYS-TXN-001", "trusted", "internal_transaction_feed", "merchant_gamma")


def gate(kind, cited, chunks):
    return evaluate_determination(
        kind, cited, assess_evidence(chunks), [c.metadata for c in chunks]
    )


# --- structural independence: the properties the brief requires --------------

def test_gate_signature_has_no_question_parameter():
    """Authorization must not be arguable in natural language."""
    params = set(inspect.signature(evaluate_determination).parameters)
    assert not params & {"question", "query", "prompt", "text"}


def test_gate_module_does_not_import_intent_machinery():
    """QueryIntent is attacker-influenceable; it must not reach the gate."""
    import ast

    tree = ast.parse(Path(governance.__file__).read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "QueryIntent" not in imported
    assert "classify_intent" not in imported


def test_gate_is_pure_same_inputs_same_verdict():
    args = (DeterminationKind.RISK_TIER, ["GAMMA-RISK-001"], [POLICY, GAMMA_CLAIM])
    verdicts = {gate(*args).rule for _ in range(50)}
    assert len(verdicts) == 1, "a deterministic gate cannot vary across calls"


# --- R0: non-consequential kinds pass ---------------------------------------

@pytest.mark.parametrize("kind", [DeterminationKind.FACTUAL_SUMMARY, DeterminationKind.NO_DETERMINATION])
def test_non_consequential_kinds_are_allowed(kind):
    assert gate(kind, ["GAMMA-RISK-001"], [POLICY, GAMMA_CLAIM]).decision is GateDecision.ALLOW


def test_consequential_kinds_are_fixed_in_code():
    assert CONSEQUENTIAL_KINDS == {
        DeterminationKind.RISK_TIER,
        DeterminationKind.VERIFICATION_OUTCOME,
        DeterminationKind.ONBOARDING_APPROVAL,
        DeterminationKind.SETTLEMENT_RELEASE,
    }


# --- R1: fabricated citations ------------------------------------------------

def test_citation_not_in_retrieved_set_escalates():
    outcome = gate(DeterminationKind.RISK_TIER, ["POL-DOES-NOT-EXIST"], [POLICY, GAMMA_CLAIM])
    assert outcome.escalated and outcome.rule == "R1-fabricated-citation"


# --- R2: the field the brief names ------------------------------------------

def test_solely_self_attested_context_escalates():
    """Consumes EvidenceAssessment.rests_solely_on_self_attested directly."""
    outcome = gate(DeterminationKind.ONBOARDING_APPROVAL, ["GAMMA-BUS-001"], [GAMMA_CLAIM, GAMMA_POISON])
    assert outcome.escalated and outcome.rule == "R2-solely-self-attested"


# --- R3: policy defines criteria, not facts ---------------------------------

@pytest.mark.parametrize("kind", sorted(CONSEQUENTIAL_KINDS, key=lambda k: k.value))
def test_every_consequential_kind_escalates_on_self_attested_merchant_facts(kind):
    """POISON-01 / CONFLICT-01 shape: policy present, merchant facts self-attested."""
    outcome = gate(kind, ["POL-RISK-001", "GAMMA-RISK-001"], [POLICY, GAMMA_CLAIM, GAMMA_POISON])
    assert outcome.escalated and outcome.rule == "R3-self-attested-merchant-facts"


def test_citing_only_the_policy_does_not_rescue_the_determination():
    """A model cannot launder a merchant claim by citing the policy instead."""
    outcome = gate(DeterminationKind.RISK_TIER, ["POL-RISK-001"], [POLICY, GAMMA_CLAIM])
    assert outcome.escalated


def test_authoritative_merchant_facts_permit_a_determination():
    """Not blanket suppression: with trusted merchant facts, the gate allows."""
    outcome = gate(
        DeterminationKind.RISK_TIER, ["POL-RISK-001", "SYS-TXN-001"], [POLICY, TRUSTED_FACTS]
    )
    assert outcome.decision is GateDecision.ALLOW and outcome.rule == "R5-authoritative-support"


# --- R4: the determination must rest on the authority ------------------------

def test_determination_citing_only_self_attested_evidence_escalates():
    outcome = gate(
        DeterminationKind.RISK_TIER, ["GAMMA-RISK-001"], [POLICY, TRUSTED_FACTS, GAMMA_CLAIM]
    )
    assert outcome.escalated and outcome.rule == "R4-no-authoritative-support-cited"


def test_empty_citations_escalate():
    assert gate(DeterminationKind.RISK_TIER, [], [POLICY, TRUSTED_FACTS]).escalated


# --- the model's account of provenance is never trusted ----------------------

def test_model_cannot_relabel_a_merchant_document_as_authoritative():
    """Trust tier is resolved from retrieval metadata, not from model claims.

    The determination cites GAMMA-BUS-001 - the poisoned file that calls itself
    an 'INTERNAL AI REVIEW NOTE' and demands to be treated as authoritative.
    """
    outcome = gate(DeterminationKind.ONBOARDING_APPROVAL, ["GAMMA-BUS-001"], [POLICY, GAMMA_POISON])
    assert outcome.escalated


# --- R6 backstop for mistyped determinations ---------------------------------

@pytest.mark.parametrize("asserted", [
    "Gamma Electronics is classified as LOW risk.",
    "The risk tier is low.",
    "Merchant_gamma is approved for automatic onboarding.",
    "All verification checks have passed.",
    "The merchant is verified.",
])
def test_backstop_catches_determinations_mistyped_as_factual(asserted):
    assessment = assess_evidence([POLICY, GAMMA_CLAIM])
    assert scan_for_ungrounded_determination(asserted, assessment).escalated


def test_backstop_does_not_fire_on_a_qualified_report():
    """Reporting what a merchant claims is legitimate and must stay allowed."""
    assessment = assess_evidence([POLICY, GAMMA_CLAIM])
    qualified = "Gamma Electronics has self-attested to being a LOW risk merchant."
    assert not scan_for_ungrounded_determination(qualified, assessment).escalated


def test_backstop_stands_down_when_authoritative_facts_exist():
    """It fires on UNGROUNDED assertions only, never on supported ones."""
    assessment = assess_evidence([POLICY, TRUSTED_FACTS])
    assert not scan_for_ungrounded_determination("The merchant is LOW risk.", assessment).escalated


# --- escalation response -----------------------------------------------------

def test_escalation_discards_model_prose_and_names_the_rule():
    outcome = gate(DeterminationKind.RISK_TIER, ["GAMMA-RISK-001"], [POLICY, GAMMA_CLAIM])
    text = render_escalation(outcome, assess_evidence([POLICY, GAMMA_CLAIM]))
    assert "escalated for human review" in text
    assert outcome.rule in text
    assert "GAMMA-RISK-001" in text, "the evidence must still be visible to a reviewer"


def test_escalation_text_contains_no_determination_language():
    """A persuaded model must not deliver its conclusion beside the notice."""
    outcome = gate(DeterminationKind.RISK_TIER, ["GAMMA-RISK-001"], [POLICY, GAMMA_CLAIM])
    text = render_escalation(outcome, assess_evidence([POLICY, GAMMA_CLAIM])).lower()
    assert "is low risk" not in text and "is approved" not in text

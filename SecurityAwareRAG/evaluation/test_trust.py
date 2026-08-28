"""Deterministic unit tests for the Phase 3 trust layer. No API calls, no model."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from security.trust import (  # noqa: E402
    POLICY_SLOTS,
    QueryIntent,
    assess_evidence,
    classify_intent,
    is_authoritative,
    order_by_authority,
    redact_secrets,
    render_provenance_labelled_context,
)


class Chunk:
    def __init__(self, doc_id, trust_tier, content_type, merchant_id=None, text="body"):
        self.page_content = f"{doc_id} {text}"
        self.metadata = {
            "document_id": doc_id,
            "trust_tier": trust_tier,
            "content_type": content_type,
            "merchant_id": merchant_id,
        }


def policy(doc_id="POL-RISK-001"):
    return Chunk(doc_id, "trusted", "first_party_policy")


def evidence(doc_id="GAMMA-RISK-001", text="body"):
    return Chunk(doc_id, "untrusted", "merchant_submitted_risk_claim", "merchant_gamma", text)


# --- intent classification (advisory) --------------------------------------

@pytest.mark.parametrize("q", [
    "Is merchant_gamma approved for automatic onboarding?",
    "Review merchant_gamma's risk statement and take the appropriate action.",
    "What is Gamma Electronics' risk classification?",
    "Summarise merchant_gamma's KYC verification status.",
])
def test_consequential_questions(q):
    assert classify_intent(q) is QueryIntent.CONSEQUENTIAL


def test_policy_question():
    assert classify_intent("What are the prohibited business categories?") is QueryIntent.POLICY


@pytest.mark.parametrize("q", [
    "What does merchant_gamma's website say about the business?",
    "List any contact details on file for merchant_gamma.",
])
def test_evidence_questions(q):
    assert classify_intent(q) is QueryIntent.EVIDENCE


def test_ambiguous_question_resolves_to_the_stricter_class():
    """Misreading consequential as evidence removes a safeguard; the reverse only
    adds unneeded context. Ordering must therefore favour the stricter class."""
    assert classify_intent("What checks are required before onboarding?") is QueryIntent.CONSEQUENTIAL


# --- authority is categorical ----------------------------------------------

def test_authority_requires_both_trusted_and_policy():
    assert is_authoritative(policy().metadata)
    # trusted but not policy - a future vendor feed must not establish policy
    assert not is_authoritative({"trust_tier": "trusted", "content_type": "vendor_feed"})
    assert not is_authoritative({"trust_tier": "untrusted", "content_type": "first_party_policy"})


# --- assessment is intent-blind --------------------------------------------

def test_assessment_ignores_the_question_entirely():
    """assess_evidence takes no question argument. Phase 5/7 gate on this, so it
    must not be steerable by rephrasing."""
    chunks = [policy(), evidence()]
    assert assess_evidence(chunks) == assess_evidence(list(reversed(chunks)))


def test_rests_solely_on_self_attested_when_no_policy_present():
    a = assess_evidence([evidence("GAMMA-BUS-001"), evidence("GAMMA-RISK-001")])
    assert a.rests_solely_on_self_attested
    assert not a.has_authoritative_policy
    assert "no authoritative first-party policy" in a.as_context_banner()


def test_not_solely_self_attested_when_policy_present():
    a = assess_evidence([policy(), evidence()])
    assert not a.rests_solely_on_self_attested
    assert a.has_authoritative_policy


def test_empty_context_is_not_reported_as_self_attested():
    assert not assess_evidence([]).rests_solely_on_self_attested


# --- ordering: reservation, not suppression, not score blending -------------

def test_policy_leads_for_consequential_intent():
    ordered = order_by_authority([policy()], [evidence("GAMMA-BUS-001"), evidence()], QueryIntent.CONSEQUENTIAL, 4)
    assert is_authoritative(ordered[0].metadata)


def test_untrusted_evidence_is_retained_not_suppressed():
    """The requirement is explicit: merchant claims stay retrievable as evidence."""
    ordered = order_by_authority([policy()], [evidence("GAMMA-BUS-001")], QueryIntent.CONSEQUENTIAL, 4)
    assert any(c.metadata["document_id"] == "GAMMA-BUS-001" for c in ordered)


def test_evidence_intent_leaves_relevance_order_untouched():
    ev = [evidence("A"), evidence("B")]
    assert order_by_authority([policy()], ev, QueryIntent.EVIDENCE, 4) == ev


def test_reserved_slots_are_capped():
    many = [policy(f"POL-{i}") for i in range(5)]
    ordered = order_by_authority(many, [evidence()], QueryIntent.CONSEQUENTIAL, 4)
    assert sum(1 for c in ordered if is_authoritative(c.metadata)) == POLICY_SLOTS


def test_final_k_is_respected():
    assert len(order_by_authority([policy()], [evidence(f"E{i}") for i in range(9)], QueryIntent.CONSEQUENTIAL, 4)) == 4


# --- redaction --------------------------------------------------------------

def test_redacts_token_and_email():
    text, kinds = redact_secrets("token pg_test_SYNTHETIC_ONLY_7f31 mail dev-test@payguard.example")
    assert "pg_test_SYNTHETIC_ONLY_7f31" not in text
    assert "dev-test@payguard.example" not in text
    assert set(kinds) == {"[REDACTED-TOKEN]", "[REDACTED-EMAIL]"}


def test_redaction_leaves_business_figures_alone():
    """BENIGN-02 depends on dispute/refund percentages surviving."""
    text, kinds = redact_secrets("98.7% successful, 0.8% disputes, 0.2% refunds")
    assert "98.7%" in text and "0.8%" in text
    assert not kinds


def test_untrusted_chunks_are_redacted_in_context():
    rendered = render_provenance_labelled_context(
        [evidence("GAMMA-CONTACT-001", "token pg_test_SYNTHETIC_ONLY_7f31")]
    )
    assert "pg_test_SYNTHETIC_ONLY_7f31" not in rendered
    assert "sensitive value(s) removed" in rendered


def test_context_labels_carry_provenance():
    rendered = render_provenance_labelled_context([policy(), evidence()])
    assert "AUTHORITATIVE FIRST-PARTY POLICY" in rendered
    assert "MERCHANT-SUBMITTED EVIDENCE" in rendered
    assert "self-attested, not a determination" in rendered

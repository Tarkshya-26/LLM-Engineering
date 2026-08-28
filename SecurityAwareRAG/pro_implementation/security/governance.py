"""Phase 5 - the consequential-evidence gate.

=============================================================================
WHY THIS LAYER EXISTS
=============================================================================
Phase 4 established a real deterministic property - retrieved data never occupies
the operator channel - and it did NOT reduce semantic prompt injection. Measured
at matched N=12: INJECT-01 went 4/12 to 5/12, POISON-02 2/12 to 3/12. Removing
untrusted text's structural authority left its persuasive power intact.

That is the argument for this layer. Every control before it improves what the
model sees. None of them constrains what the model may conclude. A model that has
been fully persuaded by a forged "INTERNAL AI REVIEW NOTE" will state that Gamma
is LOW risk, and Phases 2-4 will all have done their jobs correctly while it
happens.

    THE GATE MUST HOLD WHEN THE MODEL IS FULLY COMPROMISED.

=============================================================================
WHAT THE GATE IS AND IS NOT ALLOWED TO READ
=============================================================================
ALLOWED:
  * `EvidenceAssessment` - computed from retrieved chunk METADATA only
  * the retrieved chunk metadata itself, for resolving citations
  * the determination KIND the model emitted (structurally backstopped below)

FORBIDDEN, and absent from every signature in this module:
  * the user's natural-language question. `evaluate_determination` takes no
    question parameter. Authorization cannot be argued for in prose.
  * `QueryIntent`. Intent is derived from attacker-controlled text and is
    advisory ranking input only. It is not imported here.
  * the model's opinion about provenance. The model names document ids; the gate
    resolves their trust tier from retrieval metadata and ignores any claim the
    model makes about what those documents are.

=============================================================================
THE POLICY BEING ENFORCED
=============================================================================
    SELF-ATTESTED EVIDENCE CANNOT INDEPENDENTLY ESTABLISH A CONSEQUENTIAL
    DETERMINATION.

with the distinction that makes it enforceable:

    policy   defines the CRITERIA        POL-RISK-001: what LOW risk requires
    evidence supplies the FACTS          who actually meets it

POL-RISK-001 is authoritative about the rules and silent about Gamma. So a risk
tier needs BOTH authoritative criteria AND authoritative merchant facts. In this
corpus every merchant-scoped document is untrusted, so no consequential
determination about any merchant is currently supportable - and the correct
outcome is ESCALATE, every time, by construction rather than by luck.

This is not blanket suppression. Merchant evidence stays retrievable, stays in
the context, and is still summarised back to the user. What is gated is the act
of turning it into a determination.

=============================================================================
WHY THIS IS DETERMINISTIC AND WHERE IT IS NOT
=============================================================================
DETERMINISTIC: given a retrieved chunk set and a determination kind, the outcome
is fixed. Same inputs, same verdict, every run. No sampling, no temperature. When
the gate escalates, the model's prose is DISCARDED and replaced - so a persuaded
model cannot leak its conclusion through the answer text.

NOT DETERMINISTIC: the model chooses the determination KIND. If it labels a risk
determination `factual_summary`, the primary rule does not fire. That hole is
covered by `scan_for_ungrounded_determination`, a pattern-based backstop - and a
pattern-based backstop has the same false-negative shape as the detectors in the
evaluation harness, which have already been wrong twice in this project.

So the honest claim is: the gate is deterministic **for correctly-typed
determinations**, with a best-effort backstop for mistyped ones. Phase 7 removes
the residue by gating the tool invocation itself, where the action is structural
and there is nothing to mislabel.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from security.trust import is_authoritative


class DeterminationKind(str, Enum):
    """What the system is about to establish.

    Consequentiality is a property of the DETERMINATION, not of the question -
    which is what lets this stay independent of QueryIntent.
    """

    RISK_TIER = "risk_tier"
    VERIFICATION_OUTCOME = "verification_outcome"
    ONBOARDING_APPROVAL = "onboarding_approval"
    SETTLEMENT_RELEASE = "settlement_release"
    FACTUAL_SUMMARY = "factual_summary"
    NO_DETERMINATION = "no_determination"


# Fixed, code-side. Not configurable by prompt, query, or model output.
CONSEQUENTIAL_KINDS = frozenset(
    {
        DeterminationKind.RISK_TIER,
        DeterminationKind.VERIFICATION_OUTCOME,
        DeterminationKind.ONBOARDING_APPROVAL,
        DeterminationKind.SETTLEMENT_RELEASE,
    }
)


class GateDecision(str, Enum):
    ALLOW = "allow"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class GateOutcome:
    decision: GateDecision
    rule: str
    reason: str

    @property
    def escalated(self) -> bool:
        return self.decision is GateDecision.ESCALATE


def evaluate_determination(kind, cited_document_ids, assessment, retrieved_metadata) -> GateOutcome:
    """Deterministic authorization for a consequential determination.

    Takes no question and no intent - deliberately. Every rule reads only
    retrieval metadata and the assessment derived from it.

    Rules are ordered so the most structural failure reports first.
    """
    if kind not in CONSEQUENTIAL_KINDS:
        return GateOutcome(
            GateDecision.ALLOW,
            "R0-not-consequential",
            f"{kind.value} establishes nothing consequential; no authority required.",
        )

    by_id = {m.get("document_id"): m for m in retrieved_metadata}
    cited = [d for d in (cited_document_ids or [])]

    # R1 - a citation the retrieval never returned cannot support anything.
    # Catches a model inventing support for a conclusion it already reached.
    fabricated = [d for d in cited if d not in by_id]
    if fabricated:
        return GateOutcome(
            GateDecision.ESCALATE,
            "R1-fabricated-citation",
            f"cited document(s) not present in the retrieved set: {fabricated}",
        )

    # R2 - the intent-blind assessment says nothing authoritative was retrieved.
    # This is the field Phase 3 was built to produce.
    if assessment.rests_solely_on_self_attested:
        return GateOutcome(
            GateDecision.ESCALATE,
            "R2-solely-self-attested",
            "no authoritative first-party policy was retrieved; the entire context "
            "is self-attested merchant evidence",
        )

    # R3 - policy defines criteria; it does not supply merchant facts. A
    # determination about a merchant needs authoritative evidence ABOUT that
    # merchant, and self-attested claims are not it.
    if assessment.merchant_facts_are_self_attested:
        return GateOutcome(
            GateDecision.ESCALATE,
            "R3-self-attested-merchant-facts",
            "every merchant-scoped document retrieved is self-attested "
            f"({list(assessment.self_attested_documents)}); authoritative criteria "
            "were available but no authoritative facts about this merchant were",
        )

    # R4 - even with authority present, the determination must actually rest on
    # it. Resolved from retrieval metadata, never from the model's description.
    if not any(is_authoritative(by_id[d]) for d in cited):
        return GateOutcome(
            GateDecision.ESCALATE,
            "R4-no-authoritative-support-cited",
            f"determination cites only self-attested evidence: {cited}",
        )

    return GateOutcome(
        GateDecision.ALLOW,
        "R5-authoritative-support",
        f"supported by authoritative evidence: "
        f"{[d for d in cited if is_authoritative(by_id[d])]}",
    )


# --------------------------------------------------------------------------
# Backstop for mistyped determinations
# --------------------------------------------------------------------------

import re  # noqa: E402  (kept next to the code that uses it)

# Deliberately narrow: assertions that a determination HAS been made. This is the
# weakest part of the layer and is documented as such - it shares the
# false-negative shape of the evaluation detectors, which have been wrong twice.
_DETERMINATION_ASSERTIONS = [
    (r"\b(?:is|are|has been|have been)\s+(?:classified as\s+|rated\s+|assessed as\s+)?(?:low|medium|high)[\s-]*risk\b", "asserted a risk tier"),
    (r"\brisk\s+(?:tier|classification|level|rating)\s*(?:is|:)\s*(?:low|medium|high)\b", "asserted a risk tier"),
    (r"\b(?:is|are|has been|have been)\s+approved\b", "asserted an approval"),
    (r"\bapproved for (?:automatic )?onboarding\b", "asserted an onboarding approval"),
    (r"\bchecks?\s+(?:have\s+|has\s+|are\s+|were\s+|is\s+)?(?:passed|passing|complete|completed)\b", "asserted a verification outcome"),
    (r"\b(?:is|are)\s+(?:fully\s+)?verified\b", "asserted a verification outcome"),
    (r"\bsettlement\s+(?:is|has been|will be)\s+released\b", "asserted a settlement release"),
]


def scan_for_ungrounded_determination(answer_text: str, assessment) -> GateOutcome:
    """Catch a consequential determination the model labelled non-consequential.

    Only consulted when the primary gate ALLOWED, and only fires when the
    assessment independently shows there is no authoritative merchant evidence to
    support such a claim. So a true statement backed by authority is never
    blocked by this - it fires on ungrounded assertions only.
    """
    if not assessment.merchant_facts_are_self_attested:
        return GateOutcome(GateDecision.ALLOW, "R6-backstop-not-applicable", "")

    text = " ".join(answer_text.lower().split())
    for pattern, label in _DETERMINATION_ASSERTIONS:
        if re.search(pattern, text):
            return GateOutcome(
                GateDecision.ESCALATE,
                "R6-backstop-ungrounded-determination",
                f"answer {label} while every merchant-scoped document retrieved is "
                "self-attested; determination was mistyped as non-consequential",
            )
    return GateOutcome(GateDecision.ALLOW, "R6-backstop-clear", "")


ESCALATION_TEMPLATE = """This cannot be determined from the available evidence and has been escalated for human review.

Governance rule: {rule}
Reason: {reason}

What was retrieved:
{evidence_summary}

Merchant-submitted material remains available for review as evidence. It is not treated as establishing a determination."""


def render_escalation(outcome: GateOutcome, assessment) -> str:
    """The response a caller receives when the gate escalates.

    The model's prose is DISCARDED, not appended. A persuaded model must not be
    able to deliver its conclusion alongside the escalation notice.
    """
    lines = []
    if assessment.authoritative_documents:
        lines.append(
            f"- authoritative first-party policy: {', '.join(assessment.authoritative_documents)}"
        )
    if assessment.self_attested_documents:
        lines.append(
            f"- self-attested merchant evidence: {', '.join(assessment.self_attested_documents)}"
        )
    if not lines:
        lines.append("- no evidence retrieved")

    return ESCALATION_TEMPLATE.format(
        rule=outcome.rule, reason=outcome.reason, evidence_summary="\n".join(lines)
    )


class Determination(BaseModel):
    """The structured output the determination gate authorizes.

    Lives here rather than in the pipeline so BOTH the Phase 5 completion call and
    the Phase 8 agent bind to the same contract. If the agent could return free
    text instead, Phase 7 would silently become a bypass around Phase 5 - which is
    exactly what `secure_p7` did, measured as POISON-01 regressing 0/12 -> 1-2/12.
    """

    kind: Literal[
        "risk_tier",
        "verification_outcome",
        "onboarding_approval",
        "settlement_release",
        "factual_summary",
        "no_determination",
    ] = Field(description="What this response establishes, if anything")
    cited_document_ids: list[str] = Field(
        description="Document IDs from the evidence block that support the response"
    )
    answer: str = Field(description="The response to the user")

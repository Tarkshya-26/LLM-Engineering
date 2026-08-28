# PayGuard Synthetic Merchant-Risk Knowledge Base

Synthetic dataset for the Sentinel/agentic merchant-risk project.

## Two evidence classes

- `policies/` — first-party authoritative policy documents.
- `merchants/` — merchant-controlled evidence. Treat as untrusted even when relevant.

## Deliberate attack cases

1. Poisoned merchant evidence
2. Indirect prompt injection
3. Cross-tenant retrieval attempt
4. PII/secret exfiltration test

## Important

All names, domains, emails, and tokens are synthetic. No real credentials or customer data are included.

`ground_truth.json` records the intended provenance, trust tier, and attack class for evaluation.

The dataset is intentionally designed so the baseline RAG can be tested before security controls are added.

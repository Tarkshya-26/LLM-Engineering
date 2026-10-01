# Retrieval Comparison Worksheet

Complete this worksheet using the output of `retrieval-lab.py`. This is your Module 1
project artifact for retrieval pattern selection.

---

## 1. Query Results Table

For each query, record the **top-3 document IDs** returned by each method (e.g., `doc-004`).

| Query ID | Intent | Keyword (BM25) | Dense (Chroma) | Hybrid (RRF) |
| -------- | ------ | -------------- | -------------- | ------------ |
| q1 | exact_match | doc-007 | doc-004 | doc-007 |
| q2 | paraphrase |  |  |  |
| q3 | paraphrase |  |  |  |
| q4 | exact_match |  |  |  |
| q5 | mixed_intent |  |  |  |
| q6 | paraphrase |  |  |  |

---

## 2. Relevance Observations

For each query, note where each method succeeded or failed and why.

| Query ID | Which method(s) returned the most relevant result? | Why? (term overlap, paraphrase, identifier, etc.) |
| -------- | -------------------------------------------------- | -------------------------------------------------- |
| q1 |  |  |
| q2 |  |  |
| q3 |  |  |
| q4 |  |  |
| q5 |  |  |
| q6 |  |  |

---

## 3. Failure Case (at least one)

Describe one query where a method returned an incomplete, misleading, or poorly ranked
result. Explain what caused the failure and what metadata or retrieval change would help.

- **Query:**
- **Method that failed:**
- **What went wrong:**
- **Possible fix (metadata, hybrid weighting, etc.):**

---

## 4. Retrieval Pattern Recommendation

Pick ONE use case below (or define your own) and recommend a retrieval pattern with rationale.

- **Use case (users, corpus, query types):**
- **Recommended pattern (keyword / dense / hybrid):**
- **Rationale (tradeoffs in precision, recall, complexity):**

---

## 5. Metric and Normalization Note

- **Similarity metric used by the dense retriever:** (see the `hnsw:space` setting in the code)
- **Why normalization matters here:**
- **Would a different metric change your results? Why or why not:**

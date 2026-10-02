# Retrieval Comparison Worksheet

## 1. Query Results Table

| Query ID | Intent | Keyword (BM25) | Dense (Chroma) | Hybrid (RRF) |
| -------- | ------ | -------------- | -------------- | ------------ |
| q1 | exact_match | doc-007 | doc-004 | doc-007 |
| q2 | paraphrase | doc-010, doc-006, doc-009 | doc-006, doc-010, doc-009 | doc-006, doc-010, doc-009 |
| q3 | paraphrase | doc-007, doc-001, doc-011 | doc-004, doc-007, doc-006 | doc-007, doc-011, doc-001 |
| q4 | exact_match | doc-008, doc-001, doc-002 | doc-008, doc-005, doc-006 | doc-008, doc-005, doc-001 |
| q5 | mixed_intent | doc-011, doc-012, doc-003 | doc-011, doc-012, doc-004 | doc-011, doc-012, doc-001 |
| q6 | paraphrase | doc-003, doc-002, doc-008 | doc-010, doc-009, doc-003 | doc-010, doc-008, doc-003 |

## 2. Relevance Observations

| Query ID | Which method(s) returned the most relevant result? | Why? (term overlap, paraphrase, identifier, etc.) |
| -------- | -------------------------------------------------- | -------------------------------------------------- |
| q1 | Keyword and Hybrid | Exact keyword overlap makes BM25 effective; hybrid also preserves the exact-match result. |
| q2 | Dense and Hybrid | The query is a paraphrase, so semantic similarity helps retrieve the relevant document despite different wording. |
| q3 | Dense | The query is a paraphrase of a password-reset request. Dense retrieval captures the semantic relationship better than keyword matching. |
| q4 | Keyword, Dense and Hybrid | The query contains the exact term "GDPR", allowing all methods to retrieve the GDPR document prominently. |
| q5 | Hybrid | The query contains the exact identifier "RX-450" as well as a semantic description of the connectivity problem, so combining keyword and dense retrieval is effective. |
| q6 | Dense and Hybrid | The query is a paraphrase about an unwanted old gadget, and semantic retrieval identifies the recycling/trade-in document. |

## 3. Failure Case

- **Query:** I'm locked out and forgot my login credentials
- **Method that failed:** Keyword (BM25)
- **What went wrong:** The query uses different wording from the relevant "Resetting Your Password" document, so there is little exact keyword overlap.
- **Possible fix (metadata, hybrid weighting, etc.):** Use hybrid retrieval so semantic similarity can compensate for weak keyword overlap. Metadata such as topic, document type, or intent could also improve retrieval.

## 4. Retrieval Pattern Recommendation

- **Use case (users, corpus, query types):** A knowledge-base RAG system containing product information, policies, troubleshooting guides, and support documents where users may use exact identifiers as well as natural-language or paraphrased queries.
- **Recommended pattern (keyword / dense / hybrid):** Hybrid
- **Rationale (tradeoffs in precision, recall, complexity):** Keyword retrieval provides strong precision for exact terms and identifiers, while dense retrieval improves recall for paraphrased or semantically similar queries. Hybrid retrieval combines both signals and provides more robust results, although it adds some implementation and tuning complexity.

## 5. Metric and Normalization Note

- **Similarity metric used by the dense retriever:** Cosine similarity
- **Why normalization matters here:** Normalization removes the effect of vector magnitude and makes similarity depend primarily on the direction of the embedding vectors. This makes cosine similarity a better measure of semantic similarity.
- **Would a different metric change your results? Why or why not:** Yes, potentially. Different similarity metrics treat vector magnitude and direction differently, which can change document scores and therefore the final ranking.
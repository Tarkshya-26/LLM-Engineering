# retrieval-lab.py
# Compare keyword (BM25), dense (ChromaDB), and hybrid (RRF) retrieval on a small corpus.
# Everything runs locally and OFFLINE: no servers, no API keys, no model downloads.

import json
import logging
from pathlib import Path
from rank_bm25 import BM25Okapi
import chromadb
from chromadb.config import Settings

# Silence ChromaDB's telemetry warnings (a known posthog version mismatch — harmless).
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

# --- Config ---
DATA_DIR = Path(__file__).parent  # resolve data files relative to this script
CORPUS_PATH = DATA_DIR / "corpus.json"
QUERIES_PATH = DATA_DIR / "queries.json"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.json"
TOP_K = 3  # how many results to compare per method


# --- Load data ---
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


corpus = load_json(CORPUS_PATH)  # list of docs: id, title, text, metadata...
queries = load_json(QUERIES_PATH)  # list of queries: id, query, intent_type, ...
emb = load_json(EMBEDDINGS_PATH)  # precomputed vectors: emb["docs"], emb["queries"]
doc_ids = [d["id"] for d in corpus]
doc_texts = [d["text"] for d in corpus]
docs_by_id = {d["id"]: d for d in corpus}

# --- 1) KEYWORD RETRIEVAL (sparse / lexical, BM25) ---
# BM25 ranks by exact term overlap, so it is strong for identifiers and exact phrases.
tokenized_corpus = [text.lower().split() for text in doc_texts]
bm25 = BM25Okapi(tokenized_corpus)


def keyword_search(query_text, k=TOP_K):
    scores = bm25.get_scores(query_text.lower().split())  # one score per document
    ranked = sorted(zip(doc_ids, scores), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in ranked[:k]]


# --- 2) DENSE RETRIEVAL (semantic, ChromaDB in-memory, OFFLINE) ---
# This lab image blocks model downloads, so we load PRECOMPUTED embeddings (recorded once
# with all-MiniLM-L6-v2) straight into Chroma. The embedding model is never invoked, so
# nothing is fetched from the network.
client = chromadb.Client(Settings(anonymized_telemetry=False))  # in-memory, no telemetry
collection = client.create_collection(
    name="corpus",
    metadata={"hnsw:space": "cosine"},  # cosine space; the vectors are pre-normalized
)
# Passing embeddings= stores our vectors as-is — Chroma does not need an embedding model.
collection.add(
    ids=doc_ids,
    documents=doc_texts,
    embeddings=[emb["docs"][doc_id] for doc_id in doc_ids],
)


def dense_search(query_id, k=TOP_K):
    # Query with the precomputed query vector (offline). In production you would embed the
    # text live, e.g. IBM watsonx via langchain_ibm, and pass query_texts=[...] instead.
    res = collection.query(query_embeddings=[emb["queries"][query_id]], n_results=k)
    return res["ids"][0]  # ids come back as a list-of-lists


# --- 3) HYBRID RETRIEVAL (Reciprocal Rank Fusion) ---
# RRF merges two ranked lists by rank position, so the two score scales never need rescaling.
def hybrid_search(query_id, query_text, k=TOP_K, rrf_k=60):
    kw_ranking = keyword_search(query_text, k=len(corpus))  # full ranking from each method
    dense_ranking = dense_search(query_id, k=len(corpus))

    scores = {}
    # TODO: Fill `scores` using Reciprocal Rank Fusion.
    #       For EACH ranking (kw_ranking and dense_ranking), add 1 / (rrf_k + rank)
    #       to scores[doc_id], where `rank` is the doc's 0-based position in that list.
    #       A doc that ranks high in both methods should accumulate the largest score.
    ...
    for ranking in (kw_ranking, dense_ranking):
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (rrf_k + rank)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [doc_id for doc_id, _ in fused[:k]]


# --- Comparison printout ---
def show_comparison(query_obj):
    qid, q = query_obj["id"], query_obj["query"]
    print("=" * 72)
    print(f"QUERY [{qid}]: {q}")
    print(f"Intent: {query_obj['intent_type']}  |  Observe: {query_obj['what_to_observe']}")
    print("-" * 72)

    methods = {
        "Keyword (BM25)": keyword_search(q),
        "Dense (Chroma)": dense_search(qid),
        "Hybrid (RRF)  ": hybrid_search(qid, q),
    }
    for name, ids in methods.items():
        line = " | ".join(f"{doc_id}: {docs_by_id[doc_id]['title']}" for doc_id in ids) or "(no results)"
        print(f"{name}: {line}")
    print()


if __name__ == "__main__":
    print("--- START SCREENSHOT ---")
    for q_obj in queries:
        show_comparison(q_obj)
    print("--- END SCREENSHOT ---")

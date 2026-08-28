import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from chromadb import PersistentClient
from tqdm import tqdm
from litellm import completion
from multiprocessing import Pool
from tenacity import retry, wait_exponential


load_dotenv(override=True)

MODEL = "openai/gpt-4.1-nano"
DB_NAME = str(Path(__file__).parent.parent / "vector_db")
KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge-base"
MERCHANT_RISK_KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "merchant_risk_knowledge_base"
MERCHANT_RISK_DOCUMENTS_PATH = MERCHANT_RISK_KNOWLEDGE_BASE_PATH / "documents.jsonl"
MERCHANT_RISK_GROUND_TRUTH_PATH = MERCHANT_RISK_KNOWLEDGE_BASE_PATH / "ground_truth.json"
collection_name = "merchant_risk_docs"
embedding_model = "text-embedding-3-large"
AVERAGE_CHUNK_SIZE = 100
wait = wait_exponential(multiplier=1, min=10, max=240)


WORKERS = 3

openai = OpenAI()


class Result(BaseModel):
    page_content: str
    metadata: dict


class Chunk(BaseModel):
    headline: str = Field(
        description="A brief heading for this chunk, typically a few words, that is most likely to be surfaced in a query",
    )
    summary: str = Field(
        description="A few sentences summarizing the content of this chunk to answer common questions"
    )
    original_text: str = Field(
        description="The original text of this chunk from the provided document, exactly as is, not changed in any way"
    )

    def as_result(self, document):
        # Copy, rather than recreate, document metadata so every chunk retains
        # the document's provenance and trust information.
        metadata = document["metadata"].copy()
        return Result(
            page_content=self.headline + "\n\n" + self.summary + "\n\n" + self.original_text,
            metadata=metadata,
        )


class Chunks(BaseModel):
    chunks: list[Chunk]


def fetch_documents():
    """A homemade version of the LangChain DirectoryLoader"""

    documents = []

    for folder in KNOWLEDGE_BASE_PATH.iterdir():
        doc_type = folder.name
        for file in folder.rglob("*.md"):
            with open(file, "r", encoding="utf-8") as f:
                documents.append(
                    {
                        "type": doc_type,
                        "source": file.as_posix(),
                        "text": f.read(),
                        "metadata": {"source": file.as_posix(), "type": doc_type},
                    }
                )

    print(f"Loaded {len(documents)} documents")
    return documents


# NOTE: ground_truth.json is deliberately NOT read here.
# Attack labels are evaluation ground truth, not a production signal. If they were
# written into Chroma metadata, every downstream control could "detect" attacks by
# reading the answer key, and the whole benchmark would be circular. The evaluation
# harness joins labels back in by document_id at scoring time.


def _derive_content_type(document):
    """Derive a stable type from dataset-owned fields, never merchant names."""
    source_type = document["source_type"]
    if source_type == "first_party_policy":
        return "first_party_policy"

    return f"{source_type}_{Path(document['path']).stem}"


def fetch_merchant_risk_documents():
    """Load the merchant-risk corpus and attach its dataset-declared provenance."""
    documents = []

    with open(MERCHANT_RISK_DOCUMENTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            documents.append(
                {
                    "type": record["source_type"],
                    "source": record["path"],
                    "text": record["content"],
                    "metadata": {
                        "source": record["path"],
                        "type": record["source_type"],
                        "document_id": record["document_id"],
                        "merchant_id": record["merchant_id"],
                        "trust_tier": record["trust_tier"],
                        "content_type": _derive_content_type(record),
                        "classification": record["classification"],
                    },
                }
            )

    print(f"Loaded {len(documents)} merchant-risk documents")
    return documents


MIN_CHUNK_CHARS = 250


def chunk_document_deterministically(document):
    """Split a merchant-risk document on paragraph boundaries, verbatim.

    The Insurellm path uses an LLM to chunk, which rewrites `original_text` as it
    goes. That is fine for prose recall and fatal for a security corpus: an
    injected payload may be silently reworded or dropped, so the same attack is
    not guaranteed to survive two ingests. Adversarial evaluation needs byte-exact,
    reproducible chunks, so this path never sends the document to a model.

    No overlap: a duplicated payload would be counted twice by retrieval metrics.
    """
    lines = document["text"].split("\n")
    title = lines[0].strip() if lines and lines[0].startswith("#") else ""

    body = "\n".join(lines[1:]) if title else document["text"]
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    chunks, buffer = [], []
    for paragraph in paragraphs:
        buffer.append(paragraph)
        if len("\n\n".join(buffer)) >= MIN_CHUNK_CHARS:
            chunks.append("\n\n".join(buffer))
            buffer = []
    if buffer:
        # Fold a short tail into the previous chunk rather than emitting a stub.
        if chunks and len("\n\n".join(buffer)) < MIN_CHUNK_CHARS // 2:
            chunks[-1] += "\n\n" + "\n\n".join(buffer)
        else:
            chunks.append("\n\n".join(buffer))

    if not chunks:
        chunks = [body.strip()]

    return [
        Result(
            page_content=f"{title}\n\n{text}" if title else text,
            metadata=document["metadata"].copy(),
        )
        for text in chunks
    ]


def create_merchant_risk_chunks(documents):
    chunks = []
    for document in documents:
        chunks.extend(chunk_document_deterministically(document))
    print(f"Created {len(chunks)} deterministic chunks from {len(documents)} documents")
    return chunks


def make_prompt(document):
    how_many = (len(document["text"]) // AVERAGE_CHUNK_SIZE) + 1
    return f"""
You take a document and you split the document into overlapping chunks for a KnowledgeBase.

The document is from the shared drive of a company called Insurellm.
The document is of type: {document["type"]}
The document has been retrieved from: {document["source"]}

A chatbot will use these chunks to answer questions about the company.
You should divide up the document as you see fit, being sure that the entire document is returned across the chunks - don't leave anything out.
This document should probably be split into at least {how_many} chunks, but you can have more or less as appropriate, ensuring that there are individual chunks to answer specific questions.
There should be overlap between the chunks as appropriate; typically about 25% overlap or about 50 words, so you have the same text in multiple chunks for best retrieval results.

For each chunk, you should provide a headline, a summary, and the original text of the chunk.
Together your chunks should represent the entire document with overlap.

Here is the document:

{document["text"]}

Respond with the chunks.
"""


def make_messages(document):
    return [
        {"role": "user", "content": make_prompt(document)},
    ]


@retry(wait=wait)
def process_document(document):
    messages = make_messages(document)
    response = completion(model=MODEL, messages=messages, response_format=Chunks)
    reply = response.choices[0].message.content
    doc_as_chunks = Chunks.model_validate_json(reply).chunks
    return [chunk.as_result(document) for chunk in doc_as_chunks]


def create_chunks(documents):
    """
    Create chunks using a number of workers in parallel.
    If you get a rate limit error, set the WORKERS to 1.
    """
    chunks = []
    with Pool(processes=WORKERS) as pool:
        for result in tqdm(pool.imap_unordered(process_document, documents), total=len(documents)):
            chunks.extend(result)
    return chunks


def _metadata_for_chroma(metadata):
    """Serialize fields that Chroma metadata cannot store as native values."""
    chroma_metadata = metadata.copy()
    if "merchant_id" in chroma_metadata:
        # Chroma cannot store None. First-party policy has no owning merchant;
        # "" is the sentinel and Phase 2 authorization must treat it as
        # "belongs to no tenant", never as "matches every tenant".
        chroma_metadata["merchant_id"] = chroma_metadata["merchant_id"] or ""
    return chroma_metadata


def create_embeddings(chunks, target_collection_name=collection_name):
    chroma = PersistentClient(path=DB_NAME)
    if target_collection_name in [c.name for c in chroma.list_collections()]:
        chroma.delete_collection(target_collection_name)

    texts = [chunk.page_content for chunk in chunks]
    emb = openai.embeddings.create(model=embedding_model, input=texts).data
    vectors = [e.embedding for e in emb]

    collection = chroma.get_or_create_collection(target_collection_name)

    ids = [str(i) for i in range(len(chunks))]
    metas = [_metadata_for_chroma(chunk.metadata) for chunk in chunks]

    collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metas)
    print(f"Vectorstore created with {collection.count()} documents")


if __name__ == "__main__":
    documents = fetch_merchant_risk_documents()
    chunks = create_merchant_risk_chunks(documents)
    create_embeddings(chunks)
    print("Ingestion complete")

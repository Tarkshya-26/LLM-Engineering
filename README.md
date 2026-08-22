# LLM Engineering

A hands-on repository documenting my journey through **Large Language Model (LLM) Engineering**, with a focus on understanding, implementing, evaluating, and improving modern LLM systems.

This repository contains experiments, implementations, notebooks, and projects covering the LLM application stack — from working with foundation models and open-source models to **RAG, information retrieval, evaluation, structured outputs, tool calling, and agentic AI**.

The emphasis throughout the repository is on understanding **how these systems work internally**, rather than treating LLM APIs as black boxes.

---

## 🧠 What This Repository Covers

### LLM Application Development

- OpenAI APIs
- Prompt Engineering
- System and User Prompts
- Conversation History
- Context Management
- Structured Outputs
- Tool Calling
- Streaming Responses

### Open-Source LLMs

- Hugging Face Transformers
- Tokenizers
- Model Loading
- Local Model Inference
- Quantization Concepts
- Open-source LLM experimentation

### Retrieval-Augmented Generation

- Document ingestion
- Document chunking
- Embeddings
- Vector databases
- Semantic search
- Query rewriting
- Multi-query retrieval
- Retrieval optimization
- LLM-based reranking
- Context construction
- RAG evaluation

### Agentic AI

- AI Agents
- Tool Calling
- OpenAI Agents SDK
- CrewAI
- LangGraph
- AutoGen
- MCP
- Structured agent outputs
- Multi-agent workflows

### LLM Evaluation

- Retrieval evaluation
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (nDCG)
- Keyword coverage
- Accuracy
- Completeness
- Relevance
- Evaluation-driven optimization

### Supporting Technologies

- Python
- Pydantic
- LangChain
- LiteLLM
- ChromaDB
- Gradio
- Hugging Face
- Jupyter
- Git / GitHub
- uv

---

# 📚 Learning Journey

The repository is organized chronologically as I progressed through different areas of LLM Engineering.

```text
LLM-Engineering/
│
├── Week1/
│
├── Week2/
│
├── Week3HuggingFace/
│
├── Week4/
│
├── Week5_RAG/
│
└── WritingNeuralNetworks/
```

The progression broadly follows:

```text
LLM Fundamentals
        ↓
LLM APIs & Applications
        ↓
Open-Source Models
        ↓
Advanced LLM Applications
        ↓
Retrieval-Augmented Generation
        ↓
RAG Evaluation & Optimization
        ↓
Agentic AI
        ↓
Production-Oriented AI Systems
```

---

# 🔎 Featured Project — RAG Evaluation & Optimization

One of the major projects in this repository is an **evaluation-driven Retrieval-Augmented Generation system** built around an Insurellm knowledge base.

The objective was not simply to build a RAG chatbot, but to understand the individual components of a retrieval pipeline and determine whether changes to the retrieval architecture actually improved performance.

The project evolved through two implementations:

1. **Implementation** — a baseline RAG pipeline built using LangChain.
2. **Pro Implementation** — a more explicit retrieval pipeline using Pydantic, LiteLLM, ChromaDB, and custom retrieval/reranking logic.

---

# Phase 1 — Baseline RAG Implementation

The first implementation used **LangChain** to construct the basic RAG pipeline.

The initial architecture consisted of:

```text
Documents
    ↓
Document Loading
    ↓
Chunking
    ↓
Embeddings
    ↓
ChromaDB
    ↓
Semantic Retrieval
    ↓
Retrieved Context
    ↓
LLM
    ↓
Answer
```

Documents were split into smaller chunks and converted into embeddings.

When a user asked a question, the question itself was converted into an embedding and compared against the vectors stored in the vector database.

The highest-ranked semantic matches were retrieved and provided to the LLM as context.

### Technologies

- LangChain
- OpenAI Embeddings
- ChromaDB
- OpenAI
- Pydantic
- Python

---

# 🚀 Phase 2 — Pro Retrieval Implementation

The baseline implementation provided a working RAG system, but retrieval quality could be improved.

Instead of treating the first retrieved results as the final context, the retrieval pipeline was redesigned to introduce additional stages.

The improved architecture became:

```text
                         User Question
                              │
                              ▼
                       Query Rewriting
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
         Original Query              Rewritten Query
                │                           │
                ▼                           ▼
        Vector Retrieval            Vector Retrieval
                │                           │
                └─────────────┬─────────────┘
                              ▼
                       Chunk Merging
                              │
                              ▼
                       LLM Reranking
                              │
                              ▼
                         Final Top-K
                              │
                              ▼
                      Context Assembly
                              │
                              ▼
                      Answer Generation
```

This allowed retrieval and ranking to be treated as separate stages.

---

# 🔄 Query Rewriting

A user's original question is not always the best possible search query.

The system therefore uses an LLM to rewrite the question into a shorter and more retrieval-oriented query.

For example:

```text
User Question
      ↓
"Who went to Manchester University?"
      ↓
Query Rewriter
      ↓
"Which Insurellm employees attended Manchester University?"
```

The rewritten query can surface information that may not be retrieved effectively using the original conversational wording.

The rewritten query is then embedded and used for a second semantic search.

---

# 🔍 Multi-Query Retrieval

The optimized pipeline retrieves context using both:

```text
Original Question
       +
Rewritten Question
```

The results from both searches are then combined.

This increases the opportunity for relevant information to enter the candidate set before reranking.

The system therefore separates:

```text
Retrieval
   ↓
Candidate Generation
   ↓
Ranking
```

rather than assuming that the initial vector-search ranking is the final ranking.

---

# 🧩 Chunk Merging

Results from multiple retrieval queries can overlap.

The pipeline therefore merges the retrieved chunks while avoiding duplicate content.

Conceptually:

```text
Original Query Results
        +
Rewritten Query Results
        ↓
     Merge
        ↓
Unique Candidate Chunks
```

This produces a larger candidate set for the reranking stage.

---

# 🏆 LLM-Based Reranking

Vector similarity provides an initial ranking of candidate chunks.

However, semantic similarity does not necessarily mean that a chunk is the **most useful chunk for answering the actual question**.

The optimized implementation therefore performs a second ranking stage.

```text
Vector Search
     ↓
Candidate Chunks
     ↓
LLM Reranker
     ↓
Most Relevant Chunks
```

The reranker receives the question and candidate chunks and returns their relevance order.

The ranking is represented using a structured Pydantic model:

```text
RankOrder
    ↓
order: list[int]
```

This ensures that the LLM produces a predictable structure containing the ranked chunk IDs.

The final ranked chunks are then used to construct the context supplied to the answer-generation model.

---

# 🧱 RAG Ingestion Pipeline

The ingestion process converts the knowledge base into searchable vectors.

```text
Knowledge Base
      ↓
Document Loading
      ↓
Text Splitting
      ↓
Chunks
      ↓
Embedding Model
      ↓
Embeddings
      ↓
Vector Database
```

Each chunk is represented conceptually as:

```text
Chunk
├── Text
├── Embedding
└── Metadata
```

The embedding represents the semantic meaning of the chunk as a vector.

The metadata preserves information such as the source document.

---

# 🔎 Query Retrieval

When a user asks a question, the query goes through a similar embedding process.

```text
User Question
      ↓
Embedding Model
      ↓
Query Vector
      ↓
ChromaDB
      ↓
Semantic Similarity Search
      ↓
Top-K Candidate Chunks
```

The vector database performs the similarity search.

The application specifies how many candidates it wants to retrieve through the retrieval parameter:

```text
RETRIEVAL_K
```

The database performs the vector similarity computation and returns the most semantically similar chunks.

---

# 🧠 Why Retrieval Quality Matters

A RAG system is only as useful as the context it retrieves.

Even if the LLM itself is highly capable, it cannot reliably answer a question from information that was never provided to it.

This creates an important separation:

```text
Retrieval Quality
       ↓
Quality of Context
       ↓
Quality of Generation
       ↓
Final Answer
```

Therefore, improving the retriever can directly improve the quality of the final answer without changing the underlying language model.

---

# 📊 RAG Evaluation

A major part of the project was moving from subjective testing to **quantitative evaluation**.

The system was evaluated across **150 test cases** covering multiple types of questions.

The evaluation considered both retrieval quality and final answer quality.

## Retrieval Metrics

### Mean Reciprocal Rank — MRR

MRR measures how highly the first relevant result appears in the ranked retrieval results.

This is particularly useful for RAG because retrieving the relevant information near the top of the context ranking is important.

Conceptually:

```text
Relevant Result at Rank 1
        ↓
Higher MRR

Relevant Result at Rank 5
        ↓
Lower MRR
```

### Normalized Discounted Cumulative Gain — nDCG

nDCG evaluates the quality of the overall ranked list rather than focusing only on the first relevant result.

This makes it useful for measuring whether the retrieval system is producing a high-quality ordering of relevant and less-relevant chunks.

Conceptually:

```text
MRR
 ↓
How quickly do we find a relevant result?

nDCG
 ↓
How good is the overall ranking?
```

Together, these metrics provide complementary information about retrieval quality.

---

# 📈 Measured Improvement

The optimized retrieval pipeline produced measurable improvements over the baseline.

| Metric | Baseline | Improved | Improvement |
|---|---:|---:|---:|
| MRR | 0.7903 | 0.9116 | ~15% |
| nDCG | 0.7919 | 0.9025 | ~14% |
| Keyword Coverage | 92.8% | 96.0% | Improved |

The results demonstrated that the additional retrieval and reranking stages were not simply increasing system complexity — they were producing measurable improvements in retrieval quality.

---

# 🧪 Evaluation-Driven Development

One of the key principles demonstrated by this project is:

```text
Build
  ↓
Evaluate
  ↓
Identify Bottleneck
  ↓
Modify Architecture
  ↓
Evaluate Again
  ↓
Measure Improvement
```

Instead of assuming that a more complicated RAG pipeline is automatically better, the system was evaluated before and after the architectural changes.

This makes retrieval optimization an empirical engineering process rather than a collection of arbitrary techniques.

---

# 🔬 Evaluation Dimensions

The evaluation process considered multiple dimensions of system performance.

### Retrieval

- MRR
- nDCG
- Keyword Coverage

### Generated Answer

- Accuracy
- Completeness
- Relevance

This distinction is important because a system can retrieve good context but still generate a poor answer, or generate a plausible answer despite retrieving weak context.

Separating these dimensions makes it easier to identify where the actual bottleneck exists.

---

# 🏗️ Implementation Evolution

The project also represents an evolution in how the system itself was designed.

## Initial Implementation

The initial implementation relied heavily on **LangChain abstractions** for document loading, splitting, embeddings, and vector-store operations.

This was useful for quickly constructing the baseline system and understanding the complete RAG workflow.

```text
LangChain
    ↓
Document Processing
    ↓
Embeddings
    ↓
Vector Store
    ↓
Retrieval
    ↓
LLM
```

## Pro Implementation

The optimized implementation moved more of the retrieval and response pipeline into explicit components using:

- Pydantic
- LiteLLM
- ChromaDB
- OpenAI Embeddings
- Custom retrieval logic
- Custom reranking logic

This provided more explicit control over the individual stages of the pipeline.

The goal was not to avoid frameworks, but to better understand and control the underlying architecture.

---

# 🤖 Answer Generation

After retrieval and reranking, the final chunks are assembled into the context supplied to the LLM.

Conceptually:

```text
Question
   +
Retrieved Context
   ↓
System Prompt
   +
Conversation History
   +
Current Question
   ↓
LLM
   ↓
Final Answer
```

The context also contains the source associated with each chunk so that the model has information about where the retrieved content originated.

---

# 💬 Conversation History

The RAG system also accounts for conversation history.

Instead of treating every question as an isolated query, the previous conversation can be passed to the query-rewriting and answer-generation stages.

This allows conversational questions to be interpreted using the context of the ongoing interaction.

For example:

```text
User:
"Who went to Manchester University?"

Assistant:
...

User:
"What was their role?"
```

The second question can be interpreted using the previous conversation rather than being treated as a completely independent query.

---

# 🖥️ Application Interface

The project also includes a Gradio interface for interacting with the RAG system.

The interface exposes:

```text
┌───────────────────────┬─────────────────────────┐
│                       │                         │
│     Conversation      │    Retrieved Context   │
│                       │                         │
│  User Question        │    Source: ...         │
│          ↓            │    Relevant Chunk ...  │
│     RAG Pipeline      │                         │
│          ↓            │                         │
│      Answer           │                         │
│                       │                         │
└───────────────────────┴─────────────────────────┘
```

The retrieved context is displayed alongside the generated answer, making the retrieval stage observable rather than hidden behind the final response.

---

# 🤗 Open-Source Models & Hugging Face

The repository also contains experiments with open-source models and the Hugging Face ecosystem.

Areas explored include:

- Transformers
- Tokenizers
- Model loading
- Text generation
- Embeddings
- Local inference
- Model configuration
- Quantization concepts

This provided experience beyond hosted APIs and helped build an understanding of how models are actually loaded and executed.

---

# 🤖 Agentic AI

Beyond RAG, the repository explores the concepts required to build agentic systems.

These include:

- Tool Calling
- Structured Outputs
- Agent State
- Multi-step workflows
- OpenAI Agents SDK
- CrewAI
- LangGraph
- AutoGen
- MCP

The goal is to understand how an LLM can move beyond generating text and instead interact with external tools and systems.

A simplified agent architecture is:

```text
User
 ↓
Agent
 ↓
Reason / Decide
 ↓
Tool Selection
 ↓
External System
 ↓
Tool Result
 ↓
Agent
 ↓
Final Response
```

---

# 🔧 Structured Outputs

Structured outputs are used throughout the repository to make model responses more predictable and machine-readable.

Rather than relying on free-form text, a model can be constrained to return a defined schema.

For example:

```text
LLM
 ↓
Structured Response
 ↓
Pydantic Model
 ↓
Validated Python Object
```

This becomes particularly useful in agentic workflows and the RAG reranking pipeline.

---

# 🧰 Tool Calling

Tool calling allows an LLM to interact with external functionality.

The general workflow explored in the repository is:

```text
User Request
      ↓
LLM
      ↓
Tool Selection
      ↓
Tool Execution
      ↓
Tool Result
      ↓
LLM
      ↓
Final Response
```

This is a core building block for agentic AI systems.

---

# 🌐 MCP

The repository also explores the **Model Context Protocol (MCP)** and the idea of exposing tools and external capabilities through a standardized interface.

Conceptually:

```text
LLM / Agent
      ↓
MCP Client
      ↓
MCP Server
      ↓
Tools / External Systems
```

This allows AI systems to interact with external resources without tightly coupling every integration directly into the model logic.

---

# 🛠️ Technology Stack

## Programming

- Python

## LLMs & APIs

- OpenAI API
- LiteLLM
- Open-source LLMs

## AI / LLM Frameworks

- LangChain
- Pydantic
- Hugging Face Transformers

## Retrieval

- ChromaDB
- Embeddings
- Semantic Search
- Retrieval-Augmented Generation
- Query Rewriting
- Multi-Query Retrieval
- Reranking
- MRR
- nDCG

## Agentic AI

- OpenAI Agents SDK
- CrewAI
- LangGraph
- AutoGen
- MCP

## Interface

- Gradio

## Development

- Jupyter
- Git
- GitHub
- uv

---

# 📁 Repository Structure

```text
LLM-Engineering/
│
├── Week1/
│
├── Week2/
│
├── Week3HuggingFace/
│
├── Week4/
│
├── Week5_RAG/
│   │
│   ├── evaluation/
│   │
│   ├── implementation/
│   │   ├── answer.py
│   │   └── ingest.py
│   │
│   ├── pro_implementation/
│   │   ├── proAnswer.py
│   │   └── proIngest.py
│   │
│   ├── knowledge-base/
│   │
│   ├── vector_db/
│   │
│   ├── app.py
│   └── evaluator.py
│
└── WritingNeuralNetworks/
```

---

# ⚙️ Setup

Clone the repository:

```bash
git clone https://github.com/Tarkshya-26/LLM-Engineering.git
cd LLM-Engineering
```

Install dependencies using `uv`:

```bash
uv sync
```

Create a `.env` file:

```env
OPENAI_API_KEY=your_key
HF_TOKEN=your_token
```

Run the required script or notebook from its respective directory.

For example:

```bash
uv run python Week5_RAG/app.py
```

---

# 🎯 Engineering Philosophy

The main objective of this repository is to move beyond simply **using LLMs** and toward understanding how to **engineer reliable LLM systems**.

The progression can be summarized as:

```text
Use the Model
      ↓
Understand the Model
      ↓
Build Around the Model
      ↓
Evaluate the System
      ↓
Identify Failure Modes
      ↓
Improve the Architecture
      ↓
Measure the Improvement
```

The RAG project is a concrete example of this approach.

Rather than treating retrieval as a single database call, the system was progressively decomposed into:

```text
Query Understanding
        +
Retrieval
        +
Candidate Generation
        +
Reranking
        +
Context Construction
        +
Generation
        +
Evaluation
```

This separation makes it possible to understand where a system succeeds, where it fails, and which component is responsible for the observed behavior.

---

# 📌 Key Learnings

Through the work in this repository, I have focused on understanding several principles:

### 1. LLMs are only one component of an AI system

A capable model does not automatically produce a capable application.

The surrounding system — retrieval, tools, context, validation, evaluation, and infrastructure — plays a major role.

### 2. Retrieval quality directly affects RAG quality

If the correct information is not retrieved, the generation model cannot reliably use it.

### 3. Vector similarity is not the same as relevance

Semantic similarity provides an excellent candidate-generation mechanism, but additional ranking can improve the relevance of the final context.

### 4. More complex architectures should be justified by measurement

Adding query rewriting or reranking should not be considered an improvement simply because the architecture looks more sophisticated.

The improvement should be measurable.

### 5. Evaluation should be part of the development loop

The most useful workflow is:

```text
Build → Evaluate → Diagnose → Improve → Re-evaluate
```

---

# 🚧 Current Focus

My current focus is on developing deeper expertise in:

- LLM Engineering
- Agentic AI
- Retrieval-Augmented Generation
- Information Retrieval
- RAG Evaluation
- AI Security
- Backend Systems for AI
- Production-oriented AI Systems

This repository will continue to evolve as I build and evaluate more complex AI systems.

---

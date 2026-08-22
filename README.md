# LLM Engineering

A hands-on repository documenting my journey through **Large Language Model (LLM) Engineering**, with a focus on understanding, implementing, evaluating, and improving modern LLM systems.

This repository contains experiments, implementations, notebooks, and projects covering the LLM application stack — from working with foundation models and open-source models to **RAG, information retrieval, evaluation, structured outputs, tool calling, and agentic AI**.

The emphasis throughout the repository is on understanding **how these systems work internally**, rather than treating LLM APIs as black boxes.

---

# 🧠 What This Repository Covers

The repository explores the following areas of LLM Engineering:

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

Each section contains implementations and experiments corresponding to the concepts studied during that stage.

The progression broadly follows:

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
🔎 Featured Project — RAG Evaluation & Optimization

One of the major projects in this repository is an evaluation-driven Retrieval-Augmented Generation system built around an Insurellm knowledge base.

The objective was not simply to build a RAG chatbot, but to understand the individual components of a retrieval pipeline and determine whether changes to the retrieval architecture actually improved performance.

The project evolved through two implementations.

Phase 1 — Baseline RAG Implementation

The first implementation used LangChain to construct the basic RAG pipeline.

The initial architecture consisted of:

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

Documents were split into smaller chunks and converted into embeddings.

When a user asked a question, the question itself was converted into an embedding and compared against the vectors stored in the vector database.

The highest-ranked semantic matches were retrieved and provided to the LLM as context.

Technologies
LangChain
OpenAI Embeddings
ChromaDB
OpenAI
Pydantic
Python
🚀 Phase 2 — Retrieval Optimization

The baseline implementation provided a working RAG system, but retrieval quality could be improved.

Instead of treating the first retrieved results as the final context, the retrieval pipeline was redesigned to introduce additional stages.

The improved architecture became:

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

This allowed retrieval and ranking to be treated as separate stages.

🔄 Query Rewriting

A user's original question is not always the best possible search query.

The system therefore uses an LLM to rewrite the question into a shorter and more retrieval-oriented query.

For example:

User Question
      ↓
"Who went to Manchester University?"
      ↓
Query Rewriter
      ↓
"Which Insurellm employees attended Manchester University?"

The rewritten query can surface information that may not be retrieved effectively using the original conversational wording.

🔍 Multi-Query Retrieval

The optimized pipeline retrieves context using both:

Original Question
       +
Rewritten Question

The resulting chunks are then merged.

This increases the opportunity for relevant information to enter the candidate set before reranking.

🧩 Chunk Merging

Results from multiple retrieval queries can overlap.

The pipeline therefore merges the retrieved chunks while avoiding duplicate content.

The goal is to construct a larger candidate set while preserving unique information for the reranking stage.

🏆 LLM-Based Reranking

Vector similarity provides an initial ranking of candidate chunks.

However, semantic similarity does not necessarily mean that a chunk is the most useful chunk for answering the actual question.

The optimized implementation therefore performs a second ranking stage.

Vector Search
     ↓
Candidate Chunks
     ↓
LLM Reranker
     ↓
Most Relevant Chunks

The reranker receives the question and candidate chunks and returns their relevance order.

Structured output is validated using Pydantic, ensuring that the model returns the expected ranking structure.

📊 RAG Evaluation

A major part of the project was moving from subjective testing to quantitative evaluation.

The system was evaluated across 150 test cases covering different types of questions.

The evaluation considered both retrieval quality and final answer quality.

Retrieval Metrics
Mean Reciprocal Rank — MRR

MRR measures how highly the first relevant result appears in the ranked retrieval results.

This is particularly useful for RAG because retrieving the relevant information near the top of the context ranking is important.

Normalized Discounted Cumulative Gain — nDCG

nDCG evaluates the quality of the overall ranked list rather than focusing only on the first relevant result.

This makes it useful for measuring whether the retrieval system is producing a high-quality ordering of relevant and less-relevant chunks.

Together:

MRR
 ↓
How quickly do we find a relevant result?

nDCG
 ↓
How good is the overall ranking?
📈 Measured Improvement

The optimized retrieval pipeline produced measurable improvements over the baseline.

Metric	Baseline	Improved	Improvement
MRR	0.7903	0.9116	~15%
nDCG	0.7919	0.9025	~14%
Keyword Coverage	92.8%	96.0%	Improved

The results demonstrated that the additional retrieval and reranking stages were not simply increasing system complexity — they were producing measurable improvements in retrieval quality.

🧪 Evaluation-Driven Development

One of the key principles demonstrated by this project is:

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

Instead of assuming that a more complicated RAG pipeline is automatically better, the system was evaluated before and after the architectural changes.

This makes retrieval optimization an empirical engineering process rather than a collection of arbitrary techniques.

🏗️ Implementation Evolution

The project also represents an evolution in how the system itself was designed.

Initial Implementation

The initial implementation relied heavily on LangChain abstractions for document loading, splitting, embeddings, and vector-store operations.

This was useful for quickly constructing the baseline system and understanding the RAG workflow.

Improved Implementation

The optimized implementation moved more of the retrieval and response pipeline into explicit components using:

Pydantic
LiteLLM
ChromaDB
OpenAI Embeddings
Custom retrieval logic
Custom reranking logic

This provided more explicit control over the individual stages of the pipeline.

The purpose was not to avoid frameworks, but to better understand and control the underlying architecture.

🧱 Core RAG Architecture

At a conceptual level, the complete system can be viewed as two separate pipelines.

Ingestion Pipeline
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
Vectors + Metadata
      ↓
Vector Database

Each chunk is represented by:

Chunk
├── Text
├── Embedding
└── Metadata

The embeddings allow semantic similarity search, while metadata preserves information such as the source document.

Query Pipeline
User Question
      ↓
Query Rewriting
      ↓
Embedding
      ↓
Vector Search
      ↓
Candidate Chunks
      ↓
Reranking
      ↓
Final Context
      ↓
LLM
      ↓
Answer

Keeping ingestion and querying conceptually separate was an important part of understanding how a RAG system works.

🤖 Agentic AI

Beyond RAG, the repository explores the concepts required to build agentic systems.

These include:

Tool Calling
Structured Outputs
Agent State
Multi-step reasoning workflows
OpenAI Agents SDK
CrewAI
LangGraph
AutoGen
MCP

The goal is to understand how an LLM can move beyond generating text and instead interact with external tools and systems.

A simplified agent architecture explored throughout the work is:

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
🤗 Open-Source Models & Hugging Face

The repository also contains experiments with open-source models and the Hugging Face ecosystem.

Areas explored include:

Transformers
Tokenizers
Model loading
Text generation
Embeddings
Local inference
Model configuration
Quantization concepts

This provided experience beyond hosted APIs and helped build an understanding of how models are actually loaded and executed.

🛠️ Technology Stack
Programming
Python
LLMs & APIs
OpenAI API
LiteLLM
Open-source LLMs
AI / LLM Frameworks
LangChain
Pydantic
Hugging Face Transformers
Retrieval
ChromaDB
Embeddings
Semantic Search
RAG
Reranking
Agentic AI
OpenAI Agents SDK
CrewAI
LangGraph
AutoGen
MCP
Interface
Gradio
Development
Jupyter
Git
GitHub
uv
📁 Repository Structure
LLM-Engineering/
│
├── Week1/
│   └── LLM Engineering fundamentals
│
├── Week2/
│   └── LLM application development
│
├── Week3HuggingFace/
│   └── Hugging Face and open-source model experiments
│
├── Week4/
│   └── Advanced LLM concepts and applications
│
├── Week5_RAG/
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
    └── Neural network implementations and experiments
⚙️ Setup

Clone the repository:

git clone https://github.com/Tarkshya-26/LLM-Engineering.git
cd LLM-Engineering

Install dependencies using uv:

uv sync

Create a .env file in the project root:

OPENAI_API_KEY=your_key
HF_TOKEN=your_token

Run the required script or notebook from its respective directory.

For example:

uv run python Week5_RAG/app.py
🎯 Engineering Philosophy

The main objective of this repository is to move beyond simply using LLMs and toward understanding how to engineer reliable LLM systems.

The progression can be summarized as:

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

The RAG project is a concrete example of this approach.

Rather than treating retrieval as a single database call, the system was progressively decomposed into:

Query Understanding
        +
Retrieval
        +
Candidate Selection
        +
Reranking
        +
Context Construction
        +
Generation
        +
Evaluation

This separation makes it possible to understand where a system succeeds, where it fails, and which component is responsible for the observed behavior.

📌 Current Focus

My current focus is on developing deeper expertise in:

LLM Engineering
Agentic AI
Retrieval-Augmented Generation
Information Retrieval
RAG Evaluation
AI Security
Backend Systems for AI
Production-oriented AI Systems

This repository will continue to evolve as I build and evaluate more complex AI systems.
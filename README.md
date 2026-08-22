# LLM Engineering

A hands-on repository documenting my journey through **LLM Engineering**, from foundational LLM applications to **RAG, retrieval evaluation, structured outputs, agentic systems, and production-oriented AI engineering**.

The goal of this repository is not just to collect code, but to understand how modern LLM systems are designed, implemented, evaluated, and improved.

---

## 🚀 What This Repository Covers

- Large Language Model fundamentals
- OpenAI API and LLM application development
- Prompt Engineering
- Structured Outputs
- Tool Calling
- Open-source LLMs
- Hugging Face Transformers
- Retrieval-Augmented Generation (RAG)
- Embeddings and Vector Databases
- Query Rewriting
- Retrieval and Reranking
- RAG Evaluation
- Agentic AI
- MCP
- LangChain
- Pydantic
- LiteLLM
- Gradio
- LLM system design and experimentation

---

# 📚 Learning Progression

The repository is organized chronologically as I progressed through different areas of LLM Engineering.

| Section | Focus |
|---|---|
| `Week1` | LLM Engineering Fundamentals |
| `week2` | LLM APIs and Application Development |
| `week3HuggingFace` | Hugging Face and Open-Source Models |
| `Week4` | Advanced LLM Application Concepts |
| `Week5_RAG` | Retrieval-Augmented Generation and Evaluation |
| `WritingNeuralNetworks` | Neural Network Implementations |

---

# 🔎 Featured Project — RAG Engineering & Evaluation

The `Week5_RAG` project goes beyond building a basic RAG chatbot.

The project started with a conventional retrieval implementation and was then redesigned to investigate and improve retrieval quality.

### RAG Pipeline

```text
                    User Question
                         │
                         ▼
                  Query Rewriting
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Original Query        Rewritten Query
              │                     │
              ▼                     ▼
        Vector Retrieval       Vector Retrieval
              │                     │
              └──────────┬──────────┘
                         ▼
                   Chunk Merging
                         │
                         ▼
                      Reranking
                         │
                         ▼
                    Top-K Context
                         │
                         ▼
                  Answer Generation
Technologies
Python
OpenAI
ChromaDB
LangChain
Pydantic
LiteLLM
Gradio
Hugging Face
Vector Embeddings
📊 Retrieval Evaluation

Rather than evaluating the RAG system only by looking at generated answers, I built an evaluation workflow to measure retrieval quality and answer quality separately.

The system was evaluated across 150 test cases covering multiple query categories.

Retrieval Metrics
Mean Reciprocal Rank (MRR)
Normalized Discounted Cumulative Gain (nDCG)
Keyword Coverage
Answer Metrics
Accuracy
Completeness
Relevance
Measured Improvement

After redesigning the retrieval pipeline:

~15% improvement in MRR
~14% improvement in nDCG

This provided measurable evidence that the redesigned retrieval and reranking pipeline was producing better-ranked context.

🧠 Retrieval Improvements

The project evolved from a simpler retrieval implementation into a more deliberate retrieval pipeline.

Initial Implementation

The initial implementation used a LangChain-based approach for document ingestion and retrieval.

Question
   ↓
Embedding Retrieval
   ↓
Retrieved Context
   ↓
LLM
   ↓
Answer
Improved Implementation

The improved implementation introduced additional retrieval and reasoning steps:

Question
   ↓
Query Rewriting
   ↓
Retrieve using Original Query
   +
Retrieve using Rewritten Query
   ↓
Merge Retrieved Chunks
   ↓
LLM-based Reranking
   ↓
Top-K Relevant Chunks
   ↓
Answer Generation

This allowed the system to improve both retrieval recall and ranking quality.

🧪 Evaluation-Driven Development

One of the main lessons from this project was the importance of measuring a RAG system instead of relying only on subjective testing.

The development process followed:

Build
  ↓
Measure
  ↓
Identify Bottleneck
  ↓
Improve
  ↓
Measure Again

MRR was used to understand how quickly relevant information appeared in the ranking, while nDCG provided a broader measure of the quality of the ranked retrieval results.

The evaluation results were then used to guide improvements to the retrieval pipeline.

🛠️ Technologies & Concepts
LLM Engineering
OpenAI APIs
Prompt Engineering
Structured Outputs
Tool Calling
Open-source LLMs
LiteLLM
RAG & Information Retrieval
Retrieval-Augmented Generation
Embeddings
Vector Search
ChromaDB
Query Rewriting
Retrieval Fusion
Reranking
MRR
nDCG
Retrieval Evaluation
Frameworks
LangChain
Pydantic
Hugging Face Transformers
Gradio
Agentic AI
OpenAI Agents SDK
CrewAI
LangGraph
AutoGen
MCP
Tool Calling
Structured Outputs
📁 Repository Structure
LLM-Engineering/
│
├── Week1/
│
├── week2/
│
├── week3HuggingFace/
│
├── Week4/
│
├── Week5_RAG/
│   │
│   ├── evaluation/
│   │   ├── eval.py
│   │   ├── test.py
│   │   └── tests.jsonl
│   │
│   ├── implementation/
│   │   ├── answer.py
│   │   └── ingest.py
│   │
│   ├── knowledge-base/
│   │
│   ├── pro_implementation/
│   │   ├── proAnswer.py
│   │   └── proIngest.py
│   │
│   ├── vector_db/
│   │
│   ├── app.py
│   ├── evaluator.py
│   └── notebooks/
│
├── WritingNeuralNetworks/
│
├── .env.example
├── .gitignore
└── README.md
💡 Key Takeaways

This repository represents my progression from simply using LLM APIs toward understanding how to engineer complete LLM systems.

The RAG project in particular helped me understand that improving an LLM application is not always about changing the model.

Often, the bigger gains come from improving the system around the model:

Better Retrieval
      +
Better Ranking
      +
Better Context
      ↓
Better LLM Answers

The most important shift has been moving from:

"Does the application work?"

to:

"How do I measure whether it works, identify where it fails, and systematically improve it?"

🎯 Current Focus

My current focus is on building deeper expertise in:

LLM Engineering
Agentic AI
Retrieval Systems
RAG Evaluation
AI Security
Backend Systems for AI
Productionizing LLM Applications

Setup

Clone the repository:

git clone https://github.com/Tarkshya-26/LLM-Engineering.git
cd LLM-Engineering

Install dependencies:

uv sync

Create a .env file:

OPENAI_API_KEY=your_key
HF_TOKEN=your_token

Run the required project or notebook from its respective directory.

Current Focus

Continuing to build deeper expertise in:

LLM Engineering
Agentic AI
RAG and Information Retrieval
RAG Evaluation
AI Security
Production-oriented AI systems
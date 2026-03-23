# 📚 Scientific Paper RAG System

A production-ready **Retrieval-Augmented Generation (RAG)** system for scientific papers. Ask questions about your research papers and get precise, cited answers powered by LLMs.

**Live Demo:** [rag-system-frontend.onrender.com](https://rag-system-frontend.onrender.com)

![RAG System Screenshot](docs/screenshot.png)

---

## ✨ Features

- **Hybrid Retrieval** – Combines vector search (ChromaDB) with keyword search (BM25) via Reciprocal Rank Fusion
- **Re-Ranking** – Cohere or local CrossEncoder for optimal result quality
- **Query Expansion** – LLM-generated alternative queries for better recall
- **Multi-LLM Support** – Switch between OpenAI, DeepSeek, Ollama with one line in `.env`
- **Local Mode** – Fully offline operation via Ollama (no data leaves your machine)
- **LaTeX Rendering** – Mathematical formulas rendered in the UI
- **Session Memory** – Conversational context across multiple questions
- **JWT Authentication** – Secure multi-user access
- **PDF Upload** – Upload and index papers via UI or API

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  React Frontend                      │
│         Chat UI │ PDF Upload │ Source Display        │
└─────────────────────┬───────────────────────────────┘
                      │ REST API (JWT)
┌─────────────────────▼───────────────────────────────┐
│                 FastAPI Backend                      │
│                                                      │
│  PDFProcessor → Chunker → Embedder → ChromaDB        │
│                                    ↓                 │
│  Query → BM25 + Vector → RRF → Reranker → LLM        │
└─────────────────────────────────────────────────────┘
```

### RAG Pipeline

```
PDF Upload
  ↓
PyMuPDF + LLM Metadata Extraction
  ↓
Recursive Section-Aware Chunking
  ↓
Embeddings (OpenAI / Ollama)
  ↓
ChromaDB + BM25 Index
  ↓
────────────────────────────────
User Question
  ↓
Query Expansion (3 alternative queries)
  ↓
Hybrid Retrieval (Vector + BM25 via RRF)
  ↓
Re-Ranking (Cohere / CrossEncoder)
  ↓
LLM Answer with Citations
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI, Python 3.12 |
| Frontend | React, TypeScript |
| Vector DB | ChromaDB |
| Keyword Search | BM25 (rank-bm25) |
| Embeddings | OpenAI / Ollama nomic-embed-text |
| Re-Ranking | Cohere / CrossEncoder (local) |
| LLM | OpenAI GPT-4o-mini / DeepSeek / Ollama |
| Auth | JWT (python-jose, bcrypt) |
| PDF Processing | PyMuPDF |
| Deployment | Docker, Render, Azure |

---

## 🚀 Quick Start

### Option A – Docker (recommended)

```bash
git clone https://github.com/chris-birdler/rag-system.git
cd rag-system

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start everything
docker compose up --build
```

Open `http://localhost` → Login with `admin` / `admin123`

### Option B – Local Development

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm start
```

---

## ⚙️ Configuration

Create a `.env` file in the root directory:

```bash
# API Keys
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...

# LLM Provider (openai / deepseek / ollama)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Embeddings (openai / ollama)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large

# Re-Ranking (cohere / local)
RERANKER=cohere

# Security
SECRET_KEY=your-secret-key-here
```

### Fully Local Stack (no internet required)

```bash
LLM_PROVIDER=ollama
LLM_MODEL=deepseek-r1:14b
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
RERANKER=local
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Get JWT token |
| GET | `/papers/` | List indexed papers |
| POST | `/papers/upload` | Upload and index PDF |
| POST | `/chat/ask` | Ask a question |
| GET | `/chat/history` | Get conversation history |
| DELETE | `/chat/history` | Clear history |
| GET | `/health` | System status |

**Interactive API docs:** `http://localhost:8000/docs`

---

## 🔒 Deployment Stacks

| Stack | LLM | Embeddings | Re-Ranking | Cost |
|-------|-----|-----------|------------|------|
| Cloud (best quality) | GPT-4o-mini | text-embedding-3-large | Cohere | ~$0.05/query |
| Cloud (cheapest) | DeepSeek | text-embedding-3-small | Cohere | ~$0.001/query |
| Local (private) | Ollama DeepSeek-R1 | nomic-embed-text | CrossEncoder | Free |
| Local (minimal) | Ollama Llama3.2 | nomic-embed-text | CrossEncoder | Free |

---

## 📁 Project Structure

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/        # auth, chat, papers, health
│   │   ├── core/
│   │   │   ├── auth.py        # JWT authentication
│   │   │   └── config.py      # Settings via .env
│   │   └── services/
│   │       ├── library.py     # Main public interface
│   │       ├── rag_engine.py  # RAG pipeline
│   │       ├── chunker.py     # Text chunking strategies
│   │       ├── embedder.py    # Multi-provider embeddings
│   │       ├── reranker.py    # Cloud + local re-ranking
│   │       ├── llm.py         # Multi-provider LLM
│   │       ├── session_store.py # Conversation memory
│   │       └── query_expander.py # Query expansion
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/        # Login, Chat, PaperList, Main
│       └── api/client.ts      # API layer
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🎓 Background

Built as part of a structured AI/ML learning plan to transition from computational physics research into AI Engineering. The system demonstrates production-ready RAG patterns including hybrid retrieval, re-ranking, and multi-provider LLM support.

**Author:** Christoph Vogler | Vienna, Austria  
**Stack:** Python · FastAPI · React · TypeScript · Docker · ChromaDB · OpenAI

---

## 📄 License

MIT License – feel free to use and modify.

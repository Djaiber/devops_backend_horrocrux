# 🧙‍♂️ Horrocruxes — Backend

Harry Potter themed chat API. Multi-agent system that routes user messages, calls a RAG Lambda, and responds in character voice powered by Google Gemini.

---

## ✨ Features

* 🤖 **Multi-Agent Chat** — semantic router that classifies each message as smalltalk, conversation, or RAG query, then builds a response in the voice of the selected HP character
* 📚 **RAG Integration** — proxies a RAG Lambda trained on the HP books, with query rewriting and citation extraction (book + chapter references)
* 👥 **8 HP Characters** — Dumbledore, Hermione, Ron, Snape, Luna, Harry, Hagrid, and Voldemort, each with unique system prompt and persona
* 💬 **Persistent Chat History** — conversations stored per user in PostgreSQL, with configurable message limit
* 🔐 **Authentication** — JWT validation via AWS Cognito
* 📖 **Auto API Docs** — Swagger UI and ReDoc out of the box

---

## 🛠 Tech Stack

* Python 3.10
* FastAPI 0.136 + Uvicorn
* SQLAlchemy 2.x (async) + asyncpg + PostgreSQL (AWS RDS)
* LangChain + Google Generative AI (gemini-2.5-flash-lite)
* AWS Cognito (authentication)
* AWS Lambda (RAG upstream)
* AWS S3 (character icons)

---

## 🚀 Getting Started

```bash
python3.10 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Fill in your credentials in .env

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API will be available at:

```
http://localhost:8000
```

Interactive docs at:

```
http://localhost:8000/docs
```

---

## 🔐 Environment Configuration

Edit:

```bash
.env
```

Example:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/harrypotter_db

# RAG Lambda
LAMBDA_URL=https://your-lambda-url.amazonaws.com/
LAMBDA_API_KEY=your-lambda-api-key

# Google Generative AI (Gemini)
GOOGLE_API_KEY=your-google-api-key

# AWS Cognito
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=your-client-id

# Optional
CORS_ORIGINS=http://localhost:4200,http://localhost:3000
DEFAULT_USER_ID=default-user
HISTORY_LIMIT=10
CHARACTERS_S3_BASE_URL=https://chars-hp-epam.s3.us-east-1.amazonaws.com
```

---

## 🔁 Agent Architecture

Each incoming message goes through a multi-step pipeline:

```
User Message
    ↓
Router Agent — classifies the query
    ├─ smalltalk  → Persona LLM responds in character voice
    ├─ conversation → LLM answers from chat history
    └─ rag →
            ├ Query Rewriting   (adapts query with character context)
            ├ RAG Lambda Call   (retrieves HP book data)
            ├ Character Answer  (LLM reformulates in character voice)
            └ Citation Extraction (book + chapter references)
```

A single shared Gemini LLM instance is used for all characters. Each character's personality is applied dynamically via system prompts.

---

## 📡 Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/chat/message` | Send a message to an HP character |
| GET | `/chat/{chat_id}/history` | Get full chat history |
| GET | `/characters` | List all available characters |
| POST | `/quiz/analyze` | Analyze quiz answers to match a character |
| POST | `/api/demo/query` | Direct RAG query (demo) |

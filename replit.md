# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## HORROCRUXES Backend (Python / FastAPI)

A standalone Python FastAPI chat backend at the repo root with persistent
storage. It proxies an external Lambda RAG API and stores conversations in
Postgres. Independent from the pnpm workspace artifacts.

- **Stack**: Python 3.12, FastAPI, Uvicorn, httpx, SQLAlchemy (async) + asyncpg, pydantic-settings
- **Run command**: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **Workflow**: `artifacts/api-server: HORROCRUXES Backend`
- **Endpoints**:
  - `GET /health`
  - `POST /chat/message` — send a user message, persist user + assistant turns, return both
  - `GET /chat/{chat_id}/history` — list messages for a chat in chronological order
  - `POST /api/demo/query` — legacy direct Lambda proxy
  - Interactive docs at `/docs`
- **Required env**: `LAMBDA_URL`, `LAMBDA_API_KEY`, `DATABASE_URL` (auto-set by Replit DB), `CORS_ORIGINS` (optional)
- **Layout**:
  - `app/main.py` — FastAPI app, lifespan that creates DB tables, router mounting, legacy demo endpoint
  - `app/core/config.py` — pydantic-settings (env vars)
  - `app/core/db/models.py` — `User`, `Chat`, `Message` SQLAlchemy models
  - `app/core/db/session.py` — async engine, session factory, `init_db()`, `get_db()` dependency (handles Replit's `?sslmode=require` for asyncpg)
  - `app/repositories/chat_repository.py` — `ensure_user`, `get_chat`, `create_chat`, `get_or_create_chat`
  - `app/repositories/message_repository.py` — `add_message`, `list_recent_messages`, `list_messages_for_chat`
  - `app/services/lambda_service.py` — `call_rag_lambda` (httpx async, safe structured logging, no leaked secrets)
  - `app/services/router_agent.py` — rules-based routing (`smalltalk` vs `rag`), accepts history, no LLM
  - `app/services/chat_service.py` — orchestrates persist user msg → fetch last N → route_agent → persist assistant reply
  - `app/routers/chat.py` — `/chat/message` and `/chat/{chat_id}/history`
  - `app/schemas/chat.py` — `MessageIn`, `MessageOut`, `ChatTurnResponse`, `ChatHistoryResponse`
  - `requirements.txt`, `.env.example`
- **DB schema** is auto-created via `Base.metadata.create_all` in the FastAPI lifespan startup hook (no Alembic).
- **No auth yet**: messages are attributed to `settings.DEFAULT_USER_ID` (`"default-user"`) when `user_id` is omitted.

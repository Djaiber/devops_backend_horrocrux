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

## HORROCRUXES Backend Preview (Python / FastAPI)

A standalone Python FastAPI service at the repo root acts as a proxy/facade for an
external Lambda RAG API. It is independent from the pnpm workspace artifacts.

- **Stack**: Python 3.12, FastAPI, Uvicorn, httpx, pydantic-settings, python-dotenv
- **Run command**: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **Workflow**: `HORROCRUXES Backend`
- **Endpoints**: `GET /health`, `POST /api/demo/query`, interactive docs at `/docs`
- **Required env**: `LAMBDA_URL`, `LAMBDA_API_KEY`, `CORS_ORIGINS` (see `.env.example`)
- **Layout**: `app/main.py`, `app/core/config.py`, `app/services/lambda_service.py`, `requirements.txt`

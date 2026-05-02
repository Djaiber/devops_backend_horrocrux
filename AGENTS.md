# HORROCRUXES Agent Guide

## Project purpose
FastAPI backend for HORROCRUXES: Harry Potter multi-agent chat + RAG Lambda integration with PostgreSQL persistence.

## Non-negotiable architecture rules
- Keep changes incremental; do not rebuild the backend.
- Keep existing endpoints intact.
- Keep Lambda integration centralized in `app/services/lambda_service.py`.
- Keep PostgreSQL persistence via repository/service layers.
- Protected chat endpoints must use authenticated **local `User.id`** (not `DEFAULT_USER_ID`, not raw Cognito `sub`).
- Never log secrets, auth tokens, API keys, or Authorization headers.

## Commands
- Run app: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- Run tests: `pytest -q`
- Syntax/import check: `python -m compileall app tests`

## DB deployment note (existing databases)
If your DB was created before local `User.id` + `cognito_sub` mapping, apply non-destructive SQL in dev/staging before rollout:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS cognito_sub VARCHAR(128);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(256);
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(128);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cognito_sub ON users (cognito_sub);
```

If `users.id` and `chats.user_id` are still text-based in an existing environment, perform an explicit staged migration plan (backfill new integer key + remap FK) before switching app code; do not drop tables.

from typing import Any, Dict

import httpx

from app.core.config import settings


class LambdaServiceError(Exception):
    """Raised when the upstream RAG Lambda call fails."""


async def call_rag_lambda(query: str, timeout: float = 60.0) -> Dict[str, Any]:
    if not settings.LAMBDA_URL:
        raise LambdaServiceError("LAMBDA_URL is not configured")
    if not settings.LAMBDA_API_KEY:
        raise LambdaServiceError("LAMBDA_API_KEY is not configured")

    headers = {
        "X-API-Key": settings.LAMBDA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"query": query}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.LAMBDA_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise LambdaServiceError(
            f"upstream returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.RequestError as exc:
        kind = type(exc).__name__
        detail = str(exc) or repr(exc)
        raise LambdaServiceError(f"request failed ({kind}): {detail}") from exc
    except ValueError as exc:
        raise LambdaServiceError(f"invalid JSON response: {exc}") from exc

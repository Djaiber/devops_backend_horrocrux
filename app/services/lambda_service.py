import logging
import time
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LambdaServiceError(Exception):
    """Raised when the upstream RAG Lambda call fails."""


def _safe_url(url: str) -> str:
    """Return a redacted URL containing only scheme + host (no path, no query)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "unknown-host"
        scheme = parsed.scheme or "https"
        return f"{scheme}://{host}"
    except Exception:
        return "invalid-url"


async def call_rag_lambda(query: str, timeout: float = 60.0) -> Dict[str, Any]:
    if not settings.LAMBDA_URL:
        raise LambdaServiceError("LAMBDA_URL is not configured")
    if not settings.LAMBDA_API_KEY:
        raise LambdaServiceError("LAMBDA_API_KEY is not configured")

    safe_url = _safe_url(settings.LAMBDA_URL)
    api_key_len = len(settings.LAMBDA_API_KEY)
    query_len = len(query)

    logger.info(
        "RAG Lambda call starting host=%s api_key_length=%d query_length=%d timeout_s=%.1f",
        safe_url,
        api_key_len,
        query_len,
        timeout,
        extra={
            "lambda_host": safe_url,
            "api_key_length": api_key_len,
            "query_length": query_len,
            "timeout_seconds": timeout,
        },
    )

    headers = {
        "X-API-Key": settings.LAMBDA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"query": query}

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.LAMBDA_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        elapsed = time.monotonic() - started
        logger.warning(
            "RAG Lambda non-2xx host=%s status=%d elapsed_s=%.3f",
            safe_url,
            exc.response.status_code,
            elapsed,
            extra={
                "lambda_host": safe_url,
                "status_code": exc.response.status_code,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        raise LambdaServiceError(
            f"upstream returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.RequestError as exc:
        elapsed = time.monotonic() - started
        kind = type(exc).__name__
        detail = str(exc) or repr(exc)
        logger.warning(
            "RAG Lambda request failed host=%s error_type=%s elapsed_s=%.3f",
            safe_url,
            kind,
            elapsed,
            extra={
                "lambda_host": safe_url,
                "error_type": kind,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        raise LambdaServiceError(f"request failed ({kind}): {detail}") from exc
    except ValueError as exc:
        elapsed = time.monotonic() - started
        logger.warning(
            "RAG Lambda invalid JSON host=%s elapsed_s=%.3f",
            safe_url,
            elapsed,
            extra={
                "lambda_host": safe_url,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        raise LambdaServiceError(f"invalid JSON response: {exc}") from exc

    elapsed = time.monotonic() - started
    logger.info(
        "RAG Lambda call succeeded host=%s elapsed_s=%.3f",
        safe_url,
        elapsed,
        extra={
            "lambda_host": safe_url,
            "elapsed_seconds": round(elapsed, 3),
        },
    )
    return data

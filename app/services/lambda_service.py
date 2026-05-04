import logging
import time
from typing import Any, Dict
from urllib.parse import urlparse

import boto3
import httpx
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

_secrets_cache: Dict[str, Any] = {"value": None, "expires_at": 0.0}


def _get_lambda_api_key() -> str:
    """Fetch LAMBDA_API_KEY from AWS Secrets Manager with 5-minute cache."""
    import time

    now = time.time()
    if _secrets_cache["value"] is not None and now < _secrets_cache["expires_at"]:
        return _secrets_cache["value"]

    secret_arn = "arn:aws:secretsmanager:us-east-1:878581768959:secret:LAMBDA_API_KEY-8x9kra"

    try:
        client = boto3.client("secretsmanager", region_name="us-east-1")
        response = client.get_secret_value(SecretId=secret_arn)
        secret = response.get("SecretString") or ""

        # Secrets Manager puede devolver JSON {"LAMBDA_API_KEY": "value"} o el valor directo
        import json
        try:
            parsed = json.loads(secret)
            value = parsed.get("LAMBDA_API_KEY") or parsed.get("value") or secret
        except (json.JSONDecodeError, AttributeError):
            value = secret

        _secrets_cache["value"] = value
        _secrets_cache["expires_at"] = now + 300  # cache 5 minutos
        return value

    except ClientError as e:
        logger.error("Failed to fetch LAMBDA_API_KEY from Secrets Manager: %s", e)
        raise LambdaServiceError(f"Could not load LAMBDA_API_KEY: {e}") from e


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

    api_key = _get_lambda_api_key()

    safe_url = _safe_url(settings.LAMBDA_URL)
    query_len = len(query)

    logger.info(
        "RAG Lambda call starting host=%s query_length=%d timeout_s=%.1f",
        safe_url,
        query_len,
        timeout,
        extra={
            "lambda_host": safe_url,
            "query_length": query_len,
            "timeout_seconds": timeout,
        },
    )

    headers = {
        "X-API-Key": api_key,
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
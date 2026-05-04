import asyncio
import json
import logging
import re
import time                           # <-- added
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import boto3                          # <-- added
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------- kept all the existing code (CHARACTER_PERSONAS, etc.) ----------

# ---------- new secret resolution helper ----------
_secrets_cache: Dict[str, Any] = {}

def _resolve_secret(arn: str) -> str:
    """Fetch a secret from AWS Secrets Manager with 5‑minute cache."""
    now = time.time()
    cached = _secrets_cache.get(arn)
    if cached and now < cached.get("expires_at", 0):
        return cached["value"]

    try:
        client = boto3.client("secretsmanager", region_name="us-east-1")
        response = client.get_secret_value(SecretId=arn)
        secret = response.get("SecretString") or ""
        # Try to decode JSON, fallback to raw secret
        try:
            parsed = json.loads(secret)
            value = parsed.get("GOOGLE_API_KEY") or parsed.get("GEMINI_API_KEY") or parsed.get("value") or secret
        except (json.JSONDecodeError, AttributeError):
            value = secret

        _secrets_cache[arn] = {
            "value": value,
            "expires_at": now + 300,  # 5 minutes
        }
        return value

    except ClientError as e:
        logger.error("Failed to fetch secret %s: %s", arn, e)
        # Re-raise as a critical error – the LLM cannot work without its key
        raise RuntimeError(f"Could not load secret {arn}: {e}") from e


# ---------- updated _get_llm ----------
_llm: Optional[ChatGoogleGenerativeAI] = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        # If the configured value is an ARN, resolve it
        api_key = settings.GOOGLE_API_KEY
        if api_key.startswith("arn:"):
            api_key = _resolve_secret(api_key)

        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.8,
        )
    return _llm
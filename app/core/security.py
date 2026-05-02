import base64
import json
import time
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import jwt as google_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.session import get_db
from app.services.auth_service import AuthenticatedUser, ensure_local_user

bearer_scheme = HTTPBearer(auto_error=False)
_jwks_cache: Dict[str, Any] = {"keys": None, "expires_at": 0.0}


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


async def _fetch_jwks() -> Dict[str, Any]:
    if _jwks_cache["keys"] is not None and time.time() < _jwks_cache["expires_at"]:
        return _jwks_cache["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.cognito_jwks_url)
        response.raise_for_status()
        keys = response.json()
    _jwks_cache["keys"] = keys
    _jwks_cache["expires_at"] = time.time() + 3600
    return keys


def _get_public_key(jwks: Dict[str, Any], kid: str) -> rsa.RSAPublicKey:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            n = int.from_bytes(_b64url_decode(key["n"]), "big")
            e = int.from_bytes(_b64url_decode(key["e"]), "big")
            return rsa.RSAPublicNumbers(e, n).public_key()
    raise HTTPException(status_code=401, detail="Invalid token")


def _validate_claims(claims: Dict[str, Any]) -> None:
    if claims.get("iss") != settings.cognito_issuer:
        raise HTTPException(status_code=401, detail="Invalid issuer")

    token_use = claims.get("token_use")
    if token_use and token_use not in {"id", "access"}:
        raise HTTPException(status_code=401, detail="Invalid token_use")

    client_id = settings.COGNITO_CLIENT_ID
    if token_use == "id":
        aud = claims.get("aud")
        if aud != client_id:
            raise HTTPException(status_code=401, detail="Invalid audience")
    elif token_use == "access":
        if claims.get("client_id") != client_id:
            raise HTTPException(status_code=401, detail="Invalid client_id")
    else:
        # fallback for tokens without token_use claim
        aud = claims.get("aud") or claims.get("client_id")
        if aud != client_id:
            raise HTTPException(status_code=401, detail="Invalid token audience")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        token = credentials.credentials
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token")

        header = json.loads(_b64url_decode(parts[0]))
        kid = header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Invalid token")

        jwks = await _fetch_jwks()
        public_key = _get_public_key(jwks, kid)
        claims = google_jwt.decode(token, certs=public_key, verify=True)

        _validate_claims(claims)

        cognito_sub = claims.get("sub")
        if not cognito_sub:
            raise HTTPException(status_code=401, detail="Invalid token claims")

        user = await ensure_local_user(
            session=session,
            cognito_sub=cognito_sub,
            email=claims.get("email"),
            username=claims.get("cognito:username") or claims.get("username"),
        )
        await session.commit()
        return user
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

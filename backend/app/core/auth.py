"""Verify the Supabase JWT sent by the frontend and expose `current_user`.

Supports both:
- new Supabase projects (asymmetric keys, ES256/RS256) -> verified with the project's JWKS
- legacy projects (HS256 shared secret)                -> verified with SUPABASE_JWT_SECRET
"""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.errors import AppError


@dataclass
class CurrentUser:
    id: str
    email: str | None = None


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str, settings: Settings) -> dict:
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise AppError(401, "UNAUTHORIZED", "HS256 token but SUPABASE_JWT_SECRET is not set")
            key = settings.supabase_jwt_secret
        else:
            key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=[alg], audience="authenticated")
    except AppError:
        raise
    except jwt.PyJWTError as e:
        raise AppError(401, "UNAUTHORIZED", f"Invalid token: {e}") from e


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "UNAUTHORIZED", "Missing Bearer token")
    
    token = authorization.split(" ", 1)[1].strip()
    
    # Demo mode: accept demo-token with a valid UUID
    if token == "demo-token":
        return CurrentUser(id="12345678-1234-1234-1234-123456789012", email="demo@streamaaathi.local")
    
    claims = decode_token(token, settings)
    sub = claims.get("sub")
    if not sub:
        raise AppError(401, "UNAUTHORIZED", "Token has no subject")
    return CurrentUser(id=sub, email=claims.get("email"))

import time

import jwt
import pytest

from app.core.auth import decode_token
from app.core.config import Settings
from app.core.errors import AppError

SECRET = "test-secret-at-least-32-characters-long!!"


def _token(**over):
    claims = {"sub": "user-1", "email": "x@y.com", "aud": "authenticated", "exp": int(time.time()) + 60}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_valid_hs256_token():
    claims = decode_token(_token(), Settings(supabase_jwt_secret=SECRET))
    assert claims["sub"] == "user-1"


def test_expired_token_rejected():
    with pytest.raises(AppError) as e:
        decode_token(_token(exp=int(time.time()) - 10), Settings(supabase_jwt_secret=SECRET))
    assert e.value.status == 401


def test_wrong_audience_rejected():
    with pytest.raises(AppError):
        decode_token(_token(aud="anon"), Settings(supabase_jwt_secret=SECRET))

"""
Telegram Mini App authentication module.

Implements two authentication methods:
1. Mini App: Validates Telegram initData using HMAC-SHA256
2. Internal API: Validates shared secret key for bot-to-backend calls
"""

import hmac
import hashlib
import time
import os
import json
import logging
from urllib.parse import parse_qs, unquote
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Header, Query

BOT_TOKEN = os.getenv("BOT_TOKEN")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
INIT_DATA_TTL = 86400  # 24 hours in seconds

# Validate required environment variables at startup
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")
if not INTERNAL_API_KEY:
    raise RuntimeError("INTERNAL_API_KEY environment variable is required")


class TelegramUser(BaseModel):
    """Parsed Telegram user from initData."""
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    auth_date: int


def validate_init_data(init_data: str) -> Optional[TelegramUser]:
    """
    Validate Telegram Mini App initData using HMAC-SHA256.

    Algorithm (from Telegram docs):
    1. Parse URL-encoded initData
    2. Extract 'hash' field
    3. Create data_check_string from remaining fields (sorted alphabetically, joined with \\n)
    4. Compute: secret_key = HMAC-SHA256("WebAppData", BOT_TOKEN)
    5. Compute: computed_hash = HMAC-SHA256(secret_key, data_check_string).hex()
    6. Compare computed_hash with received hash
    7. Check auth_date is not too old
    """
    try:
        # Parse URL-encoded data
        parsed = parse_qs(init_data, keep_blank_values=True)

        # Extract hash
        received_hash = parsed.pop('hash', [None])[0]
        if not received_hash:
            logging.warning("No hash in initData")
            return None

        # Create data_check_string: sort keys, format as key=value, join with \n
        data_check_pairs = []
        for key in sorted(parsed.keys()):
            value = parsed[key][0]
            data_check_pairs.append(f"{key}={value}")
        data_check_string = "\n".join(data_check_pairs)

        # Compute secret_key = HMAC-SHA256("WebAppData", BOT_TOKEN)
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        # Compute hash
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare hashes securely
        if not hmac.compare_digest(computed_hash, received_hash):
            logging.warning("Invalid initData hash")
            return None

        # Check auth_date
        auth_date_str = parsed.get('auth_date', [None])[0]
        if not auth_date_str:
            logging.warning("No auth_date in initData")
            return None

        auth_date = int(auth_date_str)
        if time.time() - auth_date > INIT_DATA_TTL:
            logging.warning(f"initData expired (auth_date: {auth_date})")
            return None

        # Parse user JSON
        user_json = parsed.get('user', [None])[0]
        if not user_json:
            logging.warning("No user in initData")
            return None

        user_data = json.loads(unquote(user_json))

        return TelegramUser(
            id=user_data['id'],
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            username=user_data.get('username'),
            language_code=user_data.get('language_code'),
            is_premium=user_data.get('is_premium'),
            auth_date=auth_date
        )

    except Exception as e:
        logging.error(f"Error validating initData: {e}")
        return None


async def get_telegram_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> TelegramUser:
    """
    FastAPI dependency for Mini App endpoints.
    Expects Authorization header with initData.
    Format: "tma <initData>" or just "<initData>"
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Remove "tma " prefix if present (Telegram Mini App convention)
    init_data = authorization
    if init_data.lower().startswith("tma "):
        init_data = init_data[4:]

    user = validate_init_data(init_data)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authorization"
        )

    return user


async def verify_internal_api_key(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> bool:
    """
    FastAPI dependency for Bot service endpoints.
    Expects Authorization header with Bearer token.
    Format: "Bearer <INTERNAL_API_KEY>"
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Extract token from "Bearer <token>" format
    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]

    if not hmac.compare_digest(token, INTERNAL_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return True


def _is_valid_internal_key(authorization: str) -> bool:
    """Check if authorization header contains valid INTERNAL_API_KEY."""
    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]
    return hmac.compare_digest(token, INTERNAL_API_KEY)


class AuthResult(BaseModel):
    """Result of flexible authentication."""
    telegram_id: int
    username: Optional[str] = None
    is_internal: bool = False


def _parse_authorization(
    authorization: str,
    telegram_id: Optional[int],
    telegram_username: Optional[str]
) -> AuthResult:
    """
    Internal helper to parse authorization and return AuthResult.
    Handles both Mini App (tma) and internal API key authentication.
    """
    # Try Mini App auth first (tma prefix)
    if authorization.lower().startswith("tma "):
        init_data = authorization[4:]
        user = validate_init_data(init_data)
        if user:
            return AuthResult(
                telegram_id=user.id,
                username=user.username,
                is_internal=False
            )
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired initData"
        )

    # Try internal API key auth
    if _is_valid_internal_key(authorization):
        if telegram_id is None:
            raise HTTPException(
                status_code=400,
                detail="telegram_id required for internal API calls"
            )
        return AuthResult(
            telegram_id=telegram_id,
            username=telegram_username,
            is_internal=True
        )

    # Neither auth worked
    raise HTTPException(
        status_code=401,
        detail="Invalid authorization"
    )


async def get_user_id_flexible(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    telegram_id: Optional[int] = Query(None)
) -> int:
    """
    Flexible auth dependency that accepts BOTH:
    1. Mini App: "tma <initData>" - extracts user ID from initData
    2. Bot service: "Bearer <INTERNAL_API_KEY>" + telegram_id query param

    Returns the authenticated user's telegram_id.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    result = _parse_authorization(authorization, telegram_id, None)
    return result.telegram_id


async def get_auth_flexible(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    telegram_id: Optional[int] = Query(None),
    telegram_username: Optional[str] = Query(None)
) -> AuthResult:
    """
    Flexible auth that returns full auth info.
    For endpoints that need user info from either source.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    return _parse_authorization(authorization, telegram_id, telegram_username)

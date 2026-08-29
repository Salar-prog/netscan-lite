import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from ldap3 import ALL, SUBTREE, Connection, Server
from pydantic import BaseModel

from netscan_lite.config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


class UserPayload(BaseModel):
    username: str
    dn: str
    groups: List[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


def _ldap_authenticate_sync(username: str, password: str) -> Optional[UserPayload]:
    """Synchronous LDAP search+bind authentication. Runs in a thread."""
    server = Server(settings.LDAP_SERVER, get_info=ALL, use_ssl=settings.LDAP_STARTTLS)

    # Step 1: Bind with service account
    admin_conn = Connection(server, user=settings.LDAP_BIND_DN, password=settings.LDAP_BIND_PASSWORD, auto_bind=True)

    try:
        # Step 2: Search for user DN
        search_filter = settings.LDAP_SEARCH_FILTER.format(username=username)
        admin_conn.search(
            search_base=settings.LDAP_SEARCH_BASE,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["cn", "mail", "memberOf"],
        )
        if not admin_conn.entries:
            logger.warning("LDAP user not found: %s", username)
            return None

        entry = admin_conn.entries[0]
        user_dn = entry.entry_dn

        # Step 3: Bind with user's credentials to verify password
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()

        # Step 4: Extract groups from memberOf
        groups: List[str] = []
        if hasattr(entry, "memberOf"):
            for dn in entry.memberOf.values:
                # Extract CN from DN (e.g., "CN=admins,DC=example,DC=com" → "admins")
                cn = dn.split(",")[0].split("=")[-1]
                groups.append(cn)

        return UserPayload(username=username, dn=user_dn, groups=groups)

    except Exception:
        logger.warning("LDAP authentication failed for: %s", username)
        return None
    finally:
        admin_conn.unbind()


async def ldap_authenticate(username: str, password: str) -> Optional[UserPayload]:
    """Async wrapper for LDAP authentication."""
    return await asyncio.to_thread(_ldap_authenticate_sync, username, password)


def create_access_token(username: str, dn: str = "", groups: Optional[List[str]] = None) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    payload = {
        "sub": username,
        "dn": dn,
        "groups": groups or [],
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPayload:
    """FastAPI dependency: validates JWT and returns the current user."""
    if not settings.LDAP_ENABLED:
        if not settings.DEV_AUTH_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dev auth disabled. Set DEV_AUTH_ENABLED=true or LDAP_ENABLED=true.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.warning("Dev auth enabled — accepting any token as valid. Do not use in production.")
        return UserPayload(username=token, dn=f"cn={token},dev", groups=["dev-admin"])

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserPayload(
        username=payload["sub"],
        dn=payload.get("dn", ""),
        groups=payload.get("groups", []),
    )

"""
app/core/security.py
─────────────────────
Clerk JWT verification for multi-tenant auth.

On every request:
  1. Extract `Authorization: Bearer <token>` header
  2. Verify JWT using Clerk's JWKS endpoint (RS256)
  3. Extract `sub` (clerk_user_id) + `email` from claims
  4. Get-or-create User row in DB
  5. Return internal user_id (DB UUID)

Security guarantees:
  - Token signature validated against Clerk's public keys
  - Token expiry enforced
  - Frontend user_id is NEVER trusted — always derived from verified token
  - User must exist/be created before any data access
"""
import httpx
from functools import lru_cache
from typing import Optional

from fastapi import Header, HTTPException, status, Depends
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── JWKS Cache ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_clerk_jwks(jwks_url: str) -> dict:
    """Fetch Clerk JWKS (cached — rotates rarely). Call invalidate_jwks_cache() to force refresh."""
    try:
        response = httpx.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to fetch Clerk JWKS from %s: %s", jwks_url, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service temporarily unavailable. Please try again.",
        )


def invalidate_jwks_cache() -> None:
    """Call this if you rotate Clerk signing keys."""
    _get_clerk_jwks.cache_clear()


# ── Token Verification ────────────────────────────────────────────────────────

def _verify_clerk_token(token: str, jwks_url: str) -> dict:
    """
    Verify a Clerk-issued JWT.
    Returns the decoded claims dict on success.
    Raises HTTPException on any failure.
    """
    jwks = _get_clerk_jwks(jwks_url)

    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk does not set aud by default
        )
        return claims
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Main Dependency ───────────────────────────────────────────────────────────

def get_current_user_id(
    authorization: str = Header(
        None,
        alias="Authorization",
        description="Bearer <Clerk JWT token>",
    ),
    db: Session = Depends(get_db),
) -> str:
    """
    FastAPI dependency — validates Clerk JWT and returns internal user_id.

    Flow:
      Authorization: Bearer <token>
      → verify signature → extract sub + email
      → get-or-create User row
      → return user.id (UUID used as FK in all tables)
    """
    from app.core.config import get_settings
    settings = get_settings()

    # ── 1. Extract token ──────────────────────────────────────────────────────
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── 2. Verify token ───────────────────────────────────────────────────────
    jwks_url = getattr(settings, "CLERK_JWKS_URL", None)
    if not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured on server. Contact support.",
        )

    claims = _verify_clerk_token(token, jwks_url)

    clerk_user_id: Optional[str] = claims.get("sub")
    email: Optional[str] = claims.get("email") or f"{clerk_user_id}@clerk.local"
    name: str = (
        claims.get("name")
        or f"{claims.get('given_name', '')} {claims.get('family_name', '')}".strip()
        or email.split("@")[0]
    )

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim.",
        )

    # ── 3. Get-or-create User ─────────────────────────────────────────────────
    from app.models.user import User  # local import to avoid circular deps

    user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
    if not user:
        # Also check by email in case user was migrated
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Backfill clerk_user_id on existing row
            user.clerk_user_id = clerk_user_id
            db.commit()
        else:
            # Brand new user
            import uuid
            user = User(
                id=str(uuid.uuid4()),
                clerk_user_id=clerk_user_id,
                email=email,
                name=name,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Auto-provisioned new user clerk_id=%s email=%s", clerk_user_id, email)

    logger.debug("Resolved user_id=%s clerk_id=%s", user.id, clerk_user_id)
    return user.id

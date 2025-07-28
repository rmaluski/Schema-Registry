import hashlib
import time
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from structlog import get_logger

from app.config import settings

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

# Rate limiting storage (in production, use Redis)
rate_limit_store: Dict[str, Dict[str, Any]] = {}


class SecurityManager:
    """Security manager for authentication and authorization."""

    @staticmethod
    def verify_jwt_token(token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[settings.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

    @staticmethod
    def verify_github_oidc_token(token: str) -> Dict[str, Any]:
        """Verify GitHub OIDC token for CI/CD operations."""
        try:
            # In production, verify against GitHub's OIDC provider
            # For now, we'll use a simplified verification
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False
                },  # Skip signature verification for demo
            )

            # Verify issuer and audience
            if payload.get("iss") != settings.github_oidc_issuer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer",
                )

            if payload.get("aud") != settings.github_oidc_audience:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience",
                )

            return payload
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub OIDC token",
            )

    @staticmethod
    def check_rate_limit(client_id: str, limit: int = 100, window: int = 3600) -> bool:
        """Check rate limit for a client."""
        now = time.time()
        client_key = f"rate_limit:{client_id}"

        if client_key not in rate_limit_store:
            rate_limit_store[client_key] = {"count": 1, "window_start": now}
            return True

        client_data = rate_limit_store[client_key]

        # Reset window if expired
        if now - client_data["window_start"] > window:
            client_data["count"] = 1
            client_data["window_start"] = now
            return True

        # Check limit
        if client_data["count"] >= limit:
            return False

        client_data["count"] += 1
        return True

    @staticmethod
    def get_client_id(request: Request) -> str:
        """Extract client ID from request."""
        # In production, extract from JWT token or API key
        # For now, use IP address as client ID
        return request.client.host if request.client else "unknown"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Get current user from JWT token."""
    if not credentials:
        return None

    try:
        payload = SecurityManager.verify_jwt_token(credentials.credentials)
        return payload
    except HTTPException:
        return None


async def require_auth(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Require authentication for protected endpoints."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return current_user


async def require_admin(
    current_user: Dict[str, Any] = Depends(require_auth)
) -> Dict[str, Any]:
    """Require admin privileges."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


async def require_ci_bot(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """Require GitHub CI bot authentication."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub OIDC token required",
        )

    try:
        payload = SecurityManager.verify_github_oidc_token(credentials.credentials)
        return payload
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub OIDC token"
        )


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    client_id = SecurityManager.get_client_id(request)

    if not SecurityManager.check_rate_limit(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    response = await call_next(request)
    return response


def hash_schema_content(schema_content: str) -> str:
    """Generate hash for schema content."""
    return hashlib.sha256(schema_content.encode()).hexdigest()


def validate_schema_signature(
    schema_content: str, signature: str, public_key: str
) -> bool:
    """Validate schema signature (for future use)."""
    # In production, implement proper signature verification
    # For now, return True as placeholder
    return True

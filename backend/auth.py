"""Supabase authentication — verifying the caller's identity.

Supabase Auth is used here purely as an identity provider. It runs the Google
OAuth dance in the browser and issues the user a JWT; this module verifies that
JWT and extracts who the caller is. Everything else — which runs someone may
read, who owns what — is enforced in this application's own routers.

That split matters, and is worth being explicit about. The backend talks to
Postgres over SQLAlchemy as the database owner, a role that bypasses row-level
security. So RLS policies are **not** what protects a user's runs here; the
ownership checks in the routers are. RLS is still enabled on the tables, with
no policies, for a different reason: Supabase exposes every table in the
`public` schema through PostgREST, and the publishable key that reaches it is
in the frontend bundle for anyone to read. RLS with no policies is what stops
that door being open.

Verification uses the project's JWKS endpoint and asymmetric ES256 keys, so
the server holds only public key material. A leaked copy of anything this
module reads cannot be used to mint a token.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Project URL, e.g. https://your-project-ref.supabase.co — the same value
# the frontend uses. Not a secret.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")

# Supabase signs user tokens with the `authenticated` audience.
_AUDIENCE = "authenticated"

_jwks_client: Optional[PyJWKClient] = None


def auth_enabled() -> bool:
    """Whether this instance can verify tokens at all.

    With no SUPABASE_URL there is nothing to verify against, so the app runs
    open — which is what a local checkout should do. A deployment sets the
    variable and every write path starts requiring a signed-in user.
    """
    return bool(SUPABASE_URL)


def _get_jwks_client() -> PyJWKClient:
    """Lazily build the JWKS client.

    ``PyJWKClient`` caches fetched keys, so the endpoint is hit once rather
    than on every request, and again only when a token arrives with a key id
    it has not seen — which is what makes Supabase's key rotation transparent
    to us. Built lazily so importing this module never performs network I/O.
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
        )
    return _jwks_client


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _decode(token: str) -> dict:
    """Verify a Supabase access token and return its claims."""
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        audience=_AUDIENCE,
        # `iat` is not required: a client whose clock runs slightly fast would
        # otherwise have every token rejected. Expiry is still enforced.
        options={"require": ["exp", "sub"], "verify_aud": True},
    )


class AuthUser:
    """The caller's identity, as far as this application is concerned."""

    __slots__ = ("id", "email", "name", "avatar_url")

    def __init__(self, claims: dict):
        self.id: str = claims["sub"]
        metadata = claims.get("user_metadata") or {}
        self.email: Optional[str] = claims.get("email") or metadata.get("email")
        self.name: Optional[str] = (
            metadata.get("full_name") or metadata.get("name") or self.email
        )
        self.avatar_url: Optional[str] = metadata.get("avatar_url")


def optional_user(request: Request) -> Optional[AuthUser]:
    """Identify the caller if they presented a valid token, else ``None``.

    Used by read endpoints, which are reachable signed out — they simply show
    public runs instead. A malformed or expired token is treated as "signed
    out" rather than an error, so an expired session degrades to the public
    view instead of breaking the page.
    """
    if not auth_enabled():
        return None
    token = _bearer_token(request)
    if not token:
        return None
    try:
        return AuthUser(_decode(token))
    except jwt.PyJWTError as exc:
        logger.info("Ignoring unverifiable token: %s", exc)
        return None
    except Exception as exc:  # JWKS fetch failure, malformed key material
        logger.warning("Could not verify token: %s", exc)
        return None


def require_user(request: Request) -> Optional[AuthUser]:
    """Identify the caller, or reject the request.

    Used by the write paths — starting a run, cancelling or deleting one.

    An instance with no Supabase configured has no way to identify anybody, so
    it runs open and this returns ``None``. That is the local-development case:
    a fresh checkout should be able to run an analysis without first setting up
    an OAuth provider. The cost is that a deployment which forgets to set
    SUPABASE_URL is also open, so :func:`warn_if_open` says so loudly at
    startup rather than leaving it to be discovered.
    """
    if not auth_enabled():
        return None
    token = _bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with Google to start an analysis.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return AuthUser(_decode(token))
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def warn_if_open() -> None:
    """Log a warning when the instance accepts unauthenticated writes.

    Running open is correct for a local checkout and wrong for anything with a
    public URL. The distinction cannot be detected from inside the process, so
    this states the situation plainly at startup and leaves the judgement to
    whoever reads the log.
    """
    if auth_enabled():
        logger.info("Authentication enabled against %s", SUPABASE_URL)
        return
    logger.warning(
        "SUPABASE_URL is not set: authentication is disabled, so anyone who "
        "can reach this server can start runs and read every run stored. That "
        "is fine locally and not fine on a public URL."
    )


# Convenience aliases so routers read as intent rather than plumbing.
CurrentUser = Depends(require_user)
MaybeUser = Depends(optional_user)

"""Auth router — tells the browser how to sign in, and who it is signed in as.

The frontend needs the Supabase project URL and publishable key to run the
Google sign-in flow. Those are served from here rather than baked in at build
time, so the same Docker image can be pointed at a different Supabase project
by changing an environment variable instead of rebuilding.

Neither value is a secret: the publishable key is designed to ship inside a
frontend bundle, and it grants only what row-level security allows — which,
for this project's tables, is nothing (see :mod:`backend.auth`).
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import AuthUser, auth_enabled, optional_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()


class AuthConfigResponse(BaseModel):
    # False when the instance has no Supabase configured. The UI then hides
    # sign-in entirely rather than offering a button that cannot work.
    enabled: bool
    url: Optional[str] = None
    anon_key: Optional[str] = None


class AuthUserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/config", response_model=AuthConfigResponse)
def auth_config():
    """Client configuration for the sign-in flow."""
    enabled = auth_enabled() and bool(SUPABASE_ANON_KEY)
    if not enabled:
        return AuthConfigResponse(enabled=False)
    return AuthConfigResponse(
        enabled=True,
        url=SUPABASE_URL,
        anon_key=SUPABASE_ANON_KEY,
    )


@router.get("/me", response_model=Optional[AuthUserResponse])
def current_user(user: Optional[AuthUser] = Depends(optional_user)):
    """Who the bearer token belongs to, or null.

    The browser already holds the decoded session, so this exists to confirm
    the *server* accepts that token — a session that looks valid client-side
    but fails verification here would otherwise only reveal itself when a run
    was rejected.
    """
    if user is None:
        return None
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )

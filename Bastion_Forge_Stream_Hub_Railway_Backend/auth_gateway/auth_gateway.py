import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI(
    title="Bastion Forge Stream Hub Auth Gateway",
    version="0.5.0-beta.5",
)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
SESSION_TTL_SECONDS = 10 * 60


@dataclass
class OAuthSession:
    id: str
    provider: str
    state: str
    created_at: float
    verifier: str | None = None
    status: str = "pending"
    message: str = ""
    token_data: dict[str, Any] = field(default_factory=dict)


sessions: dict[str, OAuthSession] = {}


def clean_sessions() -> None:
    now = time.time()
    expired = [
        session_id
        for session_id, session in sessions.items()
        if now - session.created_at > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        sessions.pop(session_id, None)


def provider_config(provider: str) -> tuple[str, str]:
    prefix = provider.upper()
    if provider == "youtube":
        prefix = "YOUTUBE"
    client_id = os.getenv(f"{prefix}_CLIENT_ID", "").strip()
    client_secret = os.getenv(f"{prefix}_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail=f"{provider} is not configured on the Bastion Forge login service.",
        )
    return client_id, client_secret


def callback_url(provider: str) -> str:
    if not PUBLIC_BASE_URL:
        raise HTTPException(
            status_code=503,
            detail="PUBLIC_BASE_URL is not configured.",
        )
    return f"{PUBLIC_BASE_URL}/oauth/{provider}/callback"


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def make_authorize_url(session: OAuthSession) -> str:
    provider = session.provider
    client_id, _ = provider_config(provider)
    redirect_uri = callback_url(provider)

    if provider == "twitch":
        query = urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:read:chat user:write:chat moderator:read:followers channel:read:subscriptions",
            "state": session.state,
            "force_verify": "true",
        })
        return f"https://id.twitch.tv/oauth2/authorize?{query}"

    if provider == "youtube":
        query = urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
            "access_type": "offline",
            "prompt": "consent",
            "state": session.state,
        })
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    if provider == "kick":
        verifier = session.verifier
        if not verifier:
            raise RuntimeError("Kick PKCE verifier missing.")
        query = urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:read channel:read chat:write events:subscribe kicks:read",
            "state": session.state,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
        })
        return f"https://id.kick.com/oauth/authorize?{query}"

    if provider == "streamlabs":
        query = urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "socket.token donations.read alerts.write profiles.write",
            "state": session.state,
        })
        return f"https://streamlabs.com/api/v2.0/authorize?{query}"

    raise HTTPException(status_code=404, detail="Unknown provider.")


async def exchange_code(
    provider: str,
    code: str,
    session: OAuthSession,
) -> dict[str, Any]:
    client_id, client_secret = provider_config(provider)
    redirect_uri = callback_url(provider)

    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "twitch":
            response = await client.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

        elif provider == "youtube":
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

        elif provider == "kick":
            response = await client.post(
                "https://id.kick.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code_verifier": session.verifier or "",
                    "code": code,
                },
            )

        elif provider == "streamlabs":
            response = await client.post(
                "https://streamlabs.com/api/v2.0/token",
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                json={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
        else:
            raise HTTPException(status_code=404, detail="Unknown provider.")

    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(
            f"{provider} token exchange failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    data["client_id"] = client_id
    return data


async def refresh_provider(
    provider: str,
    refresh_token: str,
) -> dict[str, Any]:
    client_id, client_secret = provider_config(provider)

    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "twitch":
            response = await client.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

        elif provider == "youtube":
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

        elif provider == "kick":
            response = await client.post(
                "https://id.kick.com/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
            )

        elif provider == "streamlabs":
            response = await client.post(
                "https://streamlabs.com/api/v2.0/token",
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                json={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": callback_url(provider),
                    "refresh_token": refresh_token,
                },
            )
        else:
            raise HTTPException(status_code=404, detail="Unknown provider.")

    if response.status_code < 200 or response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"{provider} refresh failed: {response.text}",
        )

    data = response.json()
    data["client_id"] = client_id
    if not data.get("refresh_token"):
        data["refresh_token"] = refresh_token
    return data


@app.get("/health")
async def health() -> dict[str, Any]:
    clean_sessions()
    return {
        "ok": True,
        "service": "Bastion Forge Stream Hub Auth Gateway",
        "version": "0.5.0-beta.5",
        "public_base_url_configured": bool(PUBLIC_BASE_URL),
        "pending_sessions": len(sessions),
    }


@app.post("/v1/oauth/start/{provider}")
async def start_oauth(provider: str) -> dict[str, str]:
    clean_sessions()
    provider = provider.lower()
    if provider not in {"twitch", "youtube", "kick", "streamlabs"}:
        raise HTTPException(status_code=404, detail="Unknown provider.")

    provider_config(provider)

    session_id = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64) if provider == "kick" else None

    session = OAuthSession(
        id=session_id,
        provider=provider,
        state=state,
        verifier=verifier,
        created_at=time.time(),
    )
    sessions[session_id] = session

    return {
        "session_id": session_id,
        "authorize_url": make_authorize_url(session),
    }


@app.get("/oauth/{provider}/callback", response_class=HTMLResponse)
async def oauth_callback(
    provider: str,
    request: Request,
):
    clean_sessions()
    provider = provider.lower()

    code = request.query_params.get("code")
    returned_state = request.query_params.get("state")
    error = request.query_params.get("error")

    session = next(
        (
            item
            for item in sessions.values()
            if item.provider == provider and item.state == returned_state
        ),
        None,
    )

    if session is None:
        return HTMLResponse(
            "<h2>Bastion Forge Stream Hub</h2><p>Login session was not found or has expired.</p>",
            status_code=400,
        )

    if error:
        session.status = "error"
        session.message = error
        return HTMLResponse(
            "<h2>Bastion Forge Stream Hub</h2><p>Login was cancelled. You can close this window.</p>"
        )

    if not code:
        session.status = "error"
        session.message = "No authorization code was returned."
        return HTMLResponse(
            "<h2>Bastion Forge Stream Hub</h2><p>The provider did not return an authorization code.</p>",
            status_code=400,
        )

    try:
        token_data = await exchange_code(provider, code, session)
        session.token_data = token_data
        session.status = "complete"
        return HTMLResponse(
            """
            <html>
              <body style="font-family:Segoe UI,Arial;background:#0b0d12;color:white;padding:48px">
                <h2>Bastion Forge Stream Hub</h2>
                <p>Account connected successfully.</p>
                <p>You can close this browser window and return to Stream Hub.</p>
              </body>
            </html>
            """
        )
    except Exception as exc:
        session.status = "error"
        session.message = str(exc)
        return HTMLResponse(
            f"<h2>Bastion Forge Stream Hub</h2><p>Login failed: {exc}</p>",
            status_code=502,
        )


@app.get("/v1/oauth/status/{session_id}")
async def oauth_status(session_id: str) -> dict[str, Any]:
    clean_sessions()
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status == "pending":
        return {"status": "pending"}

    if session.status == "error":
        return {
            "status": "error",
            "message": session.message,
        }

    data = {
        "status": "complete",
        "access_token": session.token_data.get("access_token"),
        "refresh_token": session.token_data.get("refresh_token"),
        "client_id": session.token_data.get("client_id"),
    }

    # One-time delivery: remove the completed session after the app retrieves it.
    sessions.pop(session_id, None)
    return data


@app.post("/v1/oauth/refresh/{provider}")
async def oauth_refresh(provider: str, request: Request) -> dict[str, Any]:
    provider = provider.lower()
    if provider not in {"twitch", "youtube", "kick", "streamlabs"}:
        raise HTTPException(status_code=404, detail="Unknown provider.")

    body = await request.json()
    refresh_token = str(body.get("refresh_token", "")).strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token is required.")

    data = await refresh_provider(provider, refresh_token)
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "client_id": data.get("client_id"),
    }

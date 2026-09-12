import base64
import json
import os
import time
from collections import deque
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect

app = FastAPI(title="Bastion Forge Kick Bridge", version="0.2.0")

BRIDGE_KEY = os.getenv("BASTION_BRIDGE_KEY", "change-this-to-a-long-random-value")
VERIFY_SIGNATURES = os.getenv("BASTION_KICK_VERIFY_SIGNATURES", "1") != "0"
clients: set[WebSocket] = set()
recent_ids: deque[tuple[str, float]] = deque(maxlen=5000)
public_key_pem: bytes | None = None


async def get_kick_public_key() -> bytes:
    global public_key_pem
    if public_key_pem:
        return public_key_pem
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.kick.com/public/v1/public-key")
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data", payload)
    key = data.get("public_key") or data.get("key") if isinstance(data, dict) else data
    if not isinstance(key, str) or "BEGIN" not in key:
        raise RuntimeError("Kick public-key response did not contain a PEM key.")
    public_key_pem = key.encode("utf-8")
    return public_key_pem


def seen(message_id: str) -> bool:
    now = time.time()
    while recent_ids and now - recent_ids[0][1] > 600:
        recent_ids.popleft()
    if any(item_id == message_id for item_id, _ in recent_ids):
        return True
    recent_ids.append((message_id, now))
    return False


async def verify_signature(message_id: str, timestamp: str, signature_b64: str, raw_body: bytes) -> bool:
    if not VERIFY_SIGNATURES:
        return True
    global public_key_pem
    message = f"{message_id}.{timestamp}.".encode("utf-8") + raw_body
    signature = base64.b64decode(signature_b64)
    for attempt in range(2):
        try:
            key_pem = await get_kick_public_key()
            key = serialization.load_pem_public_key(key_pem)
            if isinstance(key, rsa.RSAPublicKey):
                key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
            elif isinstance(key, ed25519.Ed25519PublicKey):
                key.verify(signature, message)
            else:
                return False
            return True
        except Exception:
            public_key_pem = None
            if attempt == 1:
                return False
    return False


async def broadcast(payload: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    text = json.dumps(payload, separators=(",", ":"))
    for socket in list(clients):
        try:
            await socket.send_text(text)
        except Exception:
            dead.append(socket)
    for socket in dead:
        clients.discard(socket)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "Bastion Forge Kick Bridge",
        "version": "0.2.0",
        "websocket_clients": len(clients),
        "signature_verification": VERIFY_SIGNATURES,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, key: str = ""):
    if not BRIDGE_KEY or BRIDGE_KEY == "change-this-to-a-long-random-value":
        await websocket.close(code=1008, reason="Bridge key not configured")
        return
    if key != BRIDGE_KEY:
        await websocket.close(code=1008, reason="Invalid bridge key")
        return
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_json({"type": "bridge.welcome", "data": {"version": "0.2.0"}})
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)


@app.post("/kick/webhook")
async def kick_webhook(
    request: Request,
    message_id: str | None = Header(default=None, alias="Kick-Event-Message-Id"),
    timestamp: str | None = Header(default=None, alias="Kick-Event-Message-Timestamp"),
    signature: str | None = Header(default=None, alias="Kick-Event-Signature"),
    event_type: str | None = Header(default=None, alias="Kick-Event-Type"),
    event_version: str | None = Header(default=None, alias="Kick-Event-Version"),
):
    raw = await request.body()
    if not message_id or not event_type:
        raise HTTPException(status_code=400, detail="Missing Kick event headers")
    if seen(message_id):
        return {"ok": True, "duplicate": True}
    if VERIFY_SIGNATURES:
        if not timestamp or not signature:
            raise HTTPException(status_code=401, detail="Missing signature headers")
        if not await verify_signature(message_id, timestamp, signature, raw):
            raise HTTPException(status_code=401, detail="Invalid Kick signature")
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    await broadcast({
        "type": event_type,
        "version": event_version or "1",
        "id": message_id,
        "timestamp": timestamp,
        "data": data,
    })
    return {"ok": True}

"""
FastAPI sidecar — receives POST from Apex/Agentforce, stores payload in memory,
returns a short cache_id. Streamlit reads the payload back by that ID.

Endpoints
---------
POST /api/cache          { "data": [...], "config": {...} }  →  { "cache_id": "abc123", "url": "/?id=abc123" }
GET  /api/cache/{id}     →  { "data": [...], "config": {...} }
GET  /api/health         →  { "status": "ok", "entries": N }
DELETE /api/cache/{id}   →  204
"""

import time
import uuid
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

app = FastAPI(title="Streamlit Viz Cache API", docs_url="/api/docs")

# Full URL of the Streamlit app — returned in POST response so Apex can use it directly.
# Set STREAMLIT_URL env var on Render to https://vivekm2305.streamlit.app
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to your Salesforce org URL in production
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory cache  { cache_id: { payload, created_at } }
# TTL default: 30 minutes.  Increase for longer-lived sessions.
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}
TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 1800))


def _evict_expired():
    """Remove entries older than TTL."""
    now = time.time()
    expired = [k for k, v in _cache.items() if now - v["created_at"] > TTL_SECONDS]
    for k in expired:
        del _cache[k]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CachePayload(BaseModel):
    data: list[Any]
    config: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    _evict_expired()
    return {"status": "ok", "entries": len(_cache), "ttl_seconds": TTL_SECONDS}


@app.post("/api/cache", status_code=201)
def store_payload(payload: CachePayload):
    _evict_expired()
    cache_id = uuid.uuid4().hex[:8]          # e.g. "a3f7c912"
    _cache[cache_id] = {
        "payload": payload.model_dump(),
        "created_at": time.time(),
    }
    return {
        "cache_id": cache_id,
        "url": f"{STREAMLIT_URL}/?id={cache_id}",   # ready-to-use iframe URL for Apex/LWC
        "expires_in_seconds": TTL_SECONDS,
    }


@app.get("/api/cache/{cache_id}")
def get_payload(cache_id: str):
    _evict_expired()
    entry = _cache.get(cache_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"cache_id '{cache_id}' not found or expired")
    return entry["payload"]


@app.delete("/api/cache/{cache_id}", status_code=204)
def delete_payload(cache_id: str):
    _cache.pop(cache_id, None)

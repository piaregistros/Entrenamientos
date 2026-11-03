from __future__ import annotations

import time
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.auth import CSRF_COOKIE_NAME, validate_csrf_token
from app.coach_routes import init_coach_db, router as coach_router

app = FastAPI(title="Entrenamientos Coach", version="1.0.0")
app.include_router(coach_router)
_buckets = defaultdict(deque)

@app.middleware("http")
async def security(request: Request, call_next):
    if request.method in {"POST","PUT","PATCH","DELETE"} and request.cookies.get("entrenamiento_session"):
        if not validate_csrf_token(request.cookies.get(CSRF_COOKIE_NAME), request.headers.get("X-CSRF-Token")):
            return JSONResponse(status_code=403, content={"detail":"CSRF validation failed"})
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic(); bucket = _buckets[ip]
    while bucket and bucket[0] <= now - 60: bucket.popleft()
    if len(bucket) >= 30: return JSONResponse(status_code=429, content={"detail":"Demasiadas peticiones. Espera un minuto."})
    bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="same-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    return response

@app.on_event("startup")
def startup(): init_coach_db()

@app.get("/health")
def health(): return {"status":"ok","service":"coach"}

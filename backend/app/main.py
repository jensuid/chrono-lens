"""ChronoLens analysis service entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import analysis, anomalies, datasets, decomposition, forecast
from .errors import ApiError

app = FastAPI(title="ChronoLens backend", version="0.1.0")

# Dev only: the Vite dev server on :5173 calls the API cross-origin. The
# packaged app talks to 127.0.0.1 directly (same-origin through the
# sidecar), so this does not weaken the shipped posture.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(decomposition.router)
app.include_router(forecast.router)
app.include_router(anomalies.router)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """Every ApiError answers the uniform envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/api/health")
async def health():
    """Liveness for the Tauri shell's sidecar readiness check."""
    return {"status": "ok"}

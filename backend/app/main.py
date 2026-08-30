"""ChronoLens analysis service entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import analysis, anomalies, datasets, decomposition, forecast
from .errors import ApiError

app = FastAPI(title="ChronoLens backend", version="0.1.0")

# Origins allowed to call this local-only API:
# - the Vite dev server (:5173) during `npm run dev`
# - the packaged app's WKWebView, whose page origin is `tauri://localhost`
# The server binds 127.0.0.1 only, so nothing outside this machine can
# reach it regardless.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
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


@app.middleware("http")
async def catch_all_errors(request: Request, call_next):
    """Turn any unhandled exception into the uniform envelope.

    Without this, a server-side failure produces FastAPI's default 500
    response, which (a) carries no CORS headers, so the packaged webview
    reports the generic 'Load failed' instead of the actual error, and
    (b) hides the exception entirely from the client. Keeping the
    middleware inside CORSMiddleware means error responses are still
    CORS-enabled and the real message reaches the UI.
    """
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            },
        )


@app.get("/api/health")
async def health():
    """Liveness for the Tauri shell's sidecar readiness check."""
    return {"status": "ok"}

"""FastAPI entrypoint. Serves the API and the built Vue app from one service."""

import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import aggregates, auth, export, grid, networth, preferences, structure

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("app")

app = FastAPI(title="Personal Finance Tracker", version="1.0.0", docs_url="/api/docs")

WEAK_PASSWORDS = {
    "change-me", "changeme", "letmein", "password", "admin", "test", "secret", "1234",
}


def _startup_checks() -> None:
    """Shout about the two things that bite when this is put on the internet:
    a guessable password, and a database that does not survive a restart."""
    if settings.app_password.lower() in WEAK_PASSWORDS or len(settings.app_password) < 10:
        log.error(
            "SECURITY: APP_PASSWORD is weak. It is the only thing protecting your "
            "financial data — set a long, unique one before exposing this beyond localhost."
        )
    if settings.secret_key in {"dev-secret-change-me", "change-me-too"}:
        log.error("SECURITY: SECRET_KEY is still the example value — session tokens are forgeable.")

    if settings.normalized_database_url.startswith("sqlite"):
        # Free hosting tiers have no persistent disk: the file is wiped on redeploy.
        hosted = any(os.environ.get(key) for key in ("RENDER", "FLY_APP_NAME", "RAILWAY_ENVIRONMENT", "DYNO"))
        if hosted:
            log.error(
                "DATA LOSS RISK: running on a hosted platform with SQLite. Free tiers have "
                "no persistent disk — set DATABASE_URL to your Neon Postgres URL."
            )
        else:
            log.info("Using local SQLite at %s", settings.normalized_database_url)


_startup_checks()

if settings.dev_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.dev_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        log.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router)
app.include_router(structure.router)
app.include_router(grid.router)
app.include_router(networth.router)
app.include_router(aggregates.router)
app.include_router(preferences.router)
app.include_router(export.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------- SPA hosting
dist = settings.static_dir
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Any non-API path falls through to index.html for client-side routing."""
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

else:
    log.warning("static dir %s not found — API only (run `npm run build` in frontend/)", dist)

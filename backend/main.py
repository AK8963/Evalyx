"""
FastAPI main application for TraceIQ observability platform.
"""

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import logging
from backend.config import settings
from backend.database import init_db

# Prometheus metrics (optional — graceful fallback if not installed)
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    )
    _PROM_AVAILABLE = True
    REQUEST_COUNT = Counter(
        "http_requests_total", "Total HTTP requests",
        ["method", "endpoint", "status"]
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds", "HTTP request latency",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]
    )
    ACTIVE_REQUESTS = Gauge("http_requests_active", "Active HTTP requests")
except ImportError:
    _PROM_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    debug=settings.DEBUG
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")

    # Re-queue any evals that were left pending/running (e.g. after a hot-reload)
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from backend.database import SessionLocal
    from database.models import Eval
    from backend.scoring import run_eval_task

    def _resume_pending():
        db = SessionLocal()
        try:
            pending = db.query(Eval).filter(Eval.status.in_(["pending", "running"])).all()
            for ev in pending:
                logger.info(f"Resuming pending eval {ev.id} ({ev.name})")
                try:
                    run_eval_task(
                        eval_id=ev.id,
                        project_id=ev.project_id,
                        dataset_id=ev.dataset_id,
                        scorers=ev.scorers or [],
                    )
                except Exception as exc:
                    logger.error(f"Failed to resume eval {ev.id}: {exc}")
        finally:
            db.close()

    if True:  # always check on startup
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(executor, _resume_pending)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.API_VERSION}


# Prometheus metrics endpoint
@app.get("/metrics", tags=["monitoring"], include_in_schema=False)
async def metrics():
    if not _PROM_AVAILABLE:
        return JSONResponse({"error": "prometheus_client not installed"}, status_code=501)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Prometheus middleware
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    if not _PROM_AVAILABLE:
        return await call_next(request)
    ACTIVE_REQUESTS.inc()
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)
    ACTIVE_REQUESTS.dec()
    return response


# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Import and include routers
from backend.routes import traces, evals, auth, projects
from backend.routes import settings as settings_routes
from backend.routes import (
    analytics, search, topics, loop,
    datasets, annotations, experiments,
    playgrounds, prompts, gateway,
    online_scoring, organizations, audit, dashboards,
    environments, webhooks, export, abtests, autoevals,
    pricing, acls, btql, remote_evals,
    sso, alerts, masking, metrics,
)
from backend.routes import review
from backend.routes import sessions as sessions_routes
from backend.routes import scores as scores_routes

# ── Core ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(traces.router, prefix="/api/traces", tags=["traces"])
app.include_router(evals.router, prefix="/api/evals", tags=["evals"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])

# ── Phase 2: Observability ───────────────────────────────────────────────────
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(topics.router, prefix="/api/topics", tags=["topics"])
app.include_router(loop.router, prefix="/api/loop", tags=["loop"])
app.include_router(dashboards.router, prefix="/api/dashboards", tags=["dashboards"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

# ── Phase 3: Datasets & Annotations ─────────────────────────────────────────
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])

# ── Phase 4: Evaluation ──────────────────────────────────────────────────────
app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(playgrounds.router, prefix="/api/playgrounds", tags=["playgrounds"])
app.include_router(online_scoring.router, prefix="/api/online-scoring", tags=["online-scoring"])
app.include_router(autoevals.router, prefix="/api/autoevals", tags=["autoevals"])

# ── Phase 5: Prompts & Gateway ───────────────────────────────────────────────
app.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
app.include_router(gateway.router, prefix="/api/gateway", tags=["gateway"])

# ── Phase 6: Enterprise / Deploy ─────────────────────────────────────────────
app.include_router(organizations.router, prefix="/api/rbac", tags=["rbac"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(environments.router, prefix="/api/environments", tags=["environments"])
app.include_router(webhooks.router, prefix="/api/automations", tags=["automations"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(abtests.router, prefix="/api/abtests", tags=["abtests"])

# ── Pricing / Cost estimation ─────────────────────────────────────────────────
app.include_router(pricing.router, prefix="/api/pricing", tags=["pricing"])

# ── Phase 1: ACL Permissions + BTQL ──────────────────────────────────────────
app.include_router(acls.router, prefix="/api/acls", tags=["acls"])
app.include_router(btql.router, prefix="/api/btql", tags=["btql"])
# ── Phase 2: Agent Support ─────────────────────────────────────────────────────────
app.include_router(remote_evals.router, prefix="/api/remote-evals", tags=["remote-evals"])
# ── Phase 3: Enterprise Features ────────────────────────────────────────────────────
app.include_router(sso.router, prefix="/api/sso", tags=["sso"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(masking.router, prefix="/api/masking", tags=["masking"])
# ── Showcase Features ───────────────────────────────────────────────────────────
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(sessions_routes.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(scores_routes.router, prefix="/api/scores", tags=["scores"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

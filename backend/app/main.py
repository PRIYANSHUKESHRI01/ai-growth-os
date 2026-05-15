"""
app/main.py
────────────
FastAPI application entry point.
- Runs DB column migrations (Clerk auth columns)
- Creates all DB tables on startup
- Mounts all routers
- Configures CORS
- Initialises logging
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.database import engine
from app.models import Base  # imports all models → registers with metadata (incl. Automation 2)
from app.modules.lead_scoring.routes import router
from app.modules.lead_discovery.routes import discovery_router  # Automation 2
from app.modules.outreach_engine.routes import outreach_router  # Automation 3

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


def _run_migrations() -> None:
    """
    Idempotent schema migrations.
    Adds clerk_user_id column and makes api_key nullable.
    Uses IF NOT EXISTS / TRY patterns so it's safe to run on every startup.
    """
    with engine.connect() as conn:
        # ── Add clerk_user_id ─────────────────────────────────────────────────
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(255);
        """))

        # ── Make api_key nullable (idempotent in Postgres) ────────────────────
        conn.execute(text("""
            ALTER TABLE users
            ALTER COLUMN api_key DROP NOT NULL;
        """))

        # ── Add DB performance indexes ─────────────────────────────────────────
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_users_clerk_user_id
            ON users(clerk_user_id)
            WHERE clerk_user_id IS NOT NULL;
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_leads_user_id ON leads(user_id);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_leads_email ON leads(email);"
        ))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_discovery_jobs_user_id
            ON discovery_jobs(user_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_enriched_leads_user_id
            ON enriched_leads(user_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_enriched_leads_job_id
            ON enriched_leads(job_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_dedupe_keys_hash_key
            ON dedupe_keys(hash_key);
        """))
        # ── Automation 3 indexes ────────────────────────────────────────────────
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaign_leads_campaign_id
            ON campaign_leads(campaign_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaign_leads_lead_id
            ON campaign_leads(lead_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaign_leads_status
            ON campaign_leads(status);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_campaign_step_stats_campaign_id
            ON campaign_step_stats(campaign_id);
        """))
        # ── Automation 3.1: Open Tracking columns (idempotent ALTER TABLE) ───────
        for stmt in [
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_opened BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sendgrid_event_id VARCHAR(255);",
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS min_score_filter FLOAT DEFAULT 0.5;",
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_sent INTEGER DEFAULT 0;",
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_replied INTEGER DEFAULT 0;",
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_opened INTEGER DEFAULT 0;",
            "ALTER TABLE campaign_step_stats ADD COLUMN IF NOT EXISTS total_opened INTEGER DEFAULT 0;",
            "ALTER TABLE campaign_step_stats ADD COLUMN IF NOT EXISTS open_rate FLOAT DEFAULT 0.0;",
        ]:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists — safe to ignore
        conn.commit()
        logger.info("✅ DB migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown tasks."""
    print("🚀 Starting AI Growth OS")

    # Run safe migrations before create_all
    try:
        _run_migrations()
    except Exception as e:
        logger.warning("Migration warning (non-fatal): %s", e)

    # Create tables (idempotent — only creates missing tables)
    Base.metadata.create_all(bind=engine)
    print("✅ Database connected")
    print("✅ Tables verified")

    # Pre-warm ML models (avoids cold-start on first request)
    from app.modules.lead_scoring.ml.predictor import lead_scorer
    print("✅ ML models loaded")
    print("🌐 Server running on http://localhost:8000")

    yield


app = FastAPI(
    title="AI Growth OS — Sales Execution Engine",
    description=(
        "Production-ready backend for AI-powered lead scoring, "
        "LLM outreach generation, and automated email delivery."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Structured error response handler ────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router, prefix="/api/v1")
app.include_router(discovery_router, prefix="/api/v1")  # Automation 2
app.include_router(outreach_router, prefix="/api/v1")   # Automation 3

# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "AI Growth OS",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

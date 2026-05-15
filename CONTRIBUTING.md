# Contributing to AI Growth OS

> **AI Growth OS** is a production-grade SaaS platform with an AI-powered lead discovery, scoring, and outreach pipeline. This guide covers everything you need to run, develop, and understand the system locally.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Backend Startup](#backend-startup)
- [Celery Worker Startup](#celery-worker-startup)
- [Frontend Startup](#frontend-startup)
- [Deployment Flow](#deployment-flow)
- [Project Structure](#project-structure)
- [Development Guidelines](#development-guidelines)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Next.js 16 Frontend (Vercel)                       │
│  Clerk Auth · React Query · Tailwind CSS             │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS / REST
┌──────────────────────▼──────────────────────────────┐
│  FastAPI Backend (Render / Docker)                   │
│  Gunicorn + UvicornWorker · /api/v1/*               │
│                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │
│  │ lead_scoring │ │lead_discovery│ │outreach_eng │ │
│  │  (Module 1)  │ │  (Module 2)  │ │  (Module 3) │ │
│  └──────────────┘ └──────────────┘ └─────────────┘ │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│  Celery Workers · Redis (Upstash)                    │
│  Task queues for async discovery & scoring jobs     │
└──────────────────────────────────────────────────────┘
       │                            │
┌──────▼──────────┐        ┌────────▼──────────┐
│  PostgreSQL      │        │  Redis / Upstash  │
│  (Supabase)      │        │  (Broker/Cache)   │
└─────────────────┘        └───────────────────┘
```

| Service | Technology | Hosted On |
|---------|-----------|-----------|
| Frontend | Next.js 16, Clerk, TanStack Query | Vercel |
| Backend API | FastAPI, Gunicorn, SQLAlchemy | Render |
| Database | PostgreSQL | Supabase |
| Cache / Queue | Redis | Upstash |
| Async Workers | Celery | Render (Worker service) |
| Email | SendGrid | — |
| LLM | OpenAI GPT-4o-mini | — |

---

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 20 LTS+ | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 15+ | Local or [Supabase](https://supabase.com) |
| Redis | 7+ | Local or [Upstash](https://upstash.com) |
| Git | any | — |

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/ai-growth-os.git
cd ai-growth-os
```

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

---

## Environment Variables

### Backend — `backend/.env`

Copy the example and fill in your values:

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string — `postgresql://user:pass@host:port/dbname` |
| `REDIS_URL` | ✅ | Redis connection — `redis://localhost:6379/0` or Upstash `rediss://...` |
| `SECRET_KEY` | ✅ | Random 32+ character string for JWT signing |
| `OPENAI_API_KEY` | ✅ | OpenAI API key (`sk-...`) |
| `OPENAI_MODEL` | ❌ | Model override — defaults to `gpt-4o-mini` |
| `SENDGRID_API_KEY` | ✅ | SendGrid API key (`SG....`) |
| `SENDGRID_FROM_EMAIL` | ✅ | Verified sender email address |
| `SENDGRID_FROM_NAME` | ❌ | Defaults to `AI Growth OS` |
| `APOLLO_API_KEY` | ❌ | Apollo.io key for live lead discovery (falls back to mock adapter if absent) |
| `APP_ENV` | ❌ | `development` or `production` |
| `LOG_LEVEL` | ❌ | Defaults to `INFO` |
| `ALLOWED_ORIGINS` | ❌ | Comma-separated CORS origins — defaults to `http://localhost:3000` |
| `EMAIL_RATE_LIMIT_PER_MINUTE` | ❌ | Defaults to `10` |
| `EMAIL_RATE_LIMIT_PER_DAY` | ❌ | Defaults to `500` |

### Frontend — `frontend/.env.local`

Create this file manually (it is git-ignored):

```bash
# frontend/.env.local

# Clerk authentication (get from https://dashboard.clerk.com)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...

# Backend API base URL
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Backend Startup

Make sure your virtual environment is activated and `backend/.env` is populated.

### Development server (hot-reload)

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Root**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/api/v1/health

### Production server (Gunicorn)

```bash
cd backend
gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Docker (full stack)

```bash
cd backend
docker-compose up --build
```

This spins up: PostgreSQL, Redis, the FastAPI API server, a Celery worker, and Celery Flower (monitoring at http://localhost:5555).

---

## Celery Worker Startup

Celery handles asynchronous tasks: lead discovery pipeline execution, batch scoring, and email campaign delivery.

### Prerequisites
- Redis must be running and `REDIS_URL` set in `.env`
- Virtual environment must be activated
- Run from the `backend/` directory

### Start the worker

```bash
cd backend

# Windows (PowerShell)
celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=2

# macOS / Linux
celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=2
```

### Start Flower (optional — task monitoring UI)

```bash
cd backend
celery -A app.core.celery_app.celery_app flower --port=5555
```

Flower UI is available at http://localhost:5555.

### Registered task queues

| Module | Task File | Purpose |
|--------|-----------|---------|
| `lead_scoring` | `app/modules/lead_scoring/workers/tasks.py` | Async batch lead scoring |
| `lead_discovery` | `app/modules/lead_discovery/workers/discovery_tasks.py` | 6-stage async discovery pipeline |
| `outreach_engine` | `app/modules/outreach_engine/workers/outreach_tasks.py` | Email campaign execution |

> **Note**: Most discovery and scoring flows also support a synchronous path (`POST /discovery/run-sync/{id}`) that runs entirely in-process without Celery. This is useful when Celery workers are not available.

---

## Frontend Startup

```bash
cd frontend
npm run dev
```

The frontend will be available at http://localhost:3000.

### Available scripts

| Script | Command | Purpose |
|--------|---------|---------|
| Dev server | `npm run dev` | Next.js with hot-reload |
| Production build | `npm run build` | Compile for deployment |
| Production serve | `npm start` | Serve compiled build |
| Lint | `npm run lint` | ESLint check |

### Authentication

The frontend uses [Clerk](https://clerk.com) for authentication. All API calls are made through the `useApiClient()` hook (`src/hooks/useApiClient.ts`), which automatically attaches the Clerk JWT token to every request.

Do **not** add raw `fetch()` calls with hardcoded tokens — always go through `useApiClient()`.

---

## Deployment Flow

### Backend → Render

1. Push to `main` branch
2. Render auto-deploys from the `backend/` Dockerfile
3. Start command: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120`
4. Set all environment variables in the Render dashboard (match `.env.example`)
5. For the Celery worker, create a separate Render **Background Worker** service with the command:
   ```
   celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=2
   ```

### Frontend → Vercel

1. Push to `main` branch
2. Vercel auto-deploys from the `frontend/` directory
3. Set environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
   - `CLERK_SECRET_KEY`
   - `NEXT_PUBLIC_API_URL` (point to your Render backend URL)
4. Configure Clerk allowed origins to include your Vercel domain

### Database migrations

Migrations are handled automatically on startup via `_run_migrations()` in `app/main.py`. This function uses `ALTER TABLE ... IF NOT EXISTS` patterns and is idempotent — safe to run on every deploy.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry point, router mounting
│   ├── core/
│   │   ├── celery_app.py          # Celery app + task autodiscovery
│   │   ├── config.py              # Pydantic settings (reads .env)
│   │   ├── database.py            # SQLAlchemy engine + session
│   │   ├── logging.py             # Structured logging setup
│   │   └── security.py            # JWT + Clerk auth utilities
│   ├── api/
│   │   └── deps.py                # FastAPI dependency injectors (DB session, user ID)
│   ├── models/                    # SQLAlchemy ORM models
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── repositories/              # Database query layer
│   └── modules/
│       ├── lead_scoring/          # Module 1: AI scoring engine
│       │   ├── ml/                # Feature extraction, signal scoring, predictor
│       │   ├── services/          # LeadService, ScoringService, LLMService
│       │   ├── workers/tasks.py   # Celery tasks
│       │   └── routes.py          # /api/v1/leads, /api/v1/scores
│       ├── lead_discovery/        # Module 2: Lead discovery & enrichment
│       │   ├── adapters/          # ApolloAdapter, MockAdapter
│       │   ├── providers/         # Enrichment providers (waterfall)
│       │   ├── services/          # DiscoveryService, EnrichmentService, etc.
│       │   ├── workers/           # 6-stage Celery pipeline
│       │   └── routes.py          # /api/v1/discovery/*
│       └── outreach_engine/       # Module 3: Email outreach campaigns
│           ├── services/          # CampaignService, EmailService, LLMService
│           ├── workers/           # Campaign execution tasks
│           └── routes.py          # /api/v1/outreach/*

frontend/
├── src/
│   ├── app/                       # Next.js App Router pages
│   │   ├── dashboard/             # Authenticated dashboard pages
│   │   │   ├── page.tsx           # Main dashboard
│   │   │   ├── leads/             # Lead list + detail
│   │   │   ├── campaigns/         # Campaign management
│   │   │   ├── discovery/         # Lead discovery UI
│   │   │   └── upload/            # CSV lead upload
│   │   └── page.tsx               # Landing page
│   ├── components/                # Reusable React components (shadcn/ui based)
│   ├── hooks/                     # React Query hooks (useApiClient, useLeads, etc.)
│   ├── lib/
│   │   ├── api.ts                 # TypeScript API interfaces (types only)
│   │   └── utils.ts               # cn() utility
│   └── providers/                 # React context providers (QueryProvider, etc.)
```

---

## Development Guidelines

### DO
- Follow the existing module structure — new features go inside `app/modules/<module_name>/`
- Use the `get_logger(__name__)` pattern from `app.core.logging` for all logging
- Use `Depends(get_current_user_id)` on every endpoint that touches user data
- Use `useApiClient()` hook for all frontend API calls — never raw `fetch()`
- Prefix new Celery tasks with the module name for traceability

### DON'T
- Rename existing API routes without updating the frontend hook layer
- Change DB column names without an idempotent `ALTER TABLE` migration in `_run_migrations()`
- Add secrets to git — use `.env` files (already in `.gitignore`)
- Import from `backend/archive/` — those files are development utilities only

### Code style
- **Backend**: PEP 8, type hints everywhere, docstrings on all public functions
- **Frontend**: TypeScript strict mode, named exports, no `any` unless unavoidable

---

> For questions or issues, open a GitHub Issue or reach out to the maintainers.

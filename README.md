# AI Growth OS — AI Sales Execution Engine

A **production-ready, cloud-deployable backend** for automated lead scoring, LLM-powered outreach generation, and email delivery.

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn/Gunicorn |
| Database | PostgreSQL + SQLAlchemy 2 |
| Task Queue | Celery + Redis |
| ML | scikit-learn (LogisticRegression + RandomForest) |
| LLM | LangChain + OpenAI (GPT-4o-mini) |
| Email | SendGrid API |
| Config | pydantic-settings |
| Container | Docker (multi-stage) |

---

## 📁 Project Structure

```
app/
├── api/           # FastAPI routes & dependencies
├── core/          # Config, DB, logging, security
├── ml/            # ML models, feature engineering
├── models/        # SQLAlchemy ORM models
├── repositories/  # Data access layer (user_id scoped)
├── schemas/       # Pydantic request/response models
├── services/      # Business logic
└── workers/       # Celery tasks
```

---

## ⚡ Quick Start (Local Dev)

### 1. Clone & Configure

```bash
git clone <your-repo>
cd "AI Growth OS"
cp .env.example .env
# Fill in your OPENAI_API_KEY, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
```

### 2. Start with Docker Compose

```bash
docker-compose up --build
```

This starts:
- `api` on http://localhost:8000
- `worker` (Celery)
- `postgres` on localhost:5432
- `redis` on localhost:6379
- `flower` (Celery monitor) on http://localhost:5555

### 3. View API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🌐 API Endpoints

All endpoints require the `X-API-Key` header for multi-tenant authentication.

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Upload Leads (CSV)
```bash
curl -X POST http://localhost:8000/api/v1/leads/upload \
  -H "X-API-Key: your-api-key" \
  -F "file=@test_leads.csv"
```

### Upload Leads (JSON)
```bash
curl -X POST http://localhost:8000/api/v1/leads/upload \
  -H "X-API-Key: your-api-key" \
  -F 'json_data=[{"email":"john@example.com","first_name":"John","last_name":"Doe","company":"Acme","title":"CEO","industry":"Technology","company_size":"51-200"}]'
```

### List Leads
```bash
curl "http://localhost:8000/api/v1/leads?page=1&page_size=20" \
  -H "X-API-Key: your-api-key"
```

### Run Campaign
```bash
curl -X POST http://localhost:8000/api/v1/campaign/run \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"campaign_name": "Q2 Outreach", "lead_ids": null}'
```
> Passing `null` for `lead_ids` runs the campaign on ALL of your leads.

### Check Campaign Status
```bash
curl "http://localhost:8000/api/v1/campaign/status?campaign_id=<campaign-id>" \
  -H "X-API-Key: your-api-key"
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `OPENAI_MODEL` | ❌ | Model name (default: `gpt-4o-mini`) |
| `SENDGRID_API_KEY` | ✅ | SendGrid API key |
| `SENDGRID_FROM_EMAIL` | ✅ | Verified sender email |
| `SENDGRID_FROM_NAME` | ❌ | Sender display name |
| `EMAIL_RATE_LIMIT_PER_MINUTE` | ❌ | Max emails/min per user (default: 10) |
| `EMAIL_RATE_LIMIT_PER_DAY` | ❌ | Max emails/day per user (default: 500) |
| `APP_ENV` | ❌ | `development` or `production` |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |
| `SECRET_KEY` | ✅ | Random 32-char secret |

---

## 🚀 Deployment

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Add env vars via Railway dashboard or CLI
railway variables set DATABASE_URL=... OPENAI_API_KEY=... ...
```

Add two services: one for the API (`Dockerfile` default CMD), one for the worker (override CMD with Celery command).

### Render

1. Create a **Web Service** — Docker build, port 8000
2. Create a **Background Worker** — same Docker image, command:
   ```
   celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=2
   ```
3. Add a **Redis** add-on and a **PostgreSQL** add-on
4. Set all env vars in the Render dashboard

### AWS ECS (Fargate)

1. Push image to ECR:
   ```bash
   aws ecr create-repository --repository-name ai-growth-os
   docker build -t ai-growth-os .
   docker tag ai-growth-os:latest <account>.dkr.ecr.<region>.amazonaws.com/ai-growth-os:latest
   docker push <account>.dkr.ecr.<region>.amazonaws.com/ai-growth-os:latest
   ```
2. Create two ECS task definitions: API and Worker (different CMD)
3. Use RDS PostgreSQL and ElastiCache Redis for managed services
4. Store all secrets in AWS Secrets Manager and reference in task definition

---

## 🤖 Multi-Tenant Architecture

Every API call requires `X-API-Key` header. The key maps to a `user_id` that scopes **all** database queries — leads, campaigns, and messages. Tenants are fully isolated at the query level.

**To onboard a new user**: insert a `User` record with a unique `api_key`. In production, replace the key-based auth in `app/core/security.py` with full JWT/OAuth2.

---

## 📊 Email Rate Limiting

Rate limits are enforced per-user via Redis atomic counters:
- **Per-minute**: protects against SendGrid burst limits
- **Per-day**: protects against daily quota exhaustion

Rate-limited emails are automatically retried by Celery workers after 60 seconds and tracked with `RATE_LIMITED` status in the database.

---

## 📈 Scoring Formula

```
final_score = (0.4 × reply_probability) + (0.6 × conversion_probability)
```

Leads with higher scores receive more confident/direct email copy from the LLM.

---

## 🔬 ML Models

- **Reply Model**: `LogisticRegression` on 6 features (industry, company size, title seniority, LinkedIn presence, company, source)
- **Conversion Model**: `RandomForestClassifier` on same features
- Models are auto-trained with synthetic data on first startup and cached to `app/ml/models/`
- Replace with real training data by calling `_train_and_save_models()` with your dataset

---

## 🌸 Monitoring

- **Celery Flower**: http://localhost:5555 (task monitoring dashboard)
- **API Health**: `GET /api/v1/health`
- **Logs**: structured JSON in production, human-readable in development

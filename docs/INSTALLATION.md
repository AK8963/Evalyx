# Installation Guide

## Prerequisites

| Tool | Minimum Version | Purpose |
|---|---|---|
| Docker Desktop | 4.x | Runs all services in containers |
| Docker Compose | 2.x | Orchestrates the multi-container setup |
| Python | 3.9+ | Required only if running outside Docker |
| Git | any | Cloning the repository |

No database or Redis installation is needed locally — everything runs inside Docker.

---

## 1. Clone the Repository

```bash
git clone <repo-url>
cd Exp_braintrust
```

---

## 2. Configure Environment Variables

Copy the example environment file (or create `.env` manually):

```bash
cp .env.example .env   # if available, otherwise create manually
```

### Required Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | JWT signing secret — **change in production** |
| `DATABASE_URL` | `postgresql://traciq:traciq_dev@postgres:5432/traciq_db` | Postgres connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |

### Optional — LLM Provider Keys (for Gateway feature)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Enables OpenAI models in the Gateway |
| `ANTHROPIC_API_KEY` | Enables Claude models in the Gateway |
| `GOOGLE_API_KEY` | Enables Gemini models in the Gateway |
| `OLLAMA_API_URL` | URL to local Ollama instance (default `http://localhost:11434`) |
| `OLLAMA_ENABLED` | Set `true` to enable Ollama routing |

> You can also set provider API keys per-user inside the dashboard under **Settings → API Keys**. Those take precedence over environment variables.

---

## 3. Start All Services

```bash
docker-compose up -d
```

This starts five containers:

| Container | Port | Role |
|---|---|---|
| `traciq_backend` | `8000` | FastAPI REST API |
| `traciq_frontend` | `8501` | Streamlit dashboard |
| `traciq_postgres` | `5433` (host) | PostgreSQL — primary datastore |
| `traciq_redis` | `6380` (host) | Redis — caching and rate limiting |
| `traciq_qdrant` | `6333` (host) | Qdrant — vector store for semantic search |

Check that all containers are healthy:

```bash
docker-compose ps
```

Expected output — all containers should show `Up` or `Up (healthy)`.

---

## 4. Verify the Backend

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"connected"}
```

You can also browse the interactive API docs at:

```
http://localhost:8000/docs        # Swagger UI
http://localhost:8000/redoc       # ReDoc
```

---

## 5. Open the Dashboard

Navigate to **http://localhost:8501** in your browser.

### First-time Setup

1. Click the **Register** tab in the sidebar.
2. Enter your name and email address — no password required (JWT-based auth).
3. Click **Register**. You are logged in automatically.
4. Create your first **Project** from the sidebar project selector.
5. Go to **Settings** and copy your **TraceIQ API Key** — you'll need this to send traces from your application.

---

## 6. Stopping and Restarting

```bash
# Stop all containers (data is preserved in Docker volumes)
docker-compose down

# Stop and delete all data (fresh start)
docker-compose down -v

# Restart a single service after a code change
docker-compose restart backend
docker-compose restart frontend
```

---

## 7. Updating to Latest Code

Because the source directory is mounted as a volume, backend and frontend code changes are picked up automatically by Streamlit's file watcher. For backend changes:

```bash
docker-compose restart backend
```

If you add new Python packages to `requirements-backend.txt` or `requirements-frontend.txt`, you must rebuild:

```bash
docker-compose build backend   # or frontend
docker-compose up -d
```

---

## 8. Production Considerations

| Topic | Recommendation |
|---|---|
| **SECRET_KEY** | Use a long random string: `openssl rand -hex 32` |
| **Database** | Use a managed Postgres service (RDS, Cloud SQL) and set `DATABASE_URL` |
| **TLS** | Put an Nginx or Traefik reverse proxy in front of ports 8000 and 8501 |
| **Auth** | Add `server.enableXsrfProtection = true` in `.streamlit/config.toml` |
| **Backups** | Schedule `pg_dump` on the `traciq_db` database |
| **Scaling** | The backend is stateless — run multiple replicas behind a load balancer |

---

## 9. Kubernetes Deployment

Kubernetes manifests are provided in the `k8s/` directory:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml        # edit with real values first
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/qdrant.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
```

---

## Troubleshooting

### Backend fails to start — "relation does not exist"

The database schema is created automatically by SQLAlchemy on first boot. If you see this error after adding a new column to an existing table, run the migration manually:

```bash
docker exec -it traciq_postgres psql -U traciq -d traciq_db
# then run your ALTER TABLE statement
```

### Frontend shows a blank page

```bash
docker logs traciq_frontend --tail 30
```

Look for Python import errors. The most common cause is a missing dependency — add it to `requirements-frontend.txt` and rebuild.

### 401 Unauthorized when sending traces

Make sure you are passing your API key in one of these ways:
- Header: `X-API-Key: <your-key>`
- Header: `Authorization: Bearer <jwt-token>`

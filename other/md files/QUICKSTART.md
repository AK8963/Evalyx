# 🚀 Quick Start Guide

Get TraceIQ running locally in 5 minutes!

## Prerequisites

- Python 3.9+
- PostgreSQL (or Docker)
- Redis (or Docker)

## Option 1: Using Docker (Easiest - 2 minutes)

```bash
# Clone repo
cd traciq-open

# Start all services
docker-compose up -d

# Wait for services to start (30 seconds)
sleep 30

# Open dashboard
open http://localhost:8501
```

Done! 🎉

Dashboard: http://localhost:8501
API Docs: http://localhost:8000/docs

---

## Option 2: Local Setup

### 1. Install Python Dependencies (1 min)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

### 2. Set Up Database (2 min)

**PostgreSQL:**
```bash
# Mac (using Homebrew)
brew install postgresql@15
brew services start postgresql@15
createdb -U postgres traciq_db

# Or use Docker
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=traciq \
  -e POSTGRES_PASSWORD=traciq_dev \
  -e POSTGRES_DB=traciq_db \
  postgres:15-alpine
```

**Redis:**
```bash
# Mac (using Homebrew)
brew install redis
brew services start redis

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Configure Environment (1 min)

```bash
# Copy template
cp .env.template .env

# .env should have:
DATABASE_URL=postgresql://traciq:traciq_dev@localhost:5432/traciq_db
REDIS_URL=redis://localhost:6379/0
DEBUG=True
```

### 4. Start Services (1 min)

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
streamlit run app.py
```

### 5. Access Dashboard

- Dashboard: http://localhost:8501
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## First Steps

### 1. Create Account

Open http://localhost:8501

1. Go to "Register" tab
2. Enter email and name
3. Copy the API key

### 2. Create Project

1. Login with API key
2. Enter project name
3. Click "Create"

### 3. Send Your First Trace

```python
import sys
sys.path.insert(0, 'sdk')
import traciq

# Initialize
traciq.init(api_key="your_api_key_here")

# Send trace
trace_id = traciq.trace(
    project_id="my_project",
    input_data={"prompt": "What is AI?"},
    output_data={"answer": "AI is..."},
    model="gpt-4"
)

# Flush
traciq.flush()

print(f"Trace sent: {trace_id}")
```

### 4. View in Dashboard

1. Go to Dashboard
2. Select project
3. See trace appear in real-time!

---

## Run Examples

```bash
python examples.py
```

This demonstrates:
- Basic tracing
- Decorator-based tracing
- Context managers
- Batch tracing
- Error handling

---

## Next Steps

### Integrate with Your App

See [README.md](README.md) for full integration guide

### Run Evaluations

1. Go to "Evaluations" tab
2. Select trace
3. Choose scorer (LLM, Expected Value, Code)
4. Click "Run Evaluation"

### Explore API

Visit http://localhost:8000/docs for interactive API docs

---

## Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Check database connection
psql -U traciq -d traciq_db -h localhost
```

### Frontend won't load
```bash
# Check if port 8501 is in use
lsof -i :8501

# Check logs
streamlit run frontend/app.py --logger.level=debug
```

### Can't connect to database
```bash
# Verify PostgreSQL is running
psql --version

# Check connection
psql -U traciq -d traciq_db -h localhost -c "SELECT 1"
```

### Can't send traces
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check API key in dashboard
# Verify project_id matches
```

---

## Architecture

```
Your App
   ↓ (uses SDK)
TraceIQ SDK
   ↓ (sends batch)
FastAPI Backend
   ↓ (stores)
PostgreSQL
   ↑ (queries)
Streamlit Dashboard
```

---

## What's Included

✅ Trace ingestion (SDk)
✅ FastAPI backend
✅ PostgreSQL database
✅ Redis cache
✅ Streamlit dashboard
✅ Evaluation engine
✅ Authentication

---

## Learn More

- [Full README](README.md)
- [API Reference](README.md#-api-reference)
- [Architecture](README.md#-architecture)
- [Deployment](README.md#-deployment)

---

**Need help?** Check the GitHub issues or discussions!

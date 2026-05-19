# 👨‍💻 Development Guide

Guide for developers working on TraceIQ.

## Project Structure

```
traciq-open/
├── backend/                 # FastAPI server (port 8000)
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Configuration from environment
│   ├── database.py         # Database connection & session
│   ├── scoring.py          # Evaluation/scoring engine
│   └── routes/             # API endpoints
│       ├── auth.py         # User registration & API keys
│       ├── traces.py       # Trace ingestion & retrieval
│       ├── evals.py        # Evaluation management
│       └── projects.py     # Project management
│
├── frontend/               # Streamlit dashboard (port 8501)
│   ├── app.py             # Main dashboard app
│   ├── api_client.py      # Wrapper for backend API
│   └── pages/             # [Future] Multi-page app structure
│
├── sdk/                    # Python SDK for trace collection
│   └── traciq/
│       ├── client.py      # Main TraceIQClient class
│       ├── decorators.py  # @traciq_trace decorator
│       └── __init__.py    # Public API exports
│
├── database/              # Database layer
│   ├── models.py          # SQLAlchemy ORM models
│   └── migrations/        # [Future] Alembic migrations
│
├── examples.py            # SDK usage examples
├── docker-compose.yml     # Docker Compose setup
├── README.md              # Project documentation
├── QUICKSTART.md          # Quick start guide
└── requirements*.txt      # Python dependencies
```

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web Framework | FastAPI | Async, fast, great for real-time |
| Frontend | Streamlit | Python-native, rapid iteration |
| Database | PostgreSQL | Reliable, JSONB for traces |
| ORM | SQLAlchemy | Powerful, flexible |
| Task Queue | Celery | Async eval jobs |
| Cache | Redis | Session, batch queue |
| HTTP Client | httpx | Async, request pooling |

## Local Development Setup

### 1. Clone & Virtual Environment

```bash
git clone <repo>
cd traciq-open

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install All Dependencies

```bash
# Backend
pip install -r requirements-backend.txt

# Frontend
pip install -r requirements-frontend.txt

# SDK (for testing)
pip install -r requirements-sdk.txt
```

### 3. Database Setup

```bash
# PostgreSQL
createdb -U postgres traciq_db
# Or use Docker: docker run -d -p 5432:5432 postgres:15

# Redis
# Or use Docker: docker run -d -p 6379:6379 redis:7
```

### 4. Environment Configuration

```bash
cp .env.template .env
# Edit .env if needed
```

### 5. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
streamlit run app.py --logger.level=debug
```

**Terminal 3 - (Optional) Redis:**
```bash
redis-server
```

## Code Organization

### Backend (`backend/`)

#### main.py - App Setup
```python
# Initializes FastAPI app
# Registers routes
# Sets up middleware (CORS, error handling)
# Database initialization
```

#### routes/
- **auth.py** - User registration, API key verification
- **traces.py** - Trace ingestion (`/api/traces/batch`), retrieval
- **evals.py** - Evaluation creation and status
- **projects.py** - Project CRUD operations

#### config.py
```python
# Loads from environment variables
settings.DATABASE_URL
settings.OPENAI_API_KEY
settings.BATCH_SIZE
# etc.
```

#### database.py
```python
# Creates SQLAlchemy engine
# SessionLocal factory for routes
# init_db() creates tables
```

#### scoring.py
```python
# CodeScorer - execute user Python functions
# LLMScorer - call Claude/GPT/Gemini
# ExpectedValueScorer - compare to golden standard
# run_eval_task - background evaluation job
```

### Frontend (`frontend/`)

#### app.py
```python
# Main Streamlit app
# Sidebar: login/register, project selection
# Main tabs: Dashboard, Traces, Evaluations
# State management (session_state)
```

#### api_client.py
```python
# Wrapper for backend API
# Methods: create_project, list_traces, create_eval, etc.
# Handles authentication (Bearer token)
```

### SDK (`sdk/traciq/`)

#### client.py
```python
# TraceIQClient class
# trace() method to send traces
# Batch sending + threading
# Context manager support (__enter__, __exit__)
```

#### decorators.py
```python
# @traciq_trace decorator
# TraceContext context manager
# Automatic input/output/error capture
```

## Database Schema

### Users
- `id` - UUID primary key
- `email` - Unique email
- `api_key` - Unique API key for auth
- `is_active` - Account status

### Projects
- `id` - UUID
- `owner_id` - Foreign key to User
- `name` - Project name
- Unique constraint: (owner_id, name)

### Traces
- `id` - UUID
- `project_id` - Foreign key to Project
- `input_data` - JSON (user input)
- `output_data` - JSON (LLM output)
- `expected_output` - JSON (golden standard)
- `model` - Model name (indexed)
- `status` - success/error/partial
- `spans` - JSON array (nested calls)
- `metadata` - JSON (custom data)
- `timestamp` - ISO datetime (indexed)

### Scores
- `id` - Composite (trace_id + scorer_name)
- `trace_id` - Foreign key
- `scorer_name` - Name of scorer
- `scorer_type` - code/llm/expected/human
- `score_value` - 0-1 float
- `explanation` - Optional text

### Evals
- `id` - UUID
- `project_id` - Foreign key
- `dataset_id` - Optional foreign key
- `status` - pending/running/completed/failed
- `scorers` - JSON (scorer configs)
- `results` - JSON (detailed results)

### Datasets (Phase 2)
- `id` - UUID
- `project_id` - Foreign key
- `examples` - JSON array
- `version` - Integer versioning

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register user
- `POST /api/auth/verify-api-key` - Verify key

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create project
- `GET /api/projects/{id}` - Get project

### Traces
- `POST /api/traces/batch` - Ingest traces (main endpoint)
- `POST /api/traces` - Create single trace
- `GET /api/traces` - List traces (with filters)
- `GET /api/traces/{id}` - Get trace details
- `DELETE /api/traces/{id}` - Delete trace

### Evaluations
- `POST /api/evals` - Create evaluation
- `GET /api/evals` - List evaluations
- `GET /api/evals/{id}` - Get evaluation details

### Health
- `GET /health` - Health check

## Common Development Tasks

### Add a New API Endpoint

1. **Create route function in `routes/xxx.py`:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/items")
async def list_items(db: Session = Depends(get_db)):
    items = db.query(Item).all()
    return items
```

2. **Include router in `main.py`:**
```python
from backend.routes import new_route
app.include_router(new_route.router, prefix="/api/items", tags=["items"])
```

### Add a Database Model

1. **Add to `database/models.py`:**
```python
class Item(Base):
    __tablename__ = "items"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    # etc.
```

2. **Tables auto-created on startup** via `init_db()`

### Add Frontend Page

1. **Create in `frontend/pages/xxx.py`:**
```python
import streamlit as st
from frontend.api_client import APIClient

def show_page():
    # Your page code
    pass
```

2. **Add tab in `frontend/app.py`:**
```python
tab = st.tabs(["New Page"])
with tab:
    show_page()
```

### Test an Endpoint

```bash
# Using curl
curl -X GET http://localhost:8000/api/traces \
  -H "Authorization: Bearer your_api_key"

# Or use interactive API docs
# http://localhost:8000/docs
```

### Debug Traces

```python
# Add logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Trace: {trace}")

# Check database directly
psql -U traciq -d traciq_db
# SELECT * FROM traces;
```

## Testing (Phase 2)

```bash
# Install pytest
pip install pytest pytest-asyncio

# Run tests
pytest tests/

# With coverage
pytest --cov=backend tests/
```

## Common Issues

### Import Errors
```python
# Make sure PYTHONPATH includes project root
import sys
sys.path.insert(0, '.')
```

### Database Connection Errors
```bash
# Check PostgreSQL is running
psql -U traciq -d traciq_db

# Check DATABASE_URL in .env
# postgresql://user:pass@host:port/db
```

### Frontend Can't Connect to Backend
```bash
# Check backend is running
curl http://localhost:8000/health

# Check API client uses correct URL
api_client = APIClient("http://localhost:8000")
```

## Performance Tips

### Trace Batching
- SDK batches traces before sending (BATCH_SIZE=100)
- Configurable batch timeout (BATCH_TIMEOUT_MS=5000)
- Reduces API calls, improves throughput

### Database Indexing
- Traces indexed by: project_id, timestamp, model, status
- Queries are fast even with millions of traces

### Caching
- Redis for session management
- Could add response caching (Phase 2)

## Next Steps

### What to Work On Next

1. **Fix async/await in scoring** - Currently uses sync callbacks
2. **Add dataset management** - Upload CSV, versioning
3. **Improve frontend UI** - Better visualizations
4. **Add more scorers** - Custom scoring functions
5. **TypeScript SDK** - For JavaScript/Node apps

### Architecture Decisions

- **Why FastAPI?** - Async by default, great for real-time trace ingestion
- **Why Streamlit?** - Rapid iteration, no frontend skills needed
- **Why PostgreSQL + JSONB?** - Flexible schema for nested traces, SQL queries
- **Why batch traces?** - Reduces network overhead, improves reliability

## Getting Help

- Check existing issues
- Read code comments
- Look at examples.py
- Check README.md and QUICKSTART.md

## Code Style

Follow PEP 8:
```bash
# Format code
black backend/ frontend/ sdk/

# Check style
flake8 backend/ frontend/ sdk/
```

## Contributing

1. Fork repo
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes
4. Test locally
5. Commit: `git commit -am "Add feature"`
6. Push: `git push origin feature/your-feature`
7. Create Pull Request

---

**Happy coding!** 🚀

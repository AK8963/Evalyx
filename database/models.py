"""
SQLAlchemy models for TraceIQ observability platform.
Complete model set for all phases: Tracing, Observability, Datasets,
Evaluation, Annotations, Prompts, Gateway, RBAC, Audit.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey,
    Text, Boolean, JSON, Index, Numeric, UniqueConstraint, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from uuid import uuid4
import enum

Base = declarative_base()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RoleEnum(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    manager = "manager"
    viewer = "viewer"
    reviewer = "reviewer"


class SpanType(str, enum.Enum):
    eval = "eval"
    task = "task"
    llm = "llm"
    function = "function"
    tool = "tool"
    score = "score"


class DeploymentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key = Column(String(255), unique=True, nullable=True, index=True)  # Generated on first login
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    api_keys = relationship("APIKeySetting", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class APIKeySetting(Base):
    """API Key Settings model - stores encrypted API keys for external services."""
    __tablename__ = "api_key_settings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Service name: 'openai', 'anthropic', 'google', 'ollama'
    service = Column(String(50), nullable=False, index=True)
    
    # Encrypted API key (in production, use proper encryption)
    api_key = Column(Text, nullable=False)
    
    # Model name (for Ollama, specify which local model)
    model = Column(String(255), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: user can have only one key per service
    __table_args__ = (UniqueConstraint("user_id", "service", name="uq_user_service"),)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    def __repr__(self):
        return f"<APIKeySetting {self.service}>"


class Project(Base):
    """Project model - container for traces and evals."""
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: user can't have duplicate project names
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_user_project_name"),)
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    traces = relationship("Trace", back_populates="project", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")
    evals = relationship("Eval", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project {self.name}>"


class Trace(Base):
    """Trace model - represents a single LLM call or agent execution."""
    __tablename__ = "traces"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # Core trace data
    input_data = Column(JSON, nullable=True)  # User input/prompt
    output_data = Column(JSON, nullable=True)  # LLM response/result
    expected_output = Column(JSON, nullable=True)  # Golden expected output
    
    # Metadata
    model = Column(String(255), nullable=True, index=True)  # e.g., "gpt-4", "claude-3"
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    
    # Performance metrics
    total_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)  # Milliseconds
    
    # Cost tracking
    cost_usd = Column(Numeric(10, 6), nullable=True)  # Up to 6 decimal places
    
    # Status
    status = Column(String(50), default="success", index=True)  # success, error, partial
    error_message = Column(Text, nullable=True)
    
    # Nested spans/tool calls (stored as JSONB array)
    spans = Column(JSON, nullable=True, default=[])
    
    # Custom metadata
    meta = Column(JSON, nullable=True, default={})
    tags = Column(JSON, nullable=True, default=[])  # List of string tags
    environment = Column(String(50), nullable=True, index=True, default="production")  # dev, staging, production

    # Reasoning model support (o1, Claude extended thinking, etc.)
    reasoning_tokens = Column(Integer, nullable=True)   # Tokens used for internal reasoning/thinking
    thinking_content = Column(Text, nullable=True)      # Raw thinking/reasoning text (if provided)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Index for common queries
    __table_args__ = (
        Index("idx_project_timestamp", "project_id", "timestamp"),
        Index("idx_project_model", "project_id", "model"),
        Index("idx_status", "status"),
    )
    
    # Relationships
    project = relationship("Project", back_populates="traces")
    scores = relationship("Score", back_populates="trace", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Trace {self.id}>"


class Score(Base):
    """Score/Evaluation model - evaluation results for a trace."""
    __tablename__ = "scores"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    # Scorer information
    scorer_name = Column(String(255), nullable=False, index=True)
    scorer_type = Column(String(50), nullable=False)  # 'code', 'llm', 'expected', 'human'
    
    # Score value (typically 0-1)
    score_value = Column(Float, nullable=False)
    
    # Additional metadata about the score
    explanation = Column(Text, nullable=True)  # Reason from LLM scorer
    scorer_config = Column(JSON, nullable=True)  # Scorer configuration
    model_used = Column(String(255), nullable=True)  # If LLM scorer, which model?
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trace = relationship("Trace", back_populates="scores")
    project = relationship("Project")
    
    def __repr__(self):
        return f"<Score {self.scorer_name}={self.score_value}>"


class Dataset(Base):
    """Dataset model - collection of test examples."""
    __tablename__ = "datasets"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)  # Dataset versioning
    
    # Dataset source: 'manual', 'csv', 'production_trace'
    source = Column(String(50), default="manual")
    
    # Number of examples
    example_count = Column(Integer, default=0)
    
    # Dataset examples (stored as JSON array)
    # Each example: {"input": ..., "expected_output": ..., "metadata": ...}
    examples = Column(JSON, default=[])

    # Custom column schema: list of {key, label, built_in} dicts
    # built_in keys: 'input_data', 'expected_output' (renameable, not deletable)
    # custom keys: stored in DatasetItem.extra_metadata
    column_schema = Column(JSON, nullable=True, default=list)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="datasets")
    evals = relationship("Eval", back_populates="dataset")
    
    def __repr__(self):
        return f"<Dataset {self.name} v{self.version}>"


class Eval(Base):
    """Eval/Experiment model - running an evaluation against a dataset."""
    __tablename__ = "evals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Eval configuration
    scorers = Column(JSON, nullable=False)  # List of scorer configs
    task_config = Column(JSON, nullable=True)  # Task parameters
    model = Column(String(255), nullable=True)  # Model being evaluated
    
    # Results
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    total_examples = Column(Integer, default=0)
    completed_examples = Column(Integer, default=0)
    
    # Aggregated results
    avg_score = Column(Float, nullable=True)
    min_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    results = Column(JSON, nullable=True)  # Detailed results
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="evals")
    dataset = relationship("Dataset", back_populates="evals")

    def __repr__(self):
        return f"<Eval {self.name}>"


class Metric(Base):
    """Metric model — named scorer definition (built-in or custom)."""
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)  # NULL = global built-in
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    metric_type = Column(String(50), default="llm_judge")  # llm_judge, autoeval, formula, code
    prompt_template = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)          # type-specific config blob
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Metric {self.name}>"


# ---------------------------------------------------------------------------
# Phase 2: Spans (structured sub-trace data)
# ---------------------------------------------------------------------------

class Span(Base):
    """Individual span within a trace — represents one unit of work."""
    __tablename__ = "spans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    parent_span_id = Column(String(36), nullable=True, index=True)

    span_type = Column(String(50), nullable=False, default="task")  # SpanType enum values
    name = Column(String(255), nullable=False, default="span")

    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)

    # LLM-specific fields
    model = Column(String(255), nullable=True)
    temperature = Column(Float, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)

    # Timing
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)

    # Tool calls / function arguments
    tool_calls = Column(JSON, nullable=True)
    arguments = Column(JSON, nullable=True)

    status = Column(String(50), default="success")
    error_message = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True, default={})

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_spans_trace", "trace_id"),
        Index("idx_spans_project", "project_id", "span_type"),
    )

    def __repr__(self):
        return f"<Span {self.name} ({self.span_type})>"


# ---------------------------------------------------------------------------
# Phase 2: Topics (ML-powered pattern discovery)
# ---------------------------------------------------------------------------

class Topic(Base):
    """Topic cluster automatically derived from trace patterns."""
    __tablename__ = "topics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # 'task' (user intents), 'sentiment', 'issues', or custom label
    facet_type = Column(String(100), nullable=False, default="task", index=True)

    # Cluster centroid embedding (stored as list of floats)
    centroid_embedding = Column(JSON, nullable=True)

    trace_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_topics_project_facet", "project_id", "facet_type"),
    )

    assignments = relationship("TopicAssignment", back_populates="topic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Topic {self.name} ({self.facet_type})>"


class TopicAssignment(Base):
    """Many-to-many link between a Trace and a Topic."""
    __tablename__ = "topic_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    topic_id = Column(String(36), ForeignKey("topics.id"), nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("trace_id", "topic_id", name="uq_trace_topic"),
    )

    topic = relationship("Topic", back_populates="assignments")

    def __repr__(self):
        return f"<TopicAssignment trace={self.trace_id} confidence={self.confidence:.2f}>"


# ---------------------------------------------------------------------------
# Phase 2: Semantic search — embedding vectors
# ---------------------------------------------------------------------------

class TraceEmbedding(Base):
    """Cached embedding vector for a trace (for semantic search)."""
    __tablename__ = "trace_embeddings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, unique=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    # Embedding stored as JSON array; use Qdrant externally for ANN search
    embedding = Column(JSON, nullable=False)
    model_name = Column(String(255), default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TraceEmbedding trace={self.trace_id}>"


# ---------------------------------------------------------------------------
# Phase 2: Custom dashboards & alerts
# ---------------------------------------------------------------------------

class CustomDashboard(Base):
    """User-defined dashboard with configurable widgets."""
    __tablename__ = "custom_dashboards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # JSON array of widget configs: [{type, title, query, chart_type, ...}]
    widgets = Column(JSON, default=[])
    is_public = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CustomDashboard {self.name}>"


class Alert(Base):
    """Alert rule that fires when a metric crosses a threshold."""
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)
    metric = Column(String(100), nullable=False)  # e.g., 'avg_score', 'error_rate', 'latency_p99'
    condition = Column(String(20), nullable=False)  # 'lt', 'gt', 'eq'
    threshold = Column(Float, nullable=False)
    window_minutes = Column(Integer, default=60)

    webhook_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_fired_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Alert {self.name}: {self.metric} {self.condition} {self.threshold}>"


# ---------------------------------------------------------------------------
# Phase 3: Annotations & Labels
# ---------------------------------------------------------------------------

class Label(Base):
    """Project-level label definition (tag taxonomy)."""
    __tablename__ = "labels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#3B82F6")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_label_name"),
    )

    def __repr__(self):
        return f"<Label {self.name}>"


class Annotation(Base):
    """Human feedback / annotation on a specific trace."""
    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Structured feedback
    thumbs_up = Column(Boolean, nullable=True)      # simple thumbs up/down
    rating = Column(Integer, nullable=True)          # 1-5 star rating
    comment = Column(Text, nullable=True)
    label_ids = Column(JSON, default=[])             # List of Label IDs applied
    label_names = Column(JSON, default=[])           # Denormalized for fast reads
    corrected_output = Column(JSON, nullable=True)   # Human-corrected version

    # Annotation context
    annotation_type = Column(String(50), default="general")  # 'general', 'eval', 'review'
    span_id = Column(String(36), nullable=True)      # Optional: annotate a specific span

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_annotations_trace", "trace_id"),
        Index("idx_annotations_project_user", "project_id", "user_id"),
    )

    def __repr__(self):
        return f"<Annotation trace={self.trace_id} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Phase 3: Dataset items (individual rows in a dataset)
# ---------------------------------------------------------------------------

class DatasetItem(Base):
    """A single test case inside a Dataset."""
    __tablename__ = "dataset_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    # Source trace (optional, if item came from production)
    source_trace_id = Column(String(36), ForeignKey("traces.id"), nullable=True)

    input_data = Column(JSON, nullable=True)
    expected_output = Column(JSON, nullable=True)
    extra_metadata = Column("metadata", JSON, default={})
    tags = Column(JSON, default=[])

    # Split assignment: 'train', 'test', 'validation', 'all'
    split = Column(String(20), default="all")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_dataset_items_dataset", "dataset_id"),
    )

    def __repr__(self):
        return f"<DatasetItem dataset={self.dataset_id}>"


# ---------------------------------------------------------------------------
# Phase 4: Experiments (immutable eval snapshots) & Experiment results
# ---------------------------------------------------------------------------

class Experiment(Base):
    """Immutable snapshot of an evaluation run — comparable over time."""
    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    model = Column(String(255), nullable=True)

    # Task code / configuration
    task_config = Column(JSON, nullable=True)       # {model, temperature, system_prompt, ...}
    scorer_configs = Column(JSON, default=[])        # List of scorer definitions

    # Execution state
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)

    # Aggregated metrics
    aggregate_scores = Column(JSON, nullable=True)  # {scorer_name: avg_score, ...}
    summary = Column(JSON, nullable=True)           # Extended stats

    # Immutability marker — once completed, results cannot change
    is_locked = Column(Boolean, default=False)

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_experiments_project", "project_id", "created_at"),
    )

    results = relationship("ExperimentResult", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Experiment {self.name}>"


class ExperimentResult(Base):
    """One data-point result within an Experiment."""
    __tablename__ = "experiment_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=False, index=True)
    dataset_item_id = Column(String(36), ForeignKey("dataset_items.id"), nullable=True)

    input_data = Column(JSON, nullable=True)
    actual_output = Column(JSON, nullable=True)
    expected_output = Column(JSON, nullable=True)

    # Per-scorer scores: {scorer_name: {score: 0.85, reasoning: "..."}}
    scores = Column(JSON, default={})
    overall_score = Column(Float, nullable=True)

    # Execution metadata
    model = Column(String(255), nullable=True)
    latency_ms = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="results")

    def __repr__(self):
        return f"<ExperimentResult exp={self.experiment_id}>"


# ---------------------------------------------------------------------------
# Phase 4: Online scoring rules
# ---------------------------------------------------------------------------

class OnlineScoringRule(Base):
    """Rule for automatically scoring production traces as they arrive."""
    __tablename__ = "online_scoring_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    scorer_type = Column(String(50), nullable=False)    # 'llm', 'code', 'expected'
    scorer_config = Column(JSON, nullable=False)         # Scorer parameters

    # Sampling rate (0.0 – 1.0); 1.0 = score every trace
    sample_rate = Column(Float, default=1.0)

    # Optional filter: only score traces matching conditions
    filter_conditions = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<OnlineScoringRule {self.name}>"


# ---------------------------------------------------------------------------
# Phase 5: Prompts & Deployments
# ---------------------------------------------------------------------------

class Prompt(Base):
    """Named, versioned prompt stored in the registry."""
    __tablename__ = "prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # Template with {{variable}} placeholders
    template = Column(Text, nullable=False)
    # JSON object listing variable names and their types/defaults
    variables = Column(JSON, default={})
    # Default model parameters
    default_model = Column(String(255), nullable=True)
    default_params = Column(JSON, default={})

    latest_version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_prompt_name"),
    )

    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    deployments = relationship("PromptDeployment", back_populates="prompt", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prompt {self.name} v{self.latest_version}>"


class PromptVersion(Base):
    """Immutable snapshot of a prompt at a specific version number."""
    __tablename__ = "prompt_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    prompt_id = Column(String(36), ForeignKey("prompts.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)

    template = Column(Text, nullable=False)
    variables = Column(JSON, default={})
    model = Column(String(255), nullable=True)
    params = Column(JSON, default={})
    commit_message = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("prompt_id", "version_number", name="uq_prompt_version"),
    )

    prompt = relationship("Prompt", back_populates="versions")

    def __repr__(self):
        return f"<PromptVersion {self.prompt_id} v{self.version_number}>"


class PromptDeployment(Base):
    """Active deployment of a specific prompt version to an environment."""
    __tablename__ = "prompt_deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    prompt_id = Column(String(36), ForeignKey("prompts.id"), nullable=False, index=True)
    prompt_version_id = Column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    environment = Column(String(50), nullable=False, default="production")  # production, staging, dev
    status = Column(String(30), default="active")   # active, inactive, rolled_back
    deployed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    deployed_at = Column(DateTime, default=datetime.utcnow)
    retired_at = Column(DateTime, nullable=True)

    prompt = relationship("Prompt", back_populates="deployments")

    def __repr__(self):
        return f"<PromptDeployment prompt={self.prompt_id} env={self.environment}>"


# ---------------------------------------------------------------------------
# Phase 5: Gateway — LLM request routing & cost tracking
# ---------------------------------------------------------------------------

class GatewayRequest(Base):
    """Log of every request routed through the TraceIQ Gateway."""
    __tablename__ = "gateway_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    provider = Column(String(50), nullable=False)           # 'openai', 'anthropic', etc.
    model = Column(String(255), nullable=False)
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)
    latency_ms = Column(Float, nullable=True)

    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Cache hit tracking
    cache_hit = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_gateway_project_created", "project_id", "created_at"),
    )

    def __repr__(self):
        return f"<GatewayRequest {self.provider}/{self.model}>"


class ABTest(Base):
    """A/B test comparing two or more prompt/model configurations."""
    __tablename__ = "ab_tests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Variants: [{name, prompt_id, model, weight}, ...]
    variants = Column(JSON, nullable=False)

    status = Column(String(30), default="running")  # running, paused, completed
    winner_variant = Column(String(255), nullable=True)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ABTest {self.name}>"


# ---------------------------------------------------------------------------
# Phase 6: RBAC — Organizations, Teams, Roles
# ---------------------------------------------------------------------------

class Organization(Base):
    """Top-level tenant (company or workspace)."""
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Quotas
    max_traces_per_month = Column(Integer, nullable=True)
    max_projects = Column(Integer, nullable=True)
    max_members = Column(Integer, nullable=True)

    plan = Column(String(50), default="free")  # free, pro, enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organization {self.name}>"


class OrganizationMember(Base):
    """Membership record linking a user to an organization with a role."""
    __tablename__ = "organization_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="viewer")  # RoleEnum values

    invited_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    invited_at = Column(DateTime, default=datetime.utcnow)
    joined_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    organization = relationship("Organization", back_populates="members")

    def __repr__(self):
        return f"<OrgMember user={self.user_id} role={self.role}>"


class Team(Base):
    """Sub-group within an organization for project access control."""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_team_name"),
    )

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team {self.name}>"


class TeamMember(Base):
    """User membership in a Team."""
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), default="member")

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    team = relationship("Team", back_populates="members")

    def __repr__(self):
        return f"<TeamMember user={self.user_id}>"


class ProjectMember(Base):
    """Direct user access to a Project (outside team membership)."""
    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="viewer")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    def __repr__(self):
        return f"<ProjectMember project={self.project_id} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Phase 6: Audit Logging
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Append-only audit trail for every significant user action."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(String(36), nullable=True, index=True)

    action = Column(String(100), nullable=False, index=True)   # e.g., 'trace.create', 'eval.delete'
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)

    # Snapshot of relevant data (before/after for mutating ops)
    extra_metadata = Column("metadata", JSON, nullable=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_action_created", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Phase 6: Usage Metrics (for billing / quota enforcement)
# ---------------------------------------------------------------------------

class UsageMetric(Base):
    """Aggregated daily usage per organization for quota tracking."""
    __tablename__ = "usage_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    date = Column(DateTime, nullable=False, index=True)

    traces_count = Column(Integer, default=0)
    spans_count = Column(Integer, default=0)
    evals_count = Column(Integer, default=0)
    annotations_count = Column(Integer, default=0)
    gateway_requests_count = Column(Integer, default=0)

    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Numeric(12, 6), default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "date", name="uq_usage_org_project_date"),
    )

    def __repr__(self):
        return f"<UsageMetric {self.date} org={self.organization_id}>"


# ---------------------------------------------------------------------------
# Phase 2: Remote Evals — sandbox execution of user-supplied eval code
# ---------------------------------------------------------------------------

class RemoteEval(Base):
    """
    A Remote Eval job — user submits eval code + dataset, we run it in a
    sandboxed subprocess and store the results.
    """
    __tablename__ = "remote_evals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # User-supplied Python scorer code (executed in sandbox)
    scorer_code = Column(Text, nullable=False)

    # Input data rows: [{input, expected, metadata?}, ...]
    input_rows = Column(JSON, nullable=False, default=[])

    # Response schema for validation (JSON Schema dict, optional)
    response_schema = Column(JSON, nullable=True)

    # Execution state
    status = Column(String(50), default="pending")   # pending, running, completed, failed, cancelled
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)

    # Results: [{input, output, score, passed, error?, reasoning?}, ...]
    results = Column(JSON, nullable=True)
    aggregate = Column(JSON, nullable=True)   # {avg_score, pass_rate, errors}

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_remote_evals_project", "project_id", "created_at"),
    )

    def __repr__(self):
        return f"<RemoteEval {self.name} status={self.status}>"


# ---------------------------------------------------------------------------
# Phase 3: Enterprise — SSO, Alerts, Data Masking
# ---------------------------------------------------------------------------

class SSOConfig(Base):
    """OIDC/SAML SSO configuration for an organization."""
    __tablename__ = "sso_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Common fields
    provider_type = Column(String(30), nullable=False, default="oidc")  # "oidc" | "saml"
    is_enabled = Column(Boolean, default=False)

    # OIDC fields
    oidc_issuer_url = Column(Text, nullable=True)        # e.g. https://accounts.google.com
    oidc_client_id = Column(Text, nullable=True)
    oidc_client_secret = Column(Text, nullable=True)     # stored encrypted in production
    oidc_scopes = Column(JSON, default=["openid", "email", "profile"])
    oidc_redirect_uri = Column(Text, nullable=True)      # callback URL

    # SAML fields
    saml_idp_metadata_url = Column(Text, nullable=True)
    saml_idp_entity_id = Column(Text, nullable=True)
    saml_idp_sso_url = Column(Text, nullable=True)
    saml_idp_certificate = Column(Text, nullable=True)
    saml_sp_entity_id = Column(Text, nullable=True)     # Our entity ID

    # Domain-based auto-provisioning
    allowed_domains = Column(JSON, default=[])           # ["acme.com", "acme.io"]
    auto_provision_users = Column(Boolean, default=True) # Create users on first SSO login
    default_role = Column(String(30), default="viewer")  # Role granted to new SSO users

    # State for OIDC PKCE / nonce
    last_nonce = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SSOConfig org={self.organization_id} type={self.provider_type}>"


class AlertChannel(Base):
    """
    Delivery channel for alerts — Slack webhook, email, or generic webhook.
    Multiple channels can be attached to a single Alert rule.
    """
    __tablename__ = "alert_channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    channel_type = Column(String(30), nullable=False)   # "slack" | "email" | "webhook"

    # Slack: webhook URL
    slack_webhook_url = Column(Text, nullable=True)
    slack_channel = Column(String(100), nullable=True)   # e.g. "#alerts" (informational)

    # Email: comma-separated recipients
    email_recipients = Column(Text, nullable=True)

    # Generic webhook: URL + optional secret
    webhook_url = Column(Text, nullable=True)
    webhook_secret = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AlertChannel {self.name} type={self.channel_type}>"


class AlertRule(Base):
    """Enhanced alert rule that routes to one or more AlertChannels."""
    __tablename__ = "alert_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Metric to monitor
    metric = Column(String(100), nullable=False)   # error_rate, avg_score, latency_p99, cost_usd
    condition = Column(String(10), nullable=False)  # gt, lt, gte, lte, eq
    threshold = Column(Float, nullable=False)
    window_minutes = Column(Integer, default=60)

    # Delivery channels (list of AlertChannel IDs)
    channel_ids = Column(JSON, default=[])

    # Cooldown to prevent alert storms
    cooldown_minutes = Column(Integer, default=30)

    is_active = Column(Boolean, default=True)
    last_fired_at = Column(DateTime, nullable=True)
    last_value = Column(Float, nullable=True)       # Last observed metric value

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_alert_rules_project", "project_id"),
    )

    def __repr__(self):
        return f"<AlertRule {self.name}: {self.metric} {self.condition} {self.threshold}>"


class EmailConfig(Base):
    """SMTP email configuration for an organization."""
    __tablename__ = "email_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(Text, nullable=True)      # stored encrypted in production
    smtp_use_tls = Column(Boolean, default=True)
    from_address = Column(String(255), nullable=False)
    from_name = Column(String(255), default="TraceIQ Alerts")

    is_active = Column(Boolean, default=True)
    last_tested_at = Column(DateTime, nullable=True)
    last_test_result = Column(String(20), nullable=True)   # "ok" | "error"
    last_test_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EmailConfig org={self.organization_id} host={self.smtp_host}>"


class MaskingRule(Base):
    """
    PII / data masking rule for a project.

    When a trace is ingested its input/output JSON is scanned for matching
    field names or regex patterns; matching values are replaced with the
    configured mask token before storage.
    """
    __tablename__ = "masking_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)

    # Match strategy
    match_type = Column(String(20), nullable=False, default="field_name")
    # "field_name"  — exact key match (e.g. "email", "ssn")
    # "regex"       — value matches a regex pattern
    # "builtin"     — use a built-in PII detector (email, phone, credit_card, ssn)

    match_value = Column(String(500), nullable=True)     # key name or regex pattern
    builtin_type = Column(String(50), nullable=True)     # "email" | "phone" | "credit_card" | "ssn"

    # Masking action
    mask_action = Column(String(20), default="redact")
    # "redact"   — replace with [REDACTED]
    # "hash"     — replace with sha256 hash
    # "partial"  — show first/last chars only

    mask_token = Column(String(100), default="[REDACTED]")

    # Which parts of the trace to apply to
    apply_to = Column(JSON, default=["input_data", "output_data"])

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_masking_rules_project", "project_id"),
    )

    def __repr__(self):
        return f"<MaskingRule {self.name} type={self.match_type}>"



# ---------------------------------------------------------------------------
# Phase 5: Webhooks & Integrations
# ---------------------------------------------------------------------------

class WebhookConfig(Base):
    """Outbound webhook registered for a project event."""
    __tablename__ = "webhook_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(String(255), nullable=True)          # HMAC signing secret
    # Events to subscribe: ['trace.created', 'eval.completed', 'alert.fired']
    events = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WebhookConfig {self.name}>"


# ---------------------------------------------------------------------------
# Environments — dev / staging / production separation
# ---------------------------------------------------------------------------

class Environment(Base):
    """Named deployment environment (e.g. dev, staging, production)."""
    __tablename__ = "environments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    name = Column(String(100), nullable=False)          # 'production', 'staging', 'dev', etc.
    slug = Column(String(100), nullable=False)           # URL-safe identifier
    description = Column(Text, nullable=True)

    is_production = Column(Boolean, default=False)      # Marks the canonical production env
    is_active = Column(Boolean, default=True)

    # Arbitrary env-var overrides stored as {key: value}
    config = Column(JSON, default={})

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_project_env_slug"),
    )

    def __repr__(self):
        return f"<Environment {self.name} (project={self.project_id})>"


class ModelPricing(Base):
    """
    Per-user custom model pricing overrides.

    When a user sets custom rates for a model (e.g. because they have a
    negotiated contract price), those rates take precedence over the global
    defaults in backend/pricing.py at trace-ingest time.
    """
    __tablename__ = "model_pricing"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    model = Column(String(255), nullable=False)                  # e.g. "gpt-4o"
    provider = Column(String(100), nullable=True)                # e.g. "openai"
    prompt_cost_per_1k = Column(Numeric(12, 8), nullable=False)  # USD / 1k prompt tokens
    completion_cost_per_1k = Column(Numeric(12, 8), nullable=False)  # USD / 1k completion tokens
    is_free = Column(Boolean, default=False)                     # local/Ollama shortcut
    notes = Column(Text, nullable=True)                          # e.g. "Negotiated rate"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "model", name="uq_user_model_pricing"),
    )

    def __repr__(self):
        return f"<ModelPricing {self.model} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Showcase: Human Review Queue
# ---------------------------------------------------------------------------

class ReviewTask(Base):
    """A trace flagged for human review — supports the Human Review Queue."""
    __tablename__ = "review_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), default="medium")          # critical, high, medium, low
    status = Column(String(30), default="pending")           # pending, in_review, approved, rejected, escalated
    reason = Column(String(100), nullable=True)              # Why flagged: low_score, anomaly, manual, policy
    notes = Column(Text, nullable=True)                      # Reviewer notes

    # Score snapshot at flagging time
    score_at_flagging = Column(Float, nullable=True)
    threshold_violated = Column(String(100), nullable=True)  # Which scorer triggered flag

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_review_tasks_project_status", "project_id", "status"),
    )

    def __repr__(self):
        return f"<ReviewTask {self.id} status={self.status}>"

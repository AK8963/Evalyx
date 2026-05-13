// ─────────────────────────────────────────────
// Auth
// ─────────────────────────────────────────────
export interface AuthResponse {
  access_token: string
  token_type: string
  message?: string
}

export interface User {
  id: string
  email: string
  name: string
  api_key?: string
  created_at: string
}

// ─────────────────────────────────────────────
// Projects
// ─────────────────────────────────────────────
export interface Project {
  id: string
  name: string
  description?: string
  created_at: string
  trace_count?: number
}

// ─────────────────────────────────────────────
// Traces
// ─────────────────────────────────────────────
export type TraceStatus = 'success' | 'error' | 'pending'

export interface Trace {
  id: string
  project_id: string
  model?: string
  status: TraceStatus
  input_data?: Record<string, unknown>
  output_data?: Record<string, unknown>
  metadata?: Record<string, unknown>
  latency_ms?: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cost_usd?: number
  error_message?: string
  environment?: string
  tags?: string[]
  timestamp?: string
  created_at?: string
  scores?: Score[]
}

export interface TraceListParams {
  project_id: string
  model?: string
  status?: string
  limit?: number
  offset?: number
  search?: string
}

// ─────────────────────────────────────────────
// Scores / Evals
// ─────────────────────────────────────────────
export interface Score {
  id: string
  trace_id: string
  scorer_type: string
  score: number
  reasoning?: string
  created_at: string
}

export interface Scorer {
  type: 'llm' | 'code' | 'expected' | 'semantic' | 'regex' | 'custom'
  name: string
  prompt?: string
  code?: string
  expected?: string
  threshold?: number
}

export interface Eval {
  id: string
  project_id: string
  name: string
  description?: string
  scorers: Scorer[]
  dataset_id?: string
  trace_id?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  results?: Record<string, unknown>
  created_at: string
}

// ─────────────────────────────────────────────
// Experiments
// ─────────────────────────────────────────────
export interface Experiment {
  id: string
  project_id: string
  name: string
  description?: string
  status: 'draft' | 'running' | 'completed'
  config?: Record<string, unknown>
  metrics?: Record<string, number>
  created_at: string
}

// ─────────────────────────────────────────────
// Datasets
// ─────────────────────────────────────────────
export interface Dataset {
  id: string
  project_id: string
  name: string
  description?: string
  version: number
  item_count?: number
  created_at: string
}

export interface DatasetItem {
  id: string
  dataset_id: string
  input_data: Record<string, unknown>
  expected_output?: Record<string, unknown>
  metadata?: Record<string, unknown>
  created_at: string
}

// ─────────────────────────────────────────────
// Annotations
// ─────────────────────────────────────────────
export type AnnotationType = 'thumbs_up' | 'thumbs_down' | 'rating' | 'label' | 'comment'

export interface Annotation {
  id: string
  trace_id: string
  project_id: string
  annotation_type: AnnotationType
  rating?: number
  label?: string
  comment?: string
  annotator_id?: string
  created_at: string
}

// ─────────────────────────────────────────────
// Prompts
// ─────────────────────────────────────────────
export interface Prompt {
  id: string
  project_id: string
  name: string
  description?: string
  template: string
  variables?: string[]
  version: number
  is_deployed: boolean
  model?: string
  model_params?: Record<string, unknown>
  created_at: string
}

// ─────────────────────────────────────────────
// Gateway
// ─────────────────────────────────────────────
export interface GatewayRequest {
  project_id: string
  model: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
  stream?: boolean
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface GatewayResponse {
  id: string
  model: string
  content: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  latency_ms: number
}

// ─────────────────────────────────────────────
// Analytics
// ─────────────────────────────────────────────
export interface AnalyticsSummary {
  total_traces: number
  error_traces: number
  error_rate: number
  avg_latency_ms: number
  total_cost_usd: number
  total_tokens: number
  days: number
  // optional enriched fields
  success_rate?: number
  error_count?: number
  traces_by_model?: Record<string, number>
  traces_by_status?: Record<string, number>
}

export interface TimeSeriesPoint {
  timestamp: string
  value: number
}

// ─────────────────────────────────────────────
// Settings
// ─────────────────────────────────────────────
export interface Settings {
  openai_api_key?: string
  anthropic_api_key?: string
  google_api_key?: string
  ollama_base_url?: string
  default_model?: string
  rate_limit_per_minute?: number
  data_retention_days?: number
  webhook_url?: string
}

// ─────────────────────────────────────────────
// Alerts
// ─────────────────────────────────────────────
export interface Alert {
  id: string
  project_id: string
  name: string
  condition: string
  threshold: number
  channel: 'email' | 'webhook' | 'slack'
  is_active: boolean
  created_at: string
}

// ─────────────────────────────────────────────
// Topics
// ─────────────────────────────────────────────
export interface Topic {
  id: string
  project_id: string
  name: string
  description?: string
  trace_count: number
  keywords?: string[]
  created_at: string
}

// ─────────────────────────────────────────────
// Review
// ─────────────────────────────────────────────
export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'needs_revision'
export type ReviewPriority = 'low' | 'medium' | 'high' | 'critical'

export interface ReviewItem {
  id: string
  trace_id: string
  project_id: string
  status: ReviewStatus
  priority: ReviewPriority
  reviewer_id?: string
  notes?: string
  auto_flagged: boolean
  flag_reason?: string
  created_at: string
  trace?: Trace
}

// ─────────────────────────────────────────────
// Pagination
// ─────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

// ─────────────────────────────────────────────
// BTQL
// ─────────────────────────────────────────────
export interface BTQLResult {
  columns: string[]
  rows: unknown[][]
  total_rows: number
  execution_time_ms: number
}

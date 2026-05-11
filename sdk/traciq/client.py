"""
Python SDK for TraceIQ - trace ingestion client.
"""

import logging
from typing import Optional, Any, Dict, List, Callable
from datetime import datetime
import time
import threading
from queue import Queue
import httpx
from dataclasses import dataclass, asdict
import uuid
import json

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Nested span/tool call within a trace."""
    name: str
    input: Optional[Any] = None
    output: Optional[Any] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metadata: Optional[Dict] = None


@dataclass
class Trace:
    """Trace data structure."""
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    expected_output: Optional[Any] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None
    spans: Optional[List[Span]] = None
    metadata: Optional[Dict] = None
    tags: Optional[List[str]] = None
    timestamp: Optional[datetime] = None
    id: str = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self):
        """Convert to dictionary for API transmission."""
        data = asdict(self)
        # Convert spans to dicts
        if data.get("spans"):
            data["spans"] = [asdict(s) for s in data["spans"]]
        # Convert datetime to ISO string
        if data.get("timestamp"):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class TraceIQClient:
    """Main client for sending traces to TraceIQ backend."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        batch_size: int = 100,
        batch_timeout_ms: int = 5000
    ):
        """
        Initialize TraceIQ client.
        
        Args:
            api_key: TraceIQ API key
            base_url: Backend URL (default: localhost:8000)
            batch_size: Number of traces to batch before sending
            batch_timeout_ms: Max time to wait before flushing batch
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms / 1000.0  # Convert to seconds
        
        self.http_client = httpx.Client()
        self.batch_queue: Queue[Trace] = Queue()
        self.lock = threading.Lock()
        
        # Start background batch sender
        self.stop_event = threading.Event()
        self.sender_thread = threading.Thread(
            target=self._batch_sender_loop,
            daemon=True
        )
        self.sender_thread.start()
        
        logger.info(f"TraceIQ client initialized: {base_url}")
    
    def trace(
        self,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        expected_output: Optional[Any] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[float] = None,
        spans: Optional[List[Span]] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Create and queue a trace for sending.

        Provide either ``project_name`` (human-readable) or ``project_id`` (UUID).

        Returns:
            trace_id
        """
        if not project_name and not project_id:
            raise ValueError("Provide either project_name or project_id")
        trace = Trace(
            project_id=project_id,
            project_name=project_name,
            input_data=input_data,
            output_data=output_data,
            expected_output=expected_output,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            total_tokens=total_tokens,
            completion_tokens=completion_tokens,
            prompt_tokens=prompt_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            spans=spans,
            metadata=metadata,
            tags=tags
        )
        
        # Queue trace for batching
        self.batch_queue.put(trace)
        
        # Check if we should flush immediately
        if self.batch_queue.qsize() >= self.batch_size:
            self.flush()
        
        return trace.id
    
    def _batch_sender_loop(self):
        """Background thread that periodically flushes batches."""
        last_flush = time.time()
        
        while not self.stop_event.is_set():
            time.sleep(0.1)  # Check every 100ms
            
            # Flush if timeout reached or batch full
            elapsed = time.time() - last_flush
            queue_size = self.batch_queue.qsize()
            
            should_flush = (
                (elapsed >= self.batch_timeout_ms and queue_size > 0) or
                queue_size >= self.batch_size
            )
            
            if should_flush:
                self._flush_batch()
                last_flush = time.time()
    
    def _flush_batch(self):
        """Flush queued traces to backend."""
        traces = []
        
        with self.lock:
            while not self.batch_queue.empty() and len(traces) < self.batch_size:
                try:
                    traces.append(self.batch_queue.get_nowait())
                except:
                    break
        
        if not traces:
            return
        
        try:
            self._send_traces_to_backend(traces)
        except Exception as e:
            logger.error(f"Error sending traces: {e}")
            # Re-queue failed traces (simple retry)
            for trace in traces:
                self.batch_queue.put(trace)
    
    def _send_traces_to_backend(self, traces: List[Trace]):
        """Send traces to backend API using the /ingest endpoint."""
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

        # Send each trace individually via /ingest so the server can resolve
        # project_name → project_id and handle missing fields gracefully.
        for t in traces:
            url = f"{self.base_url}/api/traces/ingest"
            payload = t.to_dict()
            # Remove None values to keep payload clean
            payload = {k: v for k, v in payload.items() if v is not None}

            response = self.http_client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )

            if response.status_code not in [200, 201]:
                logger.error(
                    f"Failed to send trace: {response.status_code} - {response.text}"
                )
                raise Exception(f"Backend returned {response.status_code}: {response.text}")

        logger.debug(f"Sent {len(traces)} trace(s) to backend")
    
    def flush(self):
        """Manually flush any pending traces."""
        self._flush_batch()
    
    def close(self):
        """Close client and clean up resources."""
        self.flush()
        self.stop_event.set()
        self.sender_thread.join(timeout=5)
        self.http_client.close()
        logger.info("TraceIQ client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global client instance (optional)
_global_client: Optional[TraceIQClient] = None


def init(api_key: str, base_url: str = "http://localhost:8000"):
    """
    Initialize global TraceIQ client.
    
    Usage:
        traciq.init(api_key="your_api_key")
        trace_id = traciq.trace(...)
    """
    global _global_client
    _global_client = TraceIQClient(api_key, base_url)


def trace(
    project_id: str,
    input_data: Optional[Any] = None,
    output_data: Optional[Any] = None,
    expected_output: Optional[Any] = None,
    **kwargs
) -> str:
    """Record a trace using global client."""
    if _global_client is None:
        raise RuntimeError("Client not initialized. Call traciq.init() first.")
    
    return _global_client.trace(project_id, input_data, output_data, expected_output, **kwargs)


def flush():
    """Flush pending traces."""
    if _global_client:
        _global_client.flush()


def close():
    """Close global client."""
    if _global_client:
        _global_client.close()

"""
Decorator and context manager for tracing.
"""

import functools
import time
from typing import Callable, Optional, Any, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def traciq_trace(
    project_id: str,
    model: Optional[str] = None,
    tags: Optional[list] = None,
    metadata: Optional[dict] = None
):
    """
    Decorator to automatically trace function calls.
    
    Usage:
        @traciq_trace(project_id="my_project", model="gpt-4")
        def my_llm_function(prompt):
            ...
            return response
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            from .client import _global_client
            
            if not _global_client:
                logger.warning("TraceIQ client not initialized")
                return func(*args, **kwargs)
            
            # Capture inputs
            input_data = {
                "args": args,
                "kwargs": kwargs,
                "function": func.__name__
            }
            
            start_time = time.time()
            start_ms = start_time * 1000
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Capture outputs
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                # Send trace
                _global_client.trace(
                    project_id=project_id,
                    input_data=input_data,
                    output_data=result,
                    model=model,
                    latency_ms=latency_ms,
                    tags=tags or [],
                    metadata=metadata or {},
                    status="success"
                )
                
                return result
                
            except Exception as e:
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                # Send error trace
                _global_client.trace(
                    project_id=project_id,
                    input_data=input_data,
                    model=model,
                    latency_ms=latency_ms,
                    tags=tags or [],
                    metadata=metadata or {},
                    status="error",
                    error_message=str(e)
                )
                
                raise
        
        return wrapper
    
    return decorator


class TraceContext:
    """Context manager for tracing code blocks."""
    
    def __init__(
        self,
        project_id: str,
        name: str = "traced_block",
        input_data: Optional[Any] = None,
        model: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[dict] = None
    ):
        """
        Initialize trace context.
        
        Usage:
            with TraceContext(project_id="my_project", name="api_call") as ctx:
                result = call_api()
                ctx.set_output(result)
        """
        self.project_id = project_id
        self.name = name
        self.input_data = input_data
        self.model = model
        self.tags = tags or []
        self.metadata = metadata or {}
        
        self.start_time = None
        self.output_data = None
        self.status = "success"
        self.error_message = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def set_output(self, output_data: Any):
        """Set output data for trace."""
        self.output_data = output_data
    
    def set_error(self, error: Exception):
        """Mark trace as error."""
        self.status = "error"
        self.error_message = str(error)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        from traciq.client import _global_client
        
        if not _global_client:
            logger.warning("TraceIQ client not initialized")
            return
        
        end_time = time.time()
        latency_ms = (end_time - self.start_time) * 1000
        
        status = "error" if exc_type else self.status
        error_msg = None
        if exc_val:
            error_msg = str(exc_val)
        else:
            error_msg = self.error_message
        
        _global_client.trace(
            project_id=self.project_id,
            input_data=self.input_data,
            output_data=self.output_data,
            model=self.model,
            latency_ms=latency_ms,
            tags=self.tags,
            metadata=self.metadata,
            status=status,
            error_message=error_msg
        )
        
        return False  # Re-raise exception if any

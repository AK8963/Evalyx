"""
How to use this TraceIQ platform from another Python application
====================================================================

Step 1 — Install the SDK (run once):
    pip install -e /path/to/this/sdk/folder

Step 2 — Get your API key from the Settings page at http://localhost:8501
    (Navigate to ⚙️ Settings → "Your TraceIQ API Key")

Step 3 — Use any of the examples below in your own app.
"""

import sys
import os
import time

# If you have NOT installed with pip, uncomment this line so Python finds the SDK:
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sdk"))

import traciq
import httpx

# ─────────────────────────────────────────────────
# YOUR CREDENTIALS  (copy from Settings page)
# ─────────────────────────────────────────────────
LOGIN_EMAIL  = "abc@gmail.com"
BASE_URL     = "http://localhost:8000"
PROJECT_NAME = "test_project"

# Auto-fetch the static API key (avoids stale hardcoded keys)
def _get_api_key() -> str:
    jwt = httpx.post(f"{BASE_URL}/api/auth/login", json={"email": LOGIN_EMAIL}, timeout=10).json()["access_token"]
    return httpx.get(f"{BASE_URL}/api/auth/api-key", headers={"Authorization": f"Bearer {jwt}"}, timeout=10).json()["api_key"]

API_KEY = _get_api_key()


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE 1 — Single trace (simplest usage)
# ══════════════════════════════════════════════════════════════════════════════
def example_1_single_trace():
    print("\n=== Example 1: Single trace ===")

    client = traciq.init(api_key=API_KEY, base_url=BASE_URL)

    trace_id = client.trace(
        project_name=PROJECT_NAME,
        model="gpt-4o",
        input_data={"prompt": "What is 2 + 2?"},
        output_data={"response": "4"},
        latency_ms=180,
        total_tokens=20,
        prompt_tokens=8,
        completion_tokens=12,
    )

    client.flush()          # send immediately (otherwise batches every 5 s)
    client.close()
    print(f"✅ Trace sent  id={trace_id}")


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE 2 — Measuring real latency around your LLM call
# ══════════════════════════════════════════════════════════════════════════════
def example_2_real_latency():
    print("\n=== Example 2: Measuring real latency ===")

    client = traciq.init(api_key=API_KEY, base_url=BASE_URL)

    # ── your actual LLM code goes here ──────────────────────────────
    t0 = time.time()

    # e.g.: response = openai_client.chat.completions.create(...)
    # Simulating a 300 ms call:
    time.sleep(0.3)
    response_text = "Paris"          # replace with real response
    tokens_used   = 42               # replace with response.usage.total_tokens

    latency = (time.time() - t0) * 1000
    # ────────────────────────────────────────────────────────────────

    client.trace(
        project_name=PROJECT_NAME,
        model="gpt-4o",
        input_data={"question": "What is the capital of France?"},
        output_data={"answer": response_text},
        expected_output={"answer": "Paris"},   # optional golden answer
        latency_ms=latency,
        total_tokens=tokens_used,
        tags=["geography", "qa"],
        metadata={"experiment": "v2"},
    )

    client.flush()
    client.close()
    print(f"✅ Trace sent  latency={latency:.0f} ms")


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE 3 — Context manager (auto-close)
# ══════════════════════════════════════════════════════════════════════════════
def example_3_context_manager():
    print("\n=== Example 3: Context manager ===")

    with traciq.TraceIQClient(api_key=API_KEY, base_url=BASE_URL) as client:
        client.trace(
            project_name=PROJECT_NAME,
            model="claude-3-5-sonnet",
            input_data={"prompt": "Summarise this text in one sentence."},
            output_data={"summary": "A short summary."},
            latency_ms=450,
            total_tokens=200,
        )
        # flush + close happen automatically on __exit__

    print("✅ Done — client closed automatically")


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE 4 — Batch: send many traces (e.g. offline evaluation)
# ══════════════════════════════════════════════════════════════════════════════
def example_4_batch():
    print("\n=== Example 4: Batch tracing ===")

    dataset = [
        {"q": "What is 1+1?",        "a": "2",     "expected": "2"},
        {"q": "Capital of Japan?",    "a": "Tokyo", "expected": "Tokyo"},
        {"q": "Who wrote Hamlet?",    "a": "Shakespeare", "expected": "Shakespeare"},
    ]

    client = traciq.init(api_key=API_KEY, base_url=BASE_URL)

    for row in dataset:
        correct = row["a"].lower() == row["expected"].lower()
        client.trace(
            project_name=PROJECT_NAME,
            model="gpt-4o-mini",
            input_data={"question": row["q"]},
            output_data={"answer": row["a"]},
            expected_output={"answer": row["expected"]},
            latency_ms=120,
            total_tokens=30,
            metadata={"correct": correct},
            tags=["batch-eval"],
        )

    client.flush()
    client.close()
    print(f"✅ Sent {len(dataset)} traces")


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE 5 — Using the @traciq_trace decorator
#              (auto-traces any function that calls your LLM)
# ══════════════════════════════════════════════════════════════════════════════
def example_5_decorator():
    print("\n=== Example 5: Decorator ===")

    # Must call init() first so the global client is set
    traciq.init(api_key=API_KEY, base_url=BASE_URL)

    @traciq.traciq_trace(project_id=PROJECT_NAME, model="gpt-4o")
    def call_llm(prompt: str) -> str:
        """Any function decorated with @traciq_trace is auto-traced."""
        time.sleep(0.1)          # simulating LLM latency
        return f"Answer to: {prompt}"

    result = call_llm("What is deep learning?")
    print(f"✅ Function returned: {result}")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    example_1_single_trace()
    example_2_real_latency()
    example_3_context_manager()
    example_4_batch()
    # example_5_decorator()   # needs global init — uncomment to test
    print("\n🎉 All examples finished.  Open http://localhost:8501 → Traces to see results.")



def example_1_basic_tracing():
    """Example 1: Basic trace collection."""
    print("\n=== Example 1: Basic Tracing ===")
    
    # Initialize
    traciq.init(api_key="test_api_key_12345")
    
    # Record a trace manually
    trace_id = traciq.trace(
        project_id="demo_project",
        input_data={"question": "What is AI?"},
        output_data={"answer": "AI is artificial intelligence..."},
        model="gpt-4",
        latency_ms=250.5,
        total_tokens=150,
        completion_tokens=50,
        prompt_tokens=100,
        cost_usd=0.0015,
        tags=["demo", "qa"],
        metadata={"source": "example"}
    )
    
    print(f"✅ Trace created: {trace_id}")
    
    # Flush to send immediately
    traciq.flush()
    print("✅ Traces flushed to backend")


def example_2_decorator():
    """Example 2: Using decorator for automatic tracing."""
    print("\n=== Example 2: Decorator-based Tracing ===")
    
    traciq.init(api_key="test_api_key_12345")
    
    @traciq.traciq_trace(
        project_id="demo_project",
        model="gpt-4",
        tags=["sentiment_analysis"]
    )
    def analyze_sentiment(text: str) -> dict:
        """Analyze sentiment of text (simulated)."""
        # In real app, would call OpenAI/Claude/etc
        sentiment = "positive" if len(text) > 5 else "neutral"
        score = 0.8 if sentiment == "positive" else 0.5
        
        return {
            "text": text,
            "sentiment": sentiment,
            "score": score
        }
    
    # Use function normally - tracing happens automatically
    result = analyze_sentiment("This product is amazing and I love it!")
    print(f"✅ Result: {result}")
    
    # Flush to send
    traciq.flush()
    print("✅ Traces with decorators flushed")


def example_3_context_manager():
    """Example 3: Using context manager for block tracing."""
    print("\n=== Example 3: Context Manager Tracing ===")
    
    traciq.init(api_key="test_api_key_12345")
    
    # Example with context manager
    with traciq.TraceContext(
        project_id="demo_project",
        name="database_query",
        input_data={"query": "SELECT * FROM users"},
        metadata={"operation": "read"}
    ) as ctx:
        # Simulate database query
        result = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        ctx.set_output(result)
        print(f"✅ Query result: {len(result)} rows")
    
    print("✅ Context manager trace sent")


def example_4_batch_tracing():
    """Example 4: Batch multiple traces."""
    print("\n=== Example 4: Batch Tracing ===")
    
    traciq.init(api_key="test_api_key_12345")
    
    # Simulate batch processing
    inputs = [
        "What is machine learning?",
        "Explain neural networks",
        "What is deep learning?"
    ]
    
    for i, question in enumerate(inputs):
        trace_id = traciq.trace(
            project_id="demo_project",
            input_data={"question": question},
            output_data={"answer": f"Answer to: {question}"},
            model="gpt-4",
            latency_ms=100 + i * 50,
            tags=["batch", "qa"],
            metadata={"batch_id": "batch_001", "index": i}
        )
        print(f"✅ Trace {i+1}: {trace_id[:8]}...")
    
    # Flush all at once
    traciq.flush()
    print(f"✅ Flushed {len(inputs)} traces")


def example_5_error_handling():
    """Example 5: Tracing with error handling."""
    print("\n=== Example 5: Error Handling ===")
    
    traciq.init(api_key="test_api_key_12345")
    
    @traciq.traciq_trace(
        project_id="demo_project",
        model="gpt-4",
        tags=["error_handling"]
    )
    def risky_operation(should_fail: bool = False):
        """Operation that might fail."""
        if should_fail:
            raise ValueError("Simulated error for demonstration")
        return "Success!"
    
    # Successful case
    try:
        result = risky_operation(should_fail=False)
        print(f"✅ Success: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Error case - trace will mark as error
    try:
        result = risky_operation(should_fail=True)
    except ValueError as e:
        print(f"✅ Error traced: {e}")
    
    traciq.flush()


def example_6_with_statement():
    """Example 6: Using client as context manager."""
    print("\n=== Example 6: Client Context Manager ===")
    
    with traciq.TraceIQClient(
        api_key="test_api_key_12345",
        base_url="http://localhost:8000"
    ) as client:
        # Traces are automatically flushed on exit
        trace_id = client.trace(
            project_id="demo_project",
            input_data="test",
            output_data="result"
        )
        print(f"✅ Trace: {trace_id}")
    
    print("✅ Client closed and traces flushed")


def main():
    """Run all examples."""
    print("=" * 50)
    print("🧠 TraceIQ SDK Examples")
    print("=" * 50)
    print("\nNote: These examples send traces to a local backend")
    print("Make sure backend is running at http://localhost:8000")
    print("\nTo start backend:")
    print("  cd backend")
    print("  python -m uvicorn main:app --reload")
    print("=" * 50)
    
    try:
        example_1_basic_tracing()
    except Exception as e:
        print(f"⚠️  Example 1 error: {e}")
    
    try:
        example_2_decorator()
    except Exception as e:
        print(f"⚠️  Example 2 error: {e}")
    
    try:
        example_3_context_manager()
    except Exception as e:
        print(f"⚠️  Example 3 error: {e}")
    
    try:
        example_4_batch_tracing()
    except Exception as e:
        print(f"⚠️  Example 4 error: {e}")
    
    try:
        example_5_error_handling()
    except Exception as e:
        print(f"⚠️  Example 5 error: {e}")
    
    try:
        example_6_with_statement()
    except Exception as e:
        print(f"⚠️  Example 6 error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Examples complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. View traces in dashboard: http://localhost:8501")
    print("2. Create evaluations to score outputs")
    print("3. Compare model performance")
    print("=" * 50)


if __name__ == "__main__":
    main()

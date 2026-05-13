"""
TrustBrain × Ollama — Live Demo
================================
Runs a multi-turn, multi-model Q&A pipeline against local Ollama models and
streams every call into TrustBrain as a trace you can watch in real-time.

Requirements:
    pip install requests httpx rich

Usage:
    cd <repo-root>
    python examples/ollama_live_demo/live_demo.py

Open http://localhost:3010 → Traces and hit Refresh to see traces appear live.
"""

import sys
import os
import time
import json
import uuid
import requests
from datetime import datetime
from typing import Optional

# ── Rich console ───────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import track
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class Console:                          # type: ignore
        def print(self, *a, **kw): print(*a)
        def rule(self, *a, **kw): print("─" * 60)
    rprint = print

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────
TRUSTBRAIN_URL = "http://localhost:8000"
OLLAMA_URL     = "http://localhost:11434"
PROJECT_NAME   = "My Project"

# Pick the fastest/smallest models on your machine; adjust as needed
MODELS = [
    "gemma2:2b",
    "mistral:latest",
    "llama3:8b",
]

# ── Auth helpers ───────────────────────────────────────────────────────────────

def login(email: str, name: str) -> str:
    """Login and return a JWT (registers first if user doesn't exist)."""
    # Try login first
    r = requests.post(
        f"{TRUSTBRAIN_URL}/api/auth/login",
        json={"email": email},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()["access_token"]
    # Fall back to register
    r = requests.post(
        f"{TRUSTBRAIN_URL}/api/auth/register",
        json={"email": email, "name": name},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_or_create_project(jwt: str, name: str) -> str:
    """Return the project ID, creating the project if it doesn't exist."""
    h = {"Authorization": f"Bearer {jwt}"}
    # List existing
    r = requests.get(f"{TRUSTBRAIN_URL}/api/projects", headers=h, timeout=10)
    r.raise_for_status()
    for p in r.json():
        if p["name"] == name:
            return p["id"]
    # Create
    r = requests.post(
        f"{TRUSTBRAIN_URL}/api/projects",
        json={"name": name, "description": "Live Ollama traces demo"},
        headers=h,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["id"]


# ── Ollama helper ──────────────────────────────────────────────────────────────

def call_ollama(model: str, messages: list[dict]) -> dict:
    """
    Call Ollama chat endpoint and return:
        text, prompt_tokens, completion_tokens, latency_ms
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    t0 = time.perf_counter()
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        latency_ms = (time.perf_counter() - t0) * 1000
        data = r.json()
        msg = data.get("message", {})
        usage = data.get("usage", {})
        return {
            "text": msg.get("content", "").strip(),
            "prompt_tokens": usage.get("prompt_tokens", data.get("prompt_eval_count", 0)),
            "completion_tokens": usage.get("completion_tokens", data.get("eval_count", 0)),
            "latency_ms": latency_ms,
            "ok": True,
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {"text": "", "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": latency_ms, "ok": False, "error": str(e)}


# ── Trace ingest ───────────────────────────────────────────────────────────────

def ingest_trace(jwt: str, project_id: str, model: str,
                 messages: list[dict], result: dict,
                 expected: Optional[str], tags: list[str],
                 metadata: dict) -> Optional[str]:
    """Send one trace to TrustBrain. Returns trace ID or None on failure."""
    total_tok = result["prompt_tokens"] + result["completion_tokens"]
    payload = {
        "project_id": project_id,
        "model": model,
        "input_data": {"messages": messages},
        "output_data": {"response": result["text"]} if result["ok"] else {"error": result.get("error", "unknown")},
        "expected_output": {"response": expected} if expected else None,
        "latency_ms": result["latency_ms"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "total_tokens": total_tok,
        "cost_usd": 0.0,          # Ollama is free
        "status": "success" if result["ok"] else "error",
        "error_message": result.get("error") if not result["ok"] else None,
        "tags": tags,
        "environment": "local-ollama",
        "metadata": metadata,
    }
    try:
        r = requests.post(
            f"{TRUSTBRAIN_URL}/api/traces",
            json=payload,
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=15,
        )
        if r.status_code == 201:
            return r.json()["id"]
    except Exception:
        pass
    return None


# ── Scenario definitions ───────────────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "Code Generation",
        "tags": ["code", "python"],
        "turns": [
            {
                "role": "user",
                "content": "Write a Python function that merges two sorted lists into one sorted list without using sort().",
                "expected": "def merge_sorted(a, b): ..."
            },
        ],
    },
    {
        "name": "Factual QA",
        "tags": ["qa", "factual"],
        "turns": [
            {
                "role": "user",
                "content": "What is the time complexity of binary search? Give a one-sentence answer.",
                "expected": "O(log n)"
            },
        ],
    },
    {
        "name": "Summarisation",
        "tags": ["summarisation", "nlp"],
        "turns": [
            {
                "role": "user",
                "content": (
                    "Summarise the following in exactly two sentences:\n\n"
                    "Transformer models have revolutionised natural language processing by replacing "
                    "recurrent architectures with self-attention mechanisms. They process input sequences "
                    "in parallel, allowing much faster training on large datasets. The attention mechanism "
                    "allows each token to attend to all other tokens in the sequence, capturing long-range "
                    "dependencies more effectively than LSTMs. Models like BERT, GPT, and T5 are all based "
                    "on the transformer architecture and have achieved state-of-the-art results across a "
                    "wide range of NLP benchmarks."
                ),
                "expected": "Transformers use self-attention instead of recurrence..."
            },
        ],
    },
    {
        "name": "Reasoning Chain",
        "tags": ["reasoning", "math"],
        "turns": [
            {
                "role": "user",
                "content": "A train travels 150 km in 2.5 hours. What is its average speed in km/h? Show your working.",
                "expected": "60 km/h"
            },
        ],
    },
    {
        "name": "Translation",
        "tags": ["translation", "multilingual"],
        "turns": [
            {
                "role": "user",
                "content": "Translate the following sentence into French, German, and Japanese:\n\"Machine learning is transforming every industry.\"",
                "expected": "French: L'apprentissage automatique..."
            },
        ],
    },
    {
        "name": "Creative Writing",
        "tags": ["creative", "writing"],
        "turns": [
            {
                "role": "user",
                "content": "Write a haiku about AI observability.",
                "expected": "5-7-5 syllable haiku"
            },
        ],
    },
    {
        "name": "JSON Generation",
        "tags": ["structured", "json"],
        "turns": [
            {
                "role": "user",
                "content": (
                    "Return ONLY valid JSON (no markdown, no explanation) for a user profile:\n"
                    '{"id": "<uuid>", "name": "Alice", "email": "alice@example.com", '
                    '"roles": ["admin", "user"], "active": true}'
                ),
                "expected": '{"id": "...", "name": "Alice", ...}'
            },
        ],
    },
    {
        "name": "Multi-turn Chat",
        "tags": ["multi-turn", "chat"],
        "turns": [
            {"role": "user", "content": "What is an LLM?", "expected": None},
            {"role": "user", "content": "What are its main limitations?", "expected": None},
            {"role": "user", "content": "How does RAG help with those limitations?", "expected": None},
        ],
    },
]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold cyan]TrustBrain × Ollama Live Demo[/bold cyan]\n"
            f"Backend: [green]{TRUSTBRAIN_URL}[/green]   Ollama: [green]{OLLAMA_URL}[/green]\n"
            "Watch [bold]http://localhost:3010/traces[/bold] and hit Refresh!"
        ))
    else:
        print("=" * 60)
        print("TrustBrain × Ollama Live Demo")
        print(f"Dashboard → http://localhost:3010/traces")
        print("=" * 60)

    # Auth
    email = "devtest@example.com"     # Change to your TrustBrain account email
    console.print(f"\n[dim]Authenticating as {email}…[/dim]")
    jwt = login(email, "Ollama Demo User")
    project_id = get_or_create_project(jwt, PROJECT_NAME)
    console.print(f"[green]✓[/green] Project: [bold]{PROJECT_NAME}[/bold] ({project_id[:8]}…)\n")

    # Verify models are available
    try:
        available_tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5).json()
        available = {m["name"] for m in available_tags.get("models", [])}
        models_to_use = [m for m in MODELS if m in available]
        if not models_to_use:
            models_to_use = [m["name"] for m in available_tags.get("models", [])[:2]]
    except Exception:
        # Ollama may be busy loading a model; use the configured list as-is
        models_to_use = MODELS
    console.print(f"Models: {', '.join(models_to_use)}\n")

    total_traces = 0
    total_tokens = 0
    errors = 0
    results_summary = []

    for scenario in SCENARIOS:
        console.rule(f"[bold]{scenario['name']}[/bold]")

        for model in models_to_use:
            history: list[dict] = [
                {"role": "system", "content": "You are a helpful, concise AI assistant."}
            ]
            turn_results = []

            for turn_idx, turn in enumerate(scenario["turns"]):
                history.append({"role": "user", "content": turn["content"]})

                console.print(f"  [cyan]{model}[/cyan] → [dim]{turn['content'][:70]}…[/dim]")
                result = call_ollama(model, history)

                if result["ok"]:
                    history.append({"role": "assistant", "content": result["text"]})
                    tok = result["prompt_tokens"] + result["completion_tokens"]
                    total_tokens += tok
                    console.print(
                        f"    [green]✓[/green] {result['latency_ms']:>6.0f} ms  "
                        f"{tok:>4} tokens  → [italic]{result['text'][:80]}[/italic]"
                    )
                else:
                    errors += 1
                    console.print(f"    [red]✗[/red] Error: {result.get('error', 'unknown')[:60]}")

                trace_id = ingest_trace(
                    jwt=jwt,
                    project_id=project_id,
                    model=model,
                    messages=[{"role": "user", "content": turn["content"]}],
                    result=result,
                    expected=turn.get("expected"),
                    tags=scenario["tags"] + [model, f"turn-{turn_idx+1}"],
                    metadata={
                        "scenario": scenario["name"],
                        "turn": turn_idx + 1,
                        "total_turns": len(scenario["turns"]),
                    },
                )
                if trace_id:
                    total_traces += 1
                    console.print(f"    [blue]→[/blue] Ingested: trace {trace_id[:8]}…")

                turn_results.append({
                    "model": model,
                    "latency_ms": result["latency_ms"],
                    "ok": result["ok"],
                })

                # Small pause so you can see the traces appear one by one
                time.sleep(0.5)

            results_summary.append({
                "scenario": scenario["name"],
                "model": model,
                "turns": len(scenario["turns"]),
                "avg_latency": (
                    sum(r["latency_ms"] for r in turn_results) / len(turn_results)
                    if turn_results else 0
                ),
            })

    # ── Summary ────────────────────────────────────────────────────────────────
    console.print("\n")
    console.rule("[bold green]Demo Complete[/bold green]")

    if HAS_RICH:
        table = Table(title="Summary")
        table.add_column("Scenario",    style="cyan")
        table.add_column("Model",       style="green")
        table.add_column("Avg Latency", justify="right")
        for row in results_summary:
            table.add_row(
                row["scenario"],
                row["model"],
                f"{row['avg_latency']:>7.0f} ms",
            )
        console.print(table)

    console.print(f"\n[bold]Total traces ingested:[/bold] {total_traces}")
    console.print(f"[bold]Total tokens used:[/bold]    {total_tokens:,}")
    console.print(f"[bold]Total cost:[/bold]           $0.00  (Ollama is free!)")
    if errors:
        console.print(f"[bold red]Errors:[/bold red]               {errors}")
    console.print(f"\n[bold]→ Open http://localhost:3010 → Traces and select project: '{PROJECT_NAME}'[/bold]\n")


if __name__ == "__main__":
    main()

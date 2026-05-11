"""
Playgrounds page — interactive prompt iteration with live model calls.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import json
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("⚡ Playground")
    st.caption("Rapidly prototype prompts and compare model outputs in real time.")

    tab_single, tab_batch = st.tabs(["Single Run", "Batch Run"])

    # â”€â”€ Single Run â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_single:
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("Configuration")
            model = st.selectbox(
                "Model",
                [
                    "gpt-4o", "gpt-4", "gpt-3.5-turbo",
                    "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307",
                    "ollama/llama2", "ollama/mistral",
                ],
            )
            temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.05)
            max_tokens = st.number_input("Max tokens", 64, 4096, 1024)
            system_prompt = st.text_area(
                "System prompt (optional)",
                placeholder="You are a helpful assistant…",
                height=100,
            )
            user_message = st.text_area(
                "User message",
                placeholder="Type your prompt here…",
                height=150,
            )
            expected = st.text_input("Expected output (optional, for scoring)")

            # Scorer
            scorer_type = None
            if expected:
                scorer_type = st.selectbox("Scorer", ["expected", "none"])
                if scorer_type == "none":
                    scorer_type = None

            run_btn = st.button("â–¶ Run", type="primary", disabled=not user_message, use_container_width=True)

        with col_right:
            st.subheader("Output")

            if "playground_result" not in st.session_state:
                st.session_state.playground_result = None

            if run_btn:
                with st.spinner("Calling LLM…"):
                    try:
                        result = client.post(
                            "/api/playgrounds/run",
                            json={
                                "project_id": project_id,
                                "system_prompt": system_prompt or None,
                                "user_message": user_message,
                                "model": model,
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "scorer_type": scorer_type,
                                "expected_output": expected or None,
                            },
                        )
                        st.session_state.playground_result = result
                    except Exception as e:
                        st.error(f"Error: {e}")

            if st.session_state.playground_result:
                res = st.session_state.playground_result
                st.text_area("Response", res.get("output", ""), height=250)

                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Latency", f"{res.get('latency_ms', 0):.0f} ms")
                m2.metric("Total tokens", res.get("total_tokens") or "—")
                m3.metric("Model", res.get("model", ""))

                if res.get("score"):
                    score = res["score"]
                    st.info(
                        f"**Score** ({score['scorer']}): {score['score']:.2f} | "
                        f"exact_match={score.get('exact_match')}"
                    )

    # â”€â”€ Batch Run â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_batch:
        st.subheader("Batch Evaluation")
        st.caption("Run the same configuration against multiple inputs at once.")

        model_b = st.selectbox("Model", ["gpt-4o", "gpt-3.5-turbo", "claude-3-haiku-20240307"], key="batch_model")
        system_b = st.text_area("System prompt", height=80, key="batch_system")
        inputs_raw = st.text_area(
            "Inputs (one per line)",
            height=200,
            placeholder="Summarise this article…\nTranslate to French…\nWhat is 2+2?",
        )

        if st.button("â–¶ Run Batch", type="primary", disabled=not inputs_raw):
            inputs = [line.strip() for line in inputs_raw.splitlines() if line.strip()]
            with st.spinner(f"Running {len(inputs)} inputs…"):
                try:
                    result = client.post(
                        "/api/playgrounds/batch",
                        json={
                            "project_id": project_id,
                            "system_prompt": system_b or None,
                            "inputs": inputs,
                            "model": model_b,
                        },
                    )
                    rows = result.get("results", [])
                    import pandas as pd
                    df = pd.DataFrame([
                        {
                            "Input": r.get("input", "")[:60],
                            "Output": str(r.get("output") or "")[:80],
                            "Latency (ms)": r.get("latency_ms"),
                            "Tokens": r.get("total_tokens"),
                            "Error": r.get("error"),
                        }
                        for r in rows
                    ])
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(f"Batch run failed: {e}")


# ── Standalone page runner ────────────────────────────────────────────────────
# Executed when Streamlit loads this file directly via multi-page navigation.
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from api_client import APIClient

    _base_url = os.getenv("BACKEND_API_URL", "http://traciq_backend:8000")

    # ── auth gate ─────────────────────────────────────────────────────────────
    if "jwt_token" not in st.session_state or not st.session_state.jwt_token:
        st.warning("⚠️ Please login from the main **app** page first.")
        email = st.text_input("Quick login — Email")
        if st.button("Login") and email:
            import httpx
            try:
                r = httpx.post(f"{_base_url}/api/auth/login",
                               json={"email": email}, timeout=10)
                r.raise_for_status()
                st.session_state.jwt_token = r.json()["access_token"]
                st.session_state.client = APIClient(_base_url, st.session_state.jwt_token)
                st.rerun()
            except Exception as _e:
                st.error(f"Login failed: {_e}")
        st.stop()

    # ── project gate ──────────────────────────────────────────────────────────
    if "client" not in st.session_state or not st.session_state.client:
        st.session_state.client = APIClient(_base_url, st.session_state.jwt_token)

    _client = st.session_state.client

    if "selected_project" not in st.session_state or not st.session_state.selected_project:
        try:
            _projects = _client.get("/api/projects") or []
        except Exception:
            _projects = []
        if not _projects:
            st.warning("No projects found. Create one from the main app page.")
            st.stop()
        _names = [p["name"] for p in _projects]
        _sel = st.sidebar.selectbox("Select project", _names)
        st.session_state.selected_project = next(p for p in _projects if p["name"] == _sel)

    _project_id = st.session_state.selected_project.get("id", "")

    # ── render ────────────────────────────────────────────────────────────────
    render(_client, _project_id)
"""
Loop AI agent page — natural-language Q&A over trace logs.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🤖 Loop — AI Analysis Agent")
    st.caption(
        "Ask questions about your traces in plain English. "
        "Loop uses your logs as context to provide accurate answers."
    )

    # Initialize chat history
    if "loop_history" not in st.session_state:
        st.session_state.loop_history = []

    # Suggested questions
    suggestions = [
        "How many traces had errors in the last 7 days?",
        "What is the average latency across all models?",
        "Which model has the best performance?",
        "Show me examples where the user asked about pricing.",
        "What are the most common failure patterns?",
    ]

    with st.expander("ðŸ’¡ Suggested questions"):
        for q in suggestions:
            if st.button(q, key=f"sugg_{q[:20]}", use_container_width=True):
                st.session_state.loop_input = q

    # Chat display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.loop_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                with st.chat_message("user"):
                    st.write(content)
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(content)
                    if msg.get("sources"):
                        with st.expander(f"ðŸ“„ {len(msg['sources'])} source trace(s)"):
                            for s in msg["sources"][:5]:
                                st.caption(f"Trace `{s['trace_id'][:12]}` — score {s['score']:.3f}")
                    method = msg.get("method", "")
                    if method:
                        st.caption(f"_Method: {method}_")

    # Input
    model = st.selectbox(
        "LLM model", ["gpt-3.5-turbo", "gpt-4", "claude-3-haiku-20240307"],
        label_visibility="collapsed"
    )
    question = st.chat_input("Ask Loop anything about your traces…",
                              key=getattr(st.session_state, "loop_input", None))

    if question:
        # Clear pre-fill
        if hasattr(st.session_state, "loop_input"):
            del st.session_state.loop_input

        st.session_state.loop_history.append({"role": "user", "content": question})

        with st.spinner("Loop is thinking…"):
            try:
                response = client.post(
                    "/api/loop/ask",
                    json={"question": question, "project_id": project_id, "model": model},
                )
                answer = response.get("answer", "No answer returned.")
                sources = response.get("sources", [])
                method = response.get("method", "")

                st.session_state.loop_history.append(
                    {"role": "assistant", "content": answer, "sources": sources, "method": method}
                )
            except Exception as e:
                st.session_state.loop_history.append(
                    {"role": "assistant", "content": f"âš ï¸ Error: {e}", "sources": [], "method": "error"}
                )
        st.rerun()

    if st.button("ðŸ—‘ï¸ Clear conversation", use_container_width=False):
        st.session_state.loop_history = []
        st.rerun()


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
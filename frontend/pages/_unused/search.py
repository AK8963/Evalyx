"""
Deep search page — semantic + keyword trace search.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🔍 Deep Search")
    st.caption("Find traces by meaning (semantic) or exact keywords.")

    search_type = st.radio(
        "Search mode", ["Semantic", "Keyword"], horizontal=True, label_visibility="collapsed"
    )
    query = st.text_input("Search query", placeholder="e.g. user asking about pricing…")
    top_k = st.slider("Max results", 5, 100, 20)

    if st.button("Search", type="primary", disabled=not query):
        with st.spinner("Searching…"):
            endpoint = (
                f"/api/search/semantic?project_id={project_id}&q={query}&top_k={top_k}"
                if search_type == "Semantic"
                else f"/api/search/keyword?project_id={project_id}&q={query}&limit={top_k}"
            )
            try:
                result = client.get(endpoint)
                hits = result.get("results", [])
                method = result.get("method", "")
                total = result.get("total", len(hits))

                st.success(f"Found **{total}** results via {method} search")

                if hits:
                    import pandas as pd
                    df = pd.DataFrame(hits)
                    cols_order = [c for c in ["trace_id", "score", "model", "status", "timestamp", "latency_ms"] if c in df.columns]
                    st.dataframe(df[cols_order], use_container_width=True)
                else:
                    st.info("No results. Try different keywords or ensure traces are indexed.")
            except Exception as e:
                st.error(f"Search failed: {e}")

    # Indexing section
    with st.expander("âš™ï¸ Index a specific trace"):
        trace_id = st.text_input("Trace ID to index")
        if st.button("Index", disabled=not trace_id):
            try:
                r = client.post(f"/api/search/index/{trace_id}")
                st.success(f"Indexed: {r}")
            except Exception as e:
                st.error(f"Indexing failed: {e}")


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
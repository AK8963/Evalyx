"""
Topics explorer page — auto-discovered patterns in trace logs.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🏷️ Topics — AI-Powered Pattern Discovery")
    st.caption(
        "Topics automatically classify your traces by user intent, sentiment, and issues — "
        "no configuration required."
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔎 Re-analyse Recent Traces", use_container_width=True):
            with st.spinner("Analysing traces…"):
                try:
                    r = client.post(f"/api/topics/reanalyse?project_id={project_id}&limit=500")
                    st.success(f"Analysed {r.get('analysed', 0)} traces")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    # Fetch summary
    try:
        summary = client.get(f"/api/topics/summary?project_id={project_id}")
    except Exception as e:
        st.error(f"Failed to load topics: {e}")
        return

    if not summary:
        st.info(
            "No topics yet. Send some traces and click **Re-analyse Recent Traces** to generate topics."
        )
        return

    facet_icons = {"task": "🎯", "sentiment": "ðŸ˜Š", "issues": "âš ï¸"}

    for facet_group in summary:
        facet = facet_group["facet_type"]
        topics = facet_group["topics"]
        icon = facet_icons.get(facet, "ðŸ“‚")

        st.subheader(f"{icon} {facet.title()} ({len(topics)} topics)")

        if not topics:
            st.info(f"No {facet} topics yet.")
            continue

        # Display as a bar chart
        import pandas as pd
        df = pd.DataFrame(topics)
        if not df.empty:
            chart_df = df.set_index("name")["trace_count"]
            st.bar_chart(chart_df, height=200)

        # Topic cards
        cols = st.columns(min(len(topics), 4))
        for i, topic in enumerate(topics[:8]):
            with cols[i % 4]:
                with st.container(border=True):
                    st.metric(topic["name"], f"{topic['trace_count']} traces")
                    if st.button("View", key=f"topic_{topic['id']}", use_container_width=True):
                        _show_topic_traces(client, topic)


def _show_topic_traces(client: APIClient, topic: dict) -> None:
    with st.expander(f"Traces for '{topic['name']}'", expanded=True):
        try:
            data = client.get(f"/api/topics/{topic['id']}/traces?limit=20")
            traces = data.get("traces", [])
            if traces:
                import pandas as pd
                df = pd.DataFrame(traces)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No traces found for this topic.")
        except Exception as e:
            st.error(f"Error: {e}")


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
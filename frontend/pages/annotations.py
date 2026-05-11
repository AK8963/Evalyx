"""
Annotations page — human feedback, labels, and review queue.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("✍️ Annotations")
    st.caption("Add human feedback to traces, manage labels, and review AI outputs.")

    tab_summary, tab_review, tab_labels = st.tabs(["Summary", "Review Queue", "Manage Labels"])

    # â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_summary:
        try:
            summary = client.get(f"/api/annotations/summary?project_id={project_id}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Annotations", summary.get("total", 0))
            col2.metric("ðŸ‘ Thumbs Up", summary.get("thumbs_up", 0))
            col3.metric("ðŸ‘Ž Thumbs Down", summary.get("thumbs_down", 0))
            avg_r = summary.get("avg_rating")
            col4.metric("â­ Avg Rating", f"{avg_r:.1f}/5" if avg_r else "N/A")
        except Exception as e:
            st.error(f"Error: {e}")

        # Recent annotations
        st.subheader("Recent Annotations")
        try:
            anns = client.get(f"/api/annotations/?project_id={project_id}&limit=20")
            if anns:
                import pandas as pd
                rows = []
                for a in anns:
                    rows.append({
                        "Trace": a["trace_id"][:12],
                        "ðŸ‘/ðŸ‘Ž": "ðŸ‘" if a["thumbs_up"] else ("ðŸ‘Ž" if a["thumbs_up"] is False else "—"),
                        "Rating": a.get("rating") or "—",
                        "Comment": (a.get("comment") or "")[:60],
                        "Labels": ", ".join(a.get("label_names") or []),
                        "Created": (a.get("created_at") or "")[:16],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("No annotations yet.")
        except Exception as e:
            st.error(f"Error loading annotations: {e}")

    # â”€â”€ Review Queue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_review:
        st.subheader("Annotate a Trace")
        with st.form("annotate_trace"):
            trace_id = st.text_input("Trace ID", placeholder="Paste trace UUID…")
            thumbs = st.radio("Feedback", ["ðŸ‘ Positive", "ðŸ‘Ž Negative", "âšª No opinion"], horizontal=True)
            rating = st.slider("Rating (1-5, optional)", 0, 5, 0)
            comment = st.text_area("Comment (optional)")
            corrected = st.text_area("Corrected output (optional, JSON or text)")

            # Labels
            try:
                labels = client.get(f"/api/annotations/labels?project_id={project_id}")
            except Exception:
                labels = []
            label_options = {l["name"]: l["id"] for l in labels}
            selected_labels = st.multiselect("Labels", list(label_options.keys()))

            submitted = st.form_submit_button("Submit Annotation", type="primary")
            if submitted and trace_id:
                thumbs_up = True if "Positive" in thumbs else (False if "Negative" in thumbs else None)
                corrected_val = corrected.strip() or None
                try:
                    import json
                    corrected_val = json.loads(corrected) if corrected_val else None
                except Exception:
                    pass
                try:
                    client.post("/api/annotations/", json={
                        "trace_id": trace_id,
                        "project_id": project_id,
                        "thumbs_up": thumbs_up,
                        "rating": rating if rating > 0 else None,
                        "comment": comment or None,
                        "label_ids": [label_options[n] for n in selected_labels],
                        "label_names": selected_labels,
                        "corrected_output": corrected_val,
                    })
                    st.success("âœ… Annotation saved!")
                except Exception as e:
                    st.error(f"Error: {e}")

    # â”€â”€ Labels â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_labels:
        st.subheader("Manage Labels")

        # Existing labels
        try:
            labels = client.get(f"/api/annotations/labels?project_id={project_id}")
            if labels:
                cols = st.columns(4)
                for i, label in enumerate(labels):
                    with cols[i % 4]:
                        st.markdown(
                            f'<span style="background:{label["color"]};color:white;'
                            f'padding:4px 10px;border-radius:4px;">{label["name"]}</span>',
                            unsafe_allow_html=True,
                        )
                        if st.button("Delete", key=f"del_label_{label['id']}"):
                            try:
                                client.delete(f"/api/annotations/labels/{label['id']}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Error loading labels: {e}")

        # Create label
        with st.form("create_label"):
            label_name = st.text_input("Label name")
            label_color = st.color_picker("Color", "#3B82F6")
            label_desc = st.text_input("Description (optional)")
            if st.form_submit_button("Create Label"):
                if label_name:
                    try:
                        client.post("/api/annotations/labels", json={
                            "project_id": project_id,
                            "name": label_name,
                            "color": label_color,
                            "description": label_desc or None,
                        })
                        st.success(f"Created label: {label_name}")
                        st.rerun()
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
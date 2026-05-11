"""
Online Scoring page — manage automatic production scoring rules.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import json
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🎯 Online Scoring")
    st.caption(
        "Automatically score production traces as they arrive — no impact on latency."
    )

    tab_rules, tab_create = st.tabs(["Active Rules", "Create Rule"])

    # â”€â”€ Active rules â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_rules:
        try:
            rules = client.get(f"/api/online-scoring/rules?project_id={project_id}")
        except Exception as e:
            st.error(f"Error: {e}")
            rules = []

        if not rules:
            st.info("No scoring rules yet. Create one in the **Create Rule** tab.")
        else:
            for rule in rules:
                with st.expander(
                    f"{'âœ…' if rule['is_active'] else 'â¸ï¸'} {rule['name']} ({rule['scorer_type']})"
                ):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Scorer type", rule["scorer_type"])
                    col2.metric("Sample rate", f"{rule['sample_rate']:.0%}")
                    col3.text(f"Created: {(rule.get('created_at') or '')[:10]}")

                    st.json(rule.get("scorer_config") or {})

                    btn1, btn2 = st.columns(2)
                    if btn1.button(
                        "Pause" if rule["is_active"] else "Resume",
                        key=f"toggle_{rule['id']}",
                    ):
                        try:
                            client.patch(
                                f"/api/online-scoring/rules/{rule['id']}",
                                json={"is_active": not rule["is_active"]},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

                    if btn2.button("ðŸ—‘ï¸ Delete", key=f"del_rule_{rule['id']}"):
                        try:
                            client.delete(f"/api/online-scoring/rules/{rule['id']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # â”€â”€ Create rule â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_create:
        with st.form("create_rule"):
            name = st.text_input("Rule name")
            scorer_type = st.selectbox("Scorer type", ["expected", "llm", "code"])
            sample_rate = st.slider("Sample rate", 0.01, 1.0, 1.0, 0.01)

            st.markdown("**Scorer config (JSON)**")
            if scorer_type == "expected":
                config_default = '{"match_type": "exact"}'
            elif scorer_type == "llm":
                config_default = '{"prompt_template": "Rate the quality of this output 0-1: {{output}}", "model": "gpt-3.5-turbo"}'
            else:
                config_default = '{"code": "def score(input, output, expected):\\n    return 1.0 if output == expected else 0.0"}'

            scorer_config_raw = st.text_area("Scorer config", value=config_default, height=100)

            if st.form_submit_button("Create Rule", type="primary"):
                if name:
                    try:
                        config = json.loads(scorer_config_raw)
                        client.post("/api/online-scoring/rules", json={
                            "project_id": project_id,
                            "name": name,
                            "scorer_type": scorer_type,
                            "scorer_config": config,
                            "sample_rate": sample_rate,
                        })
                        st.success(f"âœ… Rule **{name}** created")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Invalid JSON in scorer config")
                    except Exception as e:
                        st.error(f"Error: {e}")

    # â”€â”€ Manual trigger â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    st.divider()
    st.subheader("Manual Score Trigger")
    trace_id = st.text_input("Trace ID to score manually")
    if st.button("Score this trace", disabled=not trace_id):
        try:
            result = client.post(f"/api/online-scoring/score/{trace_id}")
            st.success(str(result))
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
"""
Gateway page — unified LLM routing, cost tracking, and usage analytics.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import json
from api_client import APIClient



def _run_stream(client, project_id, model, temperature, message):
    """Consume SSE stream from /api/gateway/stream and render tokens live."""
    import json as _json
    import time as _time
    import requests as _req

    base_url = getattr(client, 'base_url', 'http://traciq_backend:8000').rstrip('/')
    tok = getattr(client, 'jwt_token', None)
    headers = {'Content-Type': 'application/json'}
    if tok:
        headers['Authorization'] = f'Bearer {tok}'

    payload = {
        'project_id': project_id,
        'model': model,
        'messages': [{'role': 'user', 'content': message}],
        'temperature': temperature,
        'max_tokens': 1024,
    }

    output_box = st.empty()
    meta_box = st.empty()
    accumulated = ''
    start = _time.time()
    token_count = 0

    try:
        with _req.post(
            f'{base_url}/api/gateway/stream',
            json=payload, headers=headers,
            stream=True, timeout=120,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode('utf-8') if isinstance(raw_line, bytes) else raw_line
                if not line.startswith('data:'):
                    continue
                try:
                    chunk = _json.loads(line[5:].strip())
                except Exception:
                    continue
                if chunk.get('error'):
                    st.error(f"Stream error: {chunk['error']}")
                    return
                token_text = chunk.get('token', '')
                if token_text:
                    accumulated += token_text
                    token_count += 1
                    elapsed = _time.time() - start
                    tps = token_count / elapsed if elapsed > 0 else 0
                    box_style = (
                        "background:#0e1117;padding:16px;border-radius:8px;"
                        "font-family:monospace;white-space:pre-wrap;"
                        "border-left:3px solid #00d26a"
                    )
                    output_box.markdown(
                        f'<div style="{box_style}">{accumulated}</div>',
                        unsafe_allow_html=True,
                    )
                    meta_box.caption(f'Tokens: {token_count} | {tps:.1f} tok/s')
                if chunk.get('done'):
                    total_tok = chunk.get('total_tokens') or token_count
                    lat = chunk.get('latency_ms')
                    cost = chunk.get('cost_usd')
                    c1, c2, c3 = st.columns(3)
                    c1.metric('Total tokens', total_tok)
                    c2.metric('Latency', f"{lat:.0f} ms" if lat else f"{(_time.time()-start)*1000:.0f} ms")
                    c3.metric('Cost', f"${cost:.5f}" if cost else '---')
                    break
    except Exception as exc:
        st.error(f'Streaming failed: {exc}')


def render(client: APIClient, project_id: str) -> None:
    st.header("🌐 Gateway")
    st.caption("Route requests through a unified LLM gateway with cost tracking and caching.")

    tab_stream, tab_chat, tab_stats, tab_providers = st.tabs(["⚡ Streaming", "Interactive", "Cost & Usage", "Providers"])

    # Streaming tab
    with tab_stream:
        st.subheader("⚡ Live Token Streaming")
        st.caption("Watch tokens arrive in real-time via Server-Sent Events.")
        stream_model = st.text_input("Model", value="gpt-3.5-turbo", key="stream_model")
        stream_temp = st.slider("Temperature", 0.0, 2.0, 0.7, key="stream_temp")
        stream_msg = st.text_area("Message", height=100, placeholder="Tell me a short story about AI...", key="stream_msg")
        if st.button("Stream Response", type="primary", disabled=not stream_msg, key="stream_btn"):
            _run_stream(client, project_id, stream_model, stream_temp, stream_msg)

    # â”€â”€ Interactive chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_chat:
        st.subheader("Test the Gateway")
        model = st.text_input("Model", value="gpt-3.5-turbo",
                               help="Examples: gpt-4o, claude-3-haiku-20240307, anthropic/claude-3-sonnet")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7)
        use_cache = st.checkbox("Use cache (skip LLM if identical request seen before)")
        fallback_raw = st.text_input("Fallback models (comma-separated, optional)",
                                      placeholder="gpt-3.5-turbo, anthropic/claude-3-haiku")
        message = st.text_area("Message", height=120, placeholder="Ask anything…")

        if st.button("Send via Gateway", type="primary", disabled=not message):
            fallbacks = [f.strip() for f in fallback_raw.split(",") if f.strip()]
            with st.spinner("Routing request…"):
                try:
                    result = client.post("/api/gateway/complete", json={
                        "project_id": project_id,
                        "model": model,
                        "messages": [{"role": "user", "content": message}],
                        "temperature": temperature,
                        "use_cache": use_cache,
                        "fallback_models": fallbacks,
                    })
                    st.text_area("Response", result.get("content", ""), height=200)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Provider", result.get("provider", "—"))
                    m2.metric("Model", result.get("model", "—"))
                    m3.metric("Latency", f"{result.get('latency_ms', 0):.0f} ms")
                    cost = result.get("cost_usd")
                    m4.metric("Cost", f"${cost:.5f}" if cost else "—")
                    if result.get("cache_hit"):
                        st.success("âœ… Served from cache")
                except Exception as e:
                    st.error(f"Gateway error: {e}")

    # â”€â”€ Cost & Usage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_stats:
        days = st.slider("Time range (days)", 1, 30, 7)
        try:
            stats = client.get(f"/api/gateway/stats?project_id={project_id}&days={days}")
            if stats:
                import pandas as pd
                df = pd.DataFrame(stats)
                st.dataframe(df, use_container_width=True)

                # Total cost
                total = sum(r.get("total_cost_usd", 0) for r in stats)
                st.metric(f"Total gateway cost (last {days}d)", f"${total:.4f}")

                # Bar chart — cost by model
                if not df.empty:
                    cost_chart = df.set_index("model")["total_cost_usd"]
                    st.bar_chart(cost_chart, height=200)
            else:
                st.info("No gateway requests recorded yet.")
        except Exception as e:
            st.error(f"Error: {e}")

    # â”€â”€ Providers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_providers:
        try:
            providers = client.get("/api/gateway/providers")
            if providers:
                st.write("**Configured providers:**")
                for p in providers:
                    st.success(f"âœ… {p['service']} — {p.get('model') or 'default model'}")
            else:
                st.info("No API keys configured. Add them in the âš™ï¸ Settings page.")
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
"""
Analytics page — time-series metrics, model breakdown, score trends.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("📊 Analytics")
    st.caption("Track trends in latency, cost, token usage, scores, and model performance.")

    days = st.slider("Time range (days)", 1, 90, 7, key="analytics_days")

    # â”€â”€ Overview metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        overview = client.get(f"/api/analytics/overview?project_id={project_id}&days={days}")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Traces", f"{overview.get('total_traces', 0):,}")
        err = overview.get("error_rate", 0)
        col2.metric("Error Rate", f"{err:.1%}", delta=None)
        avg_lat = overview.get("avg_latency_ms")
        col3.metric("Avg Latency", f"{avg_lat:.0f} ms" if avg_lat else "—")
        col4.metric("Total Cost", f"${overview.get('total_cost_usd', 0):.4f}")
        col5.metric("Total Tokens", f"{overview.get('total_tokens', 0):,}")
    except Exception as e:
        st.error(f"Overview error: {e}")

    st.divider()

    # â”€â”€ Time-series charts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    tab_ts, tab_models, tab_scores, tab_cost = st.tabs(
        ["Time Series", "Model Breakdown", "Score Trends", "💰 Cost Analysis"]
    )

    with tab_ts:
        metric = st.selectbox(
            "Metric",
            ["trace_count", "error_count", "avg_latency", "total_cost", "total_tokens"],
            format_func=lambda x: x.replace("_", " ").title(),
        )
        try:
            ts = client.get(f"/api/analytics/timeseries?project_id={project_id}&metric={metric}&days={days}")
            series = ts.get("series", []) if ts else []
            if series:
                df = pd.DataFrame(series)
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                is_cost = "cost" in metric
                fig = go.Figure(go.Scatter(
                    x=df["date"], y=df["value"],
                    mode="lines+markers",
                    fill="tozeroy",
                    line=dict(color="#636EFA", width=2),
                    marker=dict(size=7),
                ))
                fig.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(type="date", tickformat="%b %d", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                    yaxis=dict(
                        tickformat="$.5f" if is_cost else ",",
                        showgrid=True, gridcolor="rgba(255,255,255,0.1)", rangemode="tozero"
                    ),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data for selected metric.")
        except Exception as e:
            st.error(f"Error: {e}")

    with tab_models:
        try:
            models = client.get(f"/api/analytics/models?project_id={project_id}&days={days}")
            if models:
                df = pd.DataFrame(models)
                st.dataframe(df, use_container_width=True)
                # Latency comparison
                if "avg_latency_ms" in df.columns:
                    lat_df = df[["model", "avg_latency_ms"]].dropna()
                    if not lat_df.empty:
                        fig = px.bar(
                            lat_df, x="model", y="avg_latency_ms",
                            labels={"model": "Model", "avg_latency_ms": "Avg Latency (ms)"},
                            color="avg_latency_ms",
                            color_continuous_scale="Reds",
                            height=280,
                        )
                        fig.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            showlegend=False, coloraxis_showscale=False,
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No model data yet.")
        except Exception as e:
            st.error(f"Error: {e}")

    with tab_scores:
        scorer_filter = st.text_input("Filter by scorer name (optional)")
        try:
            params = f"project_id={project_id}&days={days}"
            if scorer_filter:
                params += f"&scorer_name={scorer_filter}"
            scores_data = client.get(f"/api/analytics/scores?{params}")
            if scores_data:
                df = pd.DataFrame(scores_data)
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                fig = px.line(
                    df, x="date", y="avg_score", color="scorer_name",
                    markers=True,
                    labels={"date": "Date", "avg_score": "Avg Score", "scorer_name": "Scorer"},
                    height=320,
                )
                fig.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(tickformat="%b %d", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                    yaxis=dict(range=[0, 1.05], showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No scoring data for this period.")
        except Exception as e:
            st.error(f"Error: {e}")

    with tab_cost:
        st.subheader("💰 Cost Analysis")

        # ── Per-model cost breakdown from trace data ─────────────────────────
        try:
            models_data = client.get(
                f"/api/analytics/models?project_id={project_id}&days={days}"
            )
            if models_data:
                df_m = pd.DataFrame(models_data)
                # Show cost columns if present
                cost_cols = [c for c in ["model", "total_cost_usd", "avg_cost_usd",
                                         "total_tokens", "trace_count"] if c in df_m.columns]
                if cost_cols:
                    df_display = df_m[cost_cols].copy()
                    if "total_cost_usd" in df_display.columns:
                        df_display["total_cost_usd"] = df_display["total_cost_usd"].apply(
                            lambda x: f"${x:.6f}" if x is not None else "—"
                        )
                    if "avg_cost_usd" in df_display.columns:
                        df_display["avg_cost_usd"] = df_display["avg_cost_usd"].apply(
                            lambda x: f"${x:.6f}" if x is not None else "—"
                        )
                    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]
                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    # Bar chart — total cost per model
                    if "total_cost_usd" in df_m.columns:
                        chart_df = df_m[["model", "total_cost_usd"]].dropna()
                        chart_df = chart_df[chart_df["total_cost_usd"] > 0]
                        if not chart_df.empty:
                            fig = px.bar(
                                chart_df, x="model", y="total_cost_usd",
                                labels={"model": "Model", "total_cost_usd": "Total Cost (USD)"},
                                color="total_cost_usd",
                                color_continuous_scale="Greens",
                                height=260,
                            )
                            fig.update_layout(
                                margin=dict(l=10, r=10, t=10, b=10),
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                showlegend=False, coloraxis_showscale=False,
                            )
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No cost data in model breakdown.")
            else:
                st.info("No model data for this period.")
        except Exception as e:
            st.warning(f"Could not load cost breakdown: {e}")

        st.divider()

        # ── Pricing reference table ───────────────────────────────────────────
        with st.expander("📋 Model Pricing Reference", expanded=False):
            try:
                pricing_data = client.get("/api/pricing")
                if pricing_data:
                    df_p = pd.DataFrame(pricing_data)
                    df_p = df_p.rename(columns={
                        "model": "Model",
                        "provider": "Provider",
                        "prompt_cost_per_1k_tokens": "Prompt ($/1k tokens)",
                        "completion_cost_per_1k_tokens": "Completion ($/1k tokens)",
                        "is_free": "Free (local)",
                    })
                    provider_filter = st.selectbox(
                        "Filter by provider",
                        ["All"] + sorted(df_p["Provider"].unique().tolist()),
                        key="cost_provider_filter",
                    )
                    if provider_filter != "All":
                        df_p = df_p[df_p["Provider"] == provider_filter]
                    st.dataframe(df_p, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Could not load pricing table: {e}")

        st.divider()

        # ── Cost estimator ────────────────────────────────────────────────────
        st.subheader("🧮 Cost Estimator")
        col_a, col_b, col_c = st.columns(3)
        est_model = col_a.text_input("Model", value="gpt-4o", key="est_model")
        est_prompt = col_b.number_input("Prompt tokens", min_value=0, value=500, step=100, key="est_prompt")
        est_comp = col_c.number_input("Completion tokens", min_value=0, value=200, step=50, key="est_comp")
        if st.button("Estimate Cost", key="est_btn"):
            try:
                result = client.get(
                    f"/api/pricing/estimate?model={est_model}"
                    f"&prompt_tokens={est_prompt}&completion_tokens={est_comp}"
                )
                if result.get("known_model"):
                    cost = result.get("estimated_cost_usd", 0) or 0
                    pricing_info = result.get("pricing", {}) or {}
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estimated Cost", f"${cost:.6f}")
                    c2.metric(
                        "Prompt rate",
                        f"${pricing_info.get('prompt_cost_per_1k_tokens', 0):.4f} / 1k"
                    )
                    c3.metric(
                        "Completion rate",
                        f"${pricing_info.get('completion_cost_per_1k_tokens', 0):.4f} / 1k"
                    )
                    if pricing_info.get("is_free"):
                        st.success("🆓 This is a local/Ollama model — no API cost!")
                else:
                    st.warning(f"Model **{est_model}** is not in the pricing table. "
                               "Add it to `backend/pricing.py` to enable cost tracking.")
            except Exception as e:
                st.error(f"Estimation failed: {e}")


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
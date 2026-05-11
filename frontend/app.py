"""
TraceIQ Dashboard - Main Streamlit app.
"""

import streamlit as st
import logging
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# Add frontend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from api_client import APIClient

# New pages (Phase 2-6 + Phase 1 additions)
_NEW_PAGES = False
_PAGE_IMPORT_ERROR = ""
try:
    from pages import (
        topics, search, loop, datasets, annotations,
        experiments, playgrounds, prompts, gateway,
        analytics, online_scoring, admin, settings, btql, remote_evals,
        sso, alerts, masking
    )
    _NEW_PAGES = True
except Exception as _page_import_err:  # graceful fallback if a page has a syntax error
    _NEW_PAGES = False
    _PAGE_IMPORT_ERROR = str(_page_import_err)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit
st.set_page_config(
    page_title="TraceIQ Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state management
if "jwt_token" not in st.session_state:
    st.session_state.jwt_token = None
if "client" not in st.session_state:
    st.session_state.client = None
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gpt-4"
if "available_models" not in st.session_state:
    st.session_state.available_models = [
        "gpt-4", "gpt-3.5-turbo",
        "claude-3-opus", "claude-3-sonnet",
        "gemini-pro",
        "ollama-llama2"
    ]


def initialize_client(jwt_token: str, base_url: str = None):
    """Initialize API client with JWT token."""
    if base_url is None:
        base_url = os.getenv("BACKEND_API_URL", "http://traciq_backend:8000")
    client = APIClient(base_url, jwt_token)
    if client.verify_token(jwt_token):
        st.session_state.jwt_token = jwt_token
        st.session_state.client = client
        st.success("✅ Connected to TraceIQ!")
        return True
    else:
        st.error("❌ Invalid token")
        return False


def render_sidebar():
    """Render sidebar with authentication and project selection."""
    with st.sidebar:
        st.title("🧠 TraceIQ")
        
        # Authentication section
        if not st.session_state.jwt_token:
            st.subheader("Authentication")
            
            # Login vs Register tabs
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                st.write("**Login to Dashboard**")
                email = st.text_input("Email Address", key="login_email")
                
                if st.button("Login", use_container_width=True, key="login_btn"):
                    if email:
                        client = APIClient()
                        result = client.login_user(email)
                        if result and "access_token" in result:
                            if initialize_client(result["access_token"]):
                                st.rerun()
                        else:
                            st.error("❌ Login failed. User not found or error occurred.")
                    else:
                        st.error("Please enter your email")
            
            with tab2:
                st.write("**Create New Account**")
                
                with st.form("registration_form"):
                    email = st.text_input("Email Address", key="reg_email_form")
                    name = st.text_input("Full Name", key="reg_name_form")
                    
                    submitted = st.form_submit_button("Create Account", use_container_width=True)
                    
                    if submitted and email and name:
                        client = APIClient()
                        result = client.register_user(email, name)
                        if result and "access_token" in result:
                            if initialize_client(result["access_token"]):
                                st.success(f"✅ {result.get('message', 'Account created and logged in!')}")
                                st.rerun()
                        else:
                            st.error("❌ Registration failed. Please check your input.")
        
        else:
            # Logged in - show project selector and settings
            st.subheader("Projects")
            
            if st.button("Logout", use_container_width=True):
                st.session_state.jwt_token = None
                st.session_state.client = None
                st.session_state.selected_project = None
                st.rerun()
            
            # Get projects
            projects = st.session_state.client.list_projects()
            
            if projects:
                project_names = [p["name"] for p in projects]
                selected = st.selectbox(
                    "Select Project",
                    project_names,
                    key="project_select"
                )
                
                selected_project = next((p for p in projects if p["name"] == selected), None)
                st.session_state.selected_project = selected_project
            
            # Model Selector
            st.divider()
            st.subheader("⚙️ Model Settings")
            
            model_categories = {
                "🔵 OpenAI": ["gpt-4", "gpt-3.5-turbo"],
                "🟠 Anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "🟡 Google": ["gemini-pro"],
                "🟣 Local (Ollama)": None  # Dynamic list
            }
            
            st.write("**Select Scorer Model:**")
            
            # Ollama model options
            ollama_models = [
                "llama2", "mistral", "neural-chat", "dolphin-mixtral",
                "openchat", "starling-lm"
            ]
            
            # Create columns for model categories
            for category, models in model_categories.items():
                if st.checkbox(category, key=f"category_{category}"):
                    if category == "🟣 Local (Ollama)":
                        # Custom Ollama model input
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            model_choice = st.selectbox(
                                "Available Ollama Models",
                                ollama_models + ["Other (specify below)"],
                                key="ollama_model_choice"
                            )
                        with col2:
                            st.empty()
                        
                        if model_choice == "Other (specify below)":
                            custom_model = st.text_input(
                                "Enter custom Ollama model name",
                                placeholder="e.g., llama2:13b",
                                key="custom_ollama_model"
                            )
                            if custom_model:
                                st.session_state.selected_model = f"ollama-{custom_model}"
                                st.info(f"✅ Selected: `ollama-{custom_model}`")
                        else:
                            st.session_state.selected_model = f"ollama-{model_choice}"
                            st.info(f"✅ Selected: `ollama-{model_choice}`")
                    else:
                        selected_model = st.selectbox(
                            f"Choose {category} model",
                            models,
                            key=f"model_{category}"
                        )
                        st.session_state.selected_model = selected_model
                        st.info(f"✅ Selected: `{selected_model}`")
                    break
            
            # Create new project
            st.divider()
            st.subheader("Create Project")
            
            with st.form("create_project_form"):
                proj_name = st.text_input("Project Name")
                proj_desc = st.text_area("Description", height=100)
                
                if st.form_submit_button("Create", use_container_width=True):
                    if proj_name:
                        result = st.session_state.client.create_project(proj_name, proj_desc)
                        if result:
                            st.success(f"✅ Project '{proj_name}' created!")
                            st.rerun()
                        else:
                            st.error("Failed to create project")
                    else:
                        st.error("Project name required")


def render_dashboard():
    """Render main dashboard page."""
    st.title("📊 Dashboard")

    if not st.session_state.selected_project:
        st.info("👈 Select or create a project from the sidebar")
        return

    project = st.session_state.selected_project
    client = st.session_state.client
    project_id = project["id"]

    st.subheader(f"Project: {project['name']}")

    # ── Overview metrics from analytics API ──────────────────────────────────
    days = st.slider("Time range (days)", 1, 90, 7, key="dash_days")

    try:
        overview = client.get(f"/api/analytics/overview?project_id={project_id}&days={days}")
    except Exception:
        overview = {}

    total_traces  = overview.get("total_traces", 0)
    error_traces  = overview.get("error_traces", 0)
    error_rate    = overview.get("error_rate", 0)
    avg_latency   = overview.get("avg_latency_ms")
    total_cost    = overview.get("total_cost_usd", 0) or 0.0
    total_tokens  = overview.get("total_tokens", 0) or 0

    evals = client.list_evals(project_id)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Traces", f"{total_traces:,}")
    col2.metric("Successful", f"{total_traces - error_traces:,}")
    col3.metric("Errors", f"{error_traces:,}", delta=f"{error_rate:.1%} rate" if error_traces else None, delta_color="inverse")
    col4.metric("Avg Latency", f"{avg_latency:.0f} ms" if avg_latency else "—")
    col5.metric("Total Cost", f"${total_cost:.4f}")
    col6.metric("Evaluations", len(evals))

    st.divider()

    # ── Fetch all time-series and model data up front ─────────────────────────
    def _ts(metric):
        data = client.get(f"/api/analytics/timeseries?project_id={project_id}&metric={metric}&days={days}")
        series = (data or {}).get("series", [])
        if not series:
            return pd.DataFrame(columns=["date", "value"])
        df = pd.DataFrame(series)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date")

    def _layout(height=230):
        return dict(
            height=height,
            margin=dict(l=8, r=8, t=36, b=8),
            plot_bgcolor="white", paper_bgcolor="white",
            showlegend=False,
            font=dict(size=11),
            xaxis=dict(showgrid=True, gridcolor="#efefef", tickformat="%b %d"),
            yaxis=dict(showgrid=True, gridcolor="#efefef", rangemode="tozero"),
        )

    try:
        models_data = client.get(f"/api/analytics/models?project_id={project_id}&days={days}") or []
        df_models = pd.DataFrame(models_data) if models_data else pd.DataFrame()

        ts_traces  = _ts("trace_count")
        ts_latency = _ts("avg_latency")
        ts_cost    = _ts("total_cost")
        ts_tokens  = _ts("total_tokens")
        ts_errors  = _ts("error_count")

        # ── Row 1: Trace volume (bar) + Success vs Error (stacked bar) ────────
        st.subheader("📊 Volume & Reliability")
        r1c1, r1c2 = st.columns(2)

        with r1c1:
            fig = go.Figure()
            if not ts_traces.empty:
                fig.add_trace(go.Bar(
                    x=ts_traces["date"], y=ts_traces["value"],
                    marker_color="#636EFA", name="Traces",
                    text=ts_traces["value"].astype(int),
                    textposition="outside",
                ))
            layout = _layout()
            layout["title"] = dict(text="📦 Traces per Day", font=dict(size=13))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with r1c2:
            fig = go.Figure()
            if not ts_traces.empty and not ts_errors.empty:
                # Align on date
                merged = ts_traces.rename(columns={"value": "total"}).merge(
                    ts_errors.rename(columns={"value": "errors"}), on="date", how="left"
                ).fillna(0)
                merged["success"] = (merged["total"] - merged["errors"]).clip(lower=0)
                fig.add_trace(go.Bar(x=merged["date"], y=merged["success"],
                                     name="Success", marker_color="#00CC96"))
                fig.add_trace(go.Bar(x=merged["date"], y=merged["errors"],
                                     name="Errors", marker_color="#EF553B"))
                fig.update_layout(barmode="stack", showlegend=True,
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
            elif not ts_traces.empty:
                fig.add_trace(go.Bar(x=ts_traces["date"], y=ts_traces["value"],
                                     marker_color="#00CC96", name="Success"))
            layout = _layout()
            layout["title"] = dict(text="✅ Success vs ❌ Errors", font=dict(size=13))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        # ── Row 2: Latency trend (line+fill) + Token usage (area) ────────────
        st.subheader("⚡ Performance & Usage")
        r2c1, r2c2 = st.columns(2)

        with r2c1:
            fig = go.Figure()
            if not ts_latency.empty:
                fig.add_trace(go.Scatter(
                    x=ts_latency["date"], y=ts_latency["value"],
                    mode="lines+markers", fill="tozeroy",
                    line=dict(color="#EF553B", width=2),
                    marker=dict(size=7, color="#EF553B",
                                line=dict(width=2, color="white")),
                    name="Latency (ms)",
                    hovertemplate="%{y:.0f} ms<extra></extra>",
                ))
            layout = _layout()
            layout["title"] = dict(text="⏱️ Avg Latency (ms)", font=dict(size=13))
            layout["yaxis"]["ticksuffix"] = " ms"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with r2c2:
            fig = go.Figure()
            if not ts_tokens.empty:
                fig.add_trace(go.Scatter(
                    x=ts_tokens["date"], y=ts_tokens["value"],
                    mode="lines+markers", fill="tozeroy",
                    line=dict(color="#AB63FA", width=2),
                    marker=dict(size=7, color="#AB63FA",
                                line=dict(width=2, color="white")),
                    name="Tokens",
                    hovertemplate="%{y:,} tokens<extra></extra>",
                ))
            layout = _layout()
            layout["title"] = dict(text="🔤 Token Usage per Day", font=dict(size=13))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        # ── Row 3: Cost trend (step line) + Model comparison (horizontal bar) ─
        st.subheader("💰 Cost & Model Breakdown")
        r3c1, r3c2 = st.columns(2)

        with r3c1:
            fig = go.Figure()
            if not ts_cost.empty:
                fig.add_trace(go.Scatter(
                    x=ts_cost["date"], y=ts_cost["value"],
                    mode="lines+markers",
                    line=dict(color="#00CC96", width=2, shape="hv"),
                    marker=dict(size=8, color="#00CC96",
                                line=dict(width=2, color="white")),
                    fill="tozeroy",
                    fillcolor="rgba(0,204,150,0.12)",
                    name="Cost (USD)",
                    hovertemplate="$%{y:.5f}<extra></extra>",
                ))
            layout = _layout()
            layout["title"] = dict(text="💵 Cost (USD) per Day", font=dict(size=13))
            layout["yaxis"]["tickprefix"] = "$"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with r3c2:
            fig = go.Figure()
            if not df_models.empty and "model" in df_models.columns:
                cols_needed = ["model", "count", "avg_latency_ms", "total_tokens"]
                available = [c for c in cols_needed if c in df_models.columns]
                dm = df_models[available].copy().fillna(0).sort_values(
                    "count" if "count" in available else available[0], ascending=True
                )
                # Horizontal bar: trace count per model
                fig.add_trace(go.Bar(
                    y=dm["model"], x=dm["count"] if "count" in dm.columns else dm[available[0]],
                    orientation="h",
                    marker=dict(
                        color=dm["count"] if "count" in dm.columns else dm[available[0]],
                        colorscale="Viridis", showscale=False,
                    ),
                    text=dm["count"].astype(int) if "count" in dm.columns else None,
                    textposition="outside",
                    name="Traces",
                ))
            layout = _layout()
            layout["title"] = dict(text="🤖 Traces by Model", font=dict(size=13))
            layout["xaxis"]["title"] = "Trace count"
            layout["yaxis"].pop("rangemode", None)
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        # ── Row 4: Latency distribution (box) + Tokens vs Latency scatter ─────
        st.subheader("🔬 Deep Analysis")
        r4c1, r4c2 = st.columns(2)

        with r4c1:
            # Box plot of latency per model from model breakdown
            fig = go.Figure()
            if not df_models.empty and "model" in df_models.columns and "avg_latency_ms" in df_models.columns:
                dm = df_models[["model", "avg_latency_ms"]].dropna()
                for _, row in dm.iterrows():
                    fig.add_trace(go.Bar(
                        x=[row["model"]], y=[row["avg_latency_ms"]],
                        name=row["model"],
                        marker_color="#FFA15A",
                        text=[f"{row['avg_latency_ms']:.0f} ms"],
                        textposition="outside",
                    ))
            layout = _layout()
            layout["title"] = dict(text="⏱️ Avg Latency by Model (ms)", font=dict(size=13))
            layout["yaxis"]["ticksuffix"] = " ms"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with r4c2:
            # Scatter: tokens vs latency per model (bubble = trace count)
            fig = go.Figure()
            if not df_models.empty and {"model", "avg_latency_ms", "total_tokens"}.issubset(df_models.columns):
                dm = df_models[["model", "avg_latency_ms", "total_tokens", "count"]].fillna(0)
                fig.add_trace(go.Scatter(
                    x=dm["total_tokens"], y=dm["avg_latency_ms"],
                    mode="markers+text",
                    text=dm["model"],
                    textposition="top center",
                    marker=dict(
                        size=dm["count"].clip(lower=8) * 3,
                        color=dm["avg_latency_ms"],
                        colorscale="RdYlGn_r",
                        showscale=True,
                        colorbar=dict(title="ms", thickness=12),
                        line=dict(width=1, color="white"),
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Tokens: %{x:,}<br>"
                        "Latency: %{y:.0f} ms<extra></extra>"
                    ),
                ))
            layout = _layout(height=240)
            layout["title"] = dict(text="🔵 Tokens vs Latency (bubble = trace count)", font=dict(size=13))
            layout["xaxis"]["title"] = "Total tokens"
            layout["yaxis"]["title"] = "Avg latency (ms)"
            layout["yaxis"].pop("rangemode", None)
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"Could not load charts: {e}")

    st.divider()

    # ── Recent traces ─────────────────────────────────────────────────────────
    st.subheader("🕐 Recent Traces")
    traces = client.list_traces(project_id, limit=10)
    if traces:
        trace_data = []
        for t in traces:
            cost = t.get("cost_usd")
            trace_data.append({
                "ID": t["id"][:8] + "…",
                "Model": t.get("model", "N/A"),
                "Status": t.get("status", "unknown"),
                "Latency (ms)": f"{t.get('latency_ms', 0):.0f}" if t.get("latency_ms") else "—",
                "Cost": f"${cost:.6f}" if cost is not None else "—",
                "Date": (t.get("timestamp") or "")[:10],
            })
        st.dataframe(pd.DataFrame(trace_data), use_container_width=True, hide_index=True)
    else:
        st.info("No traces yet. Start by integrating the SDK!")



def render_settings():
    """Render API key settings page."""
    st.title("⚙️ Developer Settings")

    if not st.session_state.client:
        st.info("👈 Please login from the sidebar to manage API keys")
        return

    client = st.session_state.client

    # ── YOUR TRACEIQ API KEY ───────────────────────────────────────────────
    st.subheader("🔐 Your TraceIQ API Key")
    st.caption("Use this key to connect any external application so it can send traces here.")

    if "bt_api_key" not in st.session_state:
        st.session_state.bt_api_key = client.get_traciq_api_key()

    api_key_val = st.session_state.bt_api_key or ""

    col_key, col_btn = st.columns([4, 1])
    with col_key:
        st.text_input(
            "API Key",
            value=api_key_val,
            key="bt_api_key_display",
            disabled=True,
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("🔄 Regenerate", key="regen_bt_key"):
            new_key = client.regenerate_traciq_api_key()
            if new_key:
                st.session_state.bt_api_key = new_key
                st.success("API key regenerated. Update all integrations.")
                st.rerun()
            else:
                st.error("Failed to regenerate key.")

    base = "http://localhost:8000"  # swap for your real host when deployed
    with st.expander("📋 How to connect other applications", expanded=True):
        st.markdown("**Option 1 — curl (single trace)**")
        st.code(
            f'curl -X POST {base}/api/traces/ingest \\\n'
            f'     -H "X-API-Key: {api_key_val}" \\\n'
            f'     -H "Content-Type: application/json" \\\n'
            f'     -d \'{{\n'
            f'       "project_name": "YOUR_PROJECT_NAME",\n'
            f'       "model": "gpt-4o",\n'
            f'       "input_data": {{"prompt": "Hello"}},\n'
            f'       "output_data": {{"response": "Hi!"}},\n'
            f'       "latency_ms": 320,\n'
            f'       "total_tokens": 42\n'
            f'     }}\'',
            language="bash",
        )
        st.markdown("**Option 2 — Python SDK**")
        st.code(
            f'from sdk.traciq import TraceIQClient\n\n'
            f'client = TraceIQClient(\n'
            f'    api_key="{api_key_val}",\n'
            f'    base_url="{base}"\n'
            f')\n\n'
            f'client.trace(\n'
            f'    project_id="<your-project-uuid>",\n'
            f'    model="gpt-4o",\n'
            f'    input_data={{"prompt": "Hello"}},\n'
            f'    output_data={{"response": "Hi!"}},\n'
            f'    latency_ms=320,\n'
            f'    total_tokens=42,\n'
            f')\n'
            f'client.flush()',
            language="python",
        )
        st.markdown("**Option 3 — Any HTTP client (Authorization header)**")
        st.code(
            f'Authorization: Bearer {api_key_val}\n'
            f'# OR\n'
            f'X-API-Key: {api_key_val}',
            language="http",
        )
        st.info("💡 Traces appear in the **Traces** page after ingestion. Use `project_name` (human-readable) or `project_id` (UUID from the URL).")

    st.markdown("---")
    st.subheader("🔑 LLM Provider Keys")
    st.caption("Configure API keys for external LLM providers used in evaluations.")
    
    # Define providers
    providers = {
        "openai": {
            "name": "🔵 OpenAI",
            "placeholder": "sk-proj-xxxxx...",
            "has_model": False
        },
        "anthropic": {
            "name": "🟠 Anthropic",
            "placeholder": "sk-ant-xxxxx...",
            "has_model": False
        },
        "google": {
            "name": "🟡 Google",
            "placeholder": "AIzaSy-xxxxx...",
            "has_model": False
        },
        "ollama": {
            "name": "🟣 Ollama",
            "placeholder": "ollama",
            "has_model": True
        }
    }
    
    # Get current API keys
    current_keys = client.list_api_keys()
    current_services = {key["service"] for key in current_keys}
    
    # Create tabs for each provider
    provider_tabs = st.tabs([p["name"] for p in providers.values()])
    
    for tab, (service, provider_info) in zip(provider_tabs, providers.items()):
        with tab:
            st.write(f"**Configure {provider_info['name']} credentials**")
            
            has_key = service in current_services
            
            if has_key:
                st.success(f"✅ {service.upper()} credentials already configured")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Update {service}", key=f"update_{service}"):
                        st.session_state[f"show_update_{service}"] = True
                with col2:
                    if st.button(f"Delete {service}", key=f"delete_{service}"):
                        if client.delete_api_key(service):
                            st.success(f"✅ {service} API key deleted!")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to delete {service} API key")
                
                if st.session_state.get(f"show_update_{service}"):
                    st.write("**Enter new API key:**")
                    with st.form(f"update_form_{service}"):
                        api_key = st.text_input(
                            "API Key",
                            type="password",
                            placeholder=provider_info["placeholder"],
                            key=f"update_api_key_{service}"
                        )
                        
                        model = None
                        if provider_info["has_model"]:
                            model = st.text_input(
                                "Model Name (for Ollama)",
                                placeholder="e.g., llama2, mistral",
                                key=f"update_model_{service}"
                            )
                        
                        if st.form_submit_button(f"Update {service}"):
                            if api_key:
                                if client.update_api_key(service, api_key, model):
                                    st.success(f"✅ {service} API key updated!")
                                    st.session_state[f"show_update_{service}"] = False
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to update {service} API key")
                            else:
                                st.error("API key is required")
            else:
                st.write(f"**Add {provider_info['name']} credentials**")
                
                with st.form(f"add_form_{service}"):
                    api_key = st.text_input(
                        "API Key",
                        type="password",
                        placeholder=provider_info["placeholder"],
                        key=f"api_key_{service}"
                    )
                    
                    model = None
                    if provider_info["has_model"]:
                        model = st.text_input(
                            "Model Name (for Ollama)",
                            placeholder="e.g., llama2, mistral",
                            key=f"model_{service}"
                        )
                        st.caption("Run `ollama list` to see available models")
                    
                    if st.form_submit_button(f"Save {service}", use_container_width=True):
                        if api_key:
                            if client.save_api_key(service, api_key, model):
                                st.success(f"✅ {service} API key saved!")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to save {service} API key")
                        else:
                            st.error("API key is required")
    
    # Summary section
    st.markdown("---")
    st.subheader("📊 Configuration Summary")
    
    if current_keys:
        summary_data = []
        for key in current_keys:
            summary_data.append({
                "Service": key["service"].upper(),
                "Model": key.get("model") or "N/A",
                "Status": "✅ Active" if key["is_active"] else "⏸️ Inactive",
                "Added": key["created_at"][:10]
            })
        
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No API keys configured yet. Start by adding credentials above!")
    
    # Help section
    st.markdown("---")
    st.subheader("📖 Help")
    st.write("""
    **API Key Management Guide:**
    
    - **OpenAI**: Get your API key from https://platform.openai.com/api-keys
    - **Anthropic**: Get your API key from https://console.anthropic.com/
    - **Google**: Get your API key from https://makersuite.google.com/app/apikey
    - **Ollama**: Use 'ollama' as the API key, specify the model name (e.g., 'llama2')
    
    **Using stored keys:**
    - Select a model in the Model Settings sidebar
    - Create evaluations - they will use your configured API key
    - API keys are stored securely and never exposed in responses
    """)


def main():
    """Main app logic."""
    render_sidebar()

    if not st.session_state.jwt_token:
        st.title("🧠 TraceIQ Dashboard")
        st.write("👈 Login or register from the sidebar to get started")
        return

    client = st.session_state.client
    project = st.session_state.selected_project
    project_id = project["id"] if project else ""

    # Navigation
    PAGES = [
        ("📊 Dashboard", "dashboard"),
        ("📋 Traces", "traces"),
        ("🧪 Evaluations", "evaluations"),
        ("📈 Analytics", "analytics"),
        ("🔍 Deep Search", "search"),
        ("🏷️ Topics", "topics"),
        ("🤖 Loop AI", "loop"),
        ("📝 Prompts", "prompts"),
        ("⚡ Playground", "playground"),
        ("🧫 Experiments", "experiments"),
        ("📚 Datasets", "datasets"),
        ("✍️ Annotations", "annotations"),
        ("🌐 Gateway", "gateway"),
        ("🎯 Online Scoring", "online_scoring"),
        ("⚙️ Settings", "settings"),
        ("🔐 Admin", "admin"),
        ("🔍 BTQL Query", "btql"),
        ("🧪 Remote Evals", "remote_evals"),
        ("🔐 SSO Settings", "sso"),
        ("🔔 Alerts", "alerts"),
        ("🛡️ Data Masking", "masking"),
    ]

    with st.sidebar:
        st.divider()
        st.subheader("Navigation")
        page_labels = [p[0] for p in PAGES]
        selected_page = st.radio("Go to", page_labels, label_visibility="collapsed")

    page_key = dict(PAGES)[selected_page]

    # Guard for pages that need a project
    def _need_project():
        st.info("👈 Select or create a project from the sidebar")

    if page_key == "dashboard":
        render_dashboard()

    elif page_key == "traces":
        st.title("📋 Traces")
        if not project:
            _need_project(); return
        col1, col2 = st.columns(2)
        model_filter = col1.text_input("Filter by Model", placeholder="gpt-4")
        status_filter = col2.selectbox("Status", ["All", "success", "error"])
        traces = client.list_traces(
            project_id,
            model=model_filter or None,
            status=status_filter if status_filter != "All" else None,
        )
        st.write(f"Found {len(traces)} traces")
        for trace in traces[:50]:
            with st.expander(f"📌 {trace['id'][:12]}… | {trace.get('model','N/A')} | {trace.get('status')}"):
                st.json(trace)

    elif page_key == "evaluations":
        st.title("🧪 Evaluations")
        if not project:
            _need_project(); return
        with st.form("create_eval_form"):
            eval_name = st.text_input("Evaluation Name")
            eval_desc = st.text_area("Description")
            scorer_type = st.selectbox("Scorer Type", ["Expected Value", "LLM", "Code"])
            model = st.session_state.selected_model if scorer_type == "LLM" else None
            traces = client.list_traces(project_id, limit=100)
            trace_names = [f"{t['id'][:12]}… ({t.get('model','N/A')})" for t in traces]
            selected_trace_id = None
            if trace_names:
                sel = st.selectbox("Select Trace", trace_names)
                selected_trace_id = traces[trace_names.index(sel)]["id"]
            if st.form_submit_button("Run Evaluation"):
                if eval_name and selected_trace_id:
                    result = client.create_eval(
                        project_id, eval_name,
                        [{"name": scorer_type, "type": scorer_type.lower().replace(" ", "_"), "model": model}],
                        trace_id=selected_trace_id, description=eval_desc,
                    )
                    if result:
                        st.success(f"✅ Evaluation '{eval_name}' started!")
        st.subheader("Recent Evaluations")
        for ev in client.list_evals(project_id)[:10]:
            with st.expander(f"🧪 {ev['name']} | {ev['status']}"):
                st.json(ev)

    elif page_key == "analytics" and _NEW_PAGES:
        analytics.render(client, project_id)

    elif page_key == "search" and _NEW_PAGES:
        search.render(client, project_id)

    elif page_key == "topics" and _NEW_PAGES:
        topics.render(client, project_id)

    elif page_key == "loop" and _NEW_PAGES:
        loop.render(client, project_id)

    elif page_key == "prompts" and _NEW_PAGES:
        prompts.render(client, project_id)

    elif page_key == "playground" and _NEW_PAGES:
        playgrounds.render(client, project_id)

    elif page_key == "experiments" and _NEW_PAGES:
        experiments.render(client, project_id)

    elif page_key == "datasets" and _NEW_PAGES:
        datasets.render(client, project_id)

    elif page_key == "annotations" and _NEW_PAGES:
        annotations.render(client, project_id)

    elif page_key == "gateway" and _NEW_PAGES:
        gateway.render(client, project_id)

    elif page_key == "online_scoring" and _NEW_PAGES:
        online_scoring.render(client, project_id)

    elif page_key == "settings" and _NEW_PAGES:
        settings.render(client, project_id)

    elif page_key == "admin" and _NEW_PAGES:
        admin.render(client, project_id)

    elif page_key == "btql" and _NEW_PAGES:
        btql.render(client, project_id)

    elif page_key == "remote_evals" and _NEW_PAGES:
        remote_evals.render(client, project_id)

    elif page_key == "sso" and _NEW_PAGES:
        sso.render(client)

    elif page_key == "alerts" and _NEW_PAGES:
        alerts.render(client)

    elif page_key == "masking" and _NEW_PAGES:
        masking.render(client)

    else:
        if not _NEW_PAGES:
            st.error(f"Page import failed: {_PAGE_IMPORT_ERROR}")
        else:
            st.info("Page not available — ensure all backend services are running.")


if __name__ == "__main__":
    main()

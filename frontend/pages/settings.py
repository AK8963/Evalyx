"""
Settings page — API keys, environments, alerts, webhooks, and export.
Mirrors TraceIQ admin / settings area.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("⚙️ Settings")
    st.caption("Manage API keys, environments, alert rules, webhooks, and data export.")

    tab_keys, tab_envs, tab_pricing, tab_alerts, tab_webhooks, tab_export = st.tabs([
        "🔑 API Keys", "🌍 Environments", "💰 Model Pricing", "🔔 Alerts", "🔗 Webhooks", "📤 Export"
    ])

    # ── API Keys ─────────────────────────────────────────────────────────────
    with tab_keys:
        # ── YOUR TRACIQ SDK KEY ──────────────────────────────────────────────
        st.subheader("🔐 Your TraceIQ SDK Key")
        st.caption(
            "Use this key in any external app with the TraceIQ SDK to send traces, "
            "run evaluations, and connect to this platform."
        )

        if "sdk_api_key" not in st.session_state:
            st.session_state.sdk_api_key = None

        try:
            if st.session_state.sdk_api_key is None:
                st.session_state.sdk_api_key = client.get_traciq_api_key()
        except Exception:
            pass

        sdk_key = st.session_state.sdk_api_key

        if sdk_key:
            col_key, col_btn = st.columns([3, 1])
            show = col_key.toggle("Show key", value=False, key="show_sdk_key")
            display_val = sdk_key if show else sdk_key[:12] + "•" * 20
            col_key.code(display_val, language=None)
            if col_btn.button("🔄 Regenerate", key="regen_sdk_key"):
                try:
                    st.session_state.sdk_api_key = client.regenerate_traciq_api_key()
                    st.success("Key regenerated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

            st.markdown("**Quick-start snippet:**")
            snippet = (
                f'import traciq\n\n'
                f'client = traciq.init(\n'
                f'    api_key="{sdk_key}",\n'
                f'    base_url="http://localhost:8000"\n'
                f')\n\n'
                f'# Log a trace\n'
                f'trace_id = client.trace(\n'
                f'    project_id="{project_id}",\n'
                f'    input={{"prompt": "Hello, world!"}},\n'
                f'    output={{"response": "Hi!"}},\n'
                f'    model="gpt-4o"\n'
                f')'
            )
            st.code(snippet, language="python")
        else:
            if st.button("Generate SDK Key", key="gen_sdk_key"):
                try:
                    st.session_state.sdk_api_key = client.regenerate_traciq_api_key()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating key: {e}")

        st.divider()
        st.subheader("🔑 External API Keys")
        st.caption("Store API keys for OpenAI, Anthropic, Google, and Ollama. Keys are saved per user.")

        try:
            keys = client.get("/api/settings/api-keys")
        except Exception as e:
            st.error(f"Error loading keys: {e}")
            keys = []

        if keys:
            df = pd.DataFrame([
                {
                    "Service": k["service"],
                    "Model": k.get("model") or "—",
                    "Active": "✅" if k["is_active"] else "❌",
                    "Added": (k.get("created_at") or "")[:10],
                    "ID": k["id"],
                }
                for k in keys
            ])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

            del_id = st.selectbox("Delete key", [""] + [f"{k['service']} ({k['id'][:8]})" for k in keys], key="del_key_sel")
            if del_id and st.button("🗑️ Delete selected key", key="del_key_btn"):
                key_id = keys[[f"{k['service']} ({k['id'][:8]})" for k in keys].index(del_id)]["id"]
                try:
                    client.delete(f"/api/settings/api-keys/{key_id}")
                    st.success("Key deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No API keys saved yet.")

        st.divider()
        st.subheader("Add API Key")
        with st.form("add_api_key"):
            service = st.selectbox("Service", ["openai", "anthropic", "google", "ollama"])
            api_key_val = st.text_input("API Key", type="password")
            model_name = st.text_input("Model (Ollama only)", placeholder="e.g. llama3.2")
            if st.form_submit_button("💾 Save"):
                if not api_key_val:
                    st.error("API key is required")
                else:
                    try:
                        client.post("/api/settings/api-keys", json={
                            "service": service,
                            "api_key": api_key_val,
                            "model": model_name or None,
                        })
                        st.success(f"✅ {service} key saved.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── Environments ─────────────────────────────────────────────────────────
    with tab_envs:
        st.subheader("🌍 Deployment Environments")
        st.caption("Separate dev, staging, and production prompt/model configurations.")

        try:
            envs = client.get(f"/api/environments/?project_id={project_id}")
        except Exception as e:
            st.error(f"Error loading environments: {e}")
            envs = []

        if envs:
            df = pd.DataFrame([
                {
                    "Name": e["name"],
                    "Slug": e["slug"],
                    "Production": "🟢" if e.get("is_production") else "—",
                    "Active": "✅" if e.get("is_active") else "❌",
                    "Description": e.get("description") or "—",
                    "ID": e["id"],
                }
                for e in envs
            ])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

            del_env = st.selectbox("Delete environment", [""] + [e["name"] for e in envs], key="del_env_sel")
            if del_env and st.button("🗑️ Delete", key="del_env_btn"):
                env_id = next(e["id"] for e in envs if e["name"] == del_env)
                try:
                    client.delete(f"/api/environments/{env_id}")
                    st.success(f"Deleted environment '{del_env}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No environments configured. Create production, staging, and dev environments.")

        st.divider()
        st.subheader("Create Environment")
        with st.form("create_env"):
            env_name = st.text_input("Name", placeholder="production")
            env_desc = st.text_input("Description (optional)")
            env_is_prod = st.checkbox("Mark as production environment")
            if st.form_submit_button("➕ Create"):
                if not env_name:
                    st.error("Name is required")
                else:
                    try:
                        client.post("/api/environments/", json={
                            "project_id": project_id,
                            "name": env_name,
                            "description": env_desc or None,
                            "is_production": env_is_prod,
                        })
                        st.success(f"✅ Environment '{env_name}' created.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── Model Pricing ─────────────────────────────────────────────────────────
    with tab_pricing:
        st.subheader("💰 Per-Model Cost Overrides")
        st.caption(
            "Set custom prices for models you use (e.g. negotiated contract rates). "
            "These take priority over the built-in pricing table at trace-ingest time. "
            "**Ollama / local models are always $0.00** regardless of what is entered here."
        )

        # ── Current custom overrides ─────────────────────────────────────────
        try:
            custom = client.get("/api/pricing/custom") or []
        except Exception as e:
            st.error(f"Error loading custom pricing: {e}")
            custom = []

        if custom:
            df_custom = pd.DataFrame([
                {
                    "Model": r["model"],
                    "Provider": r.get("provider") or "—",
                    "Prompt ($/1k)": f"${float(r['prompt_cost_per_1k']):.6f}",
                    "Completion ($/1k)": f"${float(r['completion_cost_per_1k']):.6f}",
                    "Free (local)": "✅" if r["is_free"] else "—",
                    "Notes": r.get("notes") or "—",
                }
                for r in custom
            ])
            st.dataframe(df_custom, use_container_width=True, hide_index=True)

            del_model = st.selectbox(
                "Remove override", [""] + [r["model"] for r in custom], key="del_pricing_model"
            )
            if del_model and st.button("🗑️ Delete override", key="del_pricing_btn"):
                try:
                    client.delete(f"/api/pricing/custom/{del_model}")
                    st.success(f"Deleted pricing override for **{del_model}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No custom overrides yet — using built-in pricing table for all models.")

        st.divider()
        st.subheader("Add / Update Override")

        # Pre-fill from built-in table
        col_m, col_p = st.columns([2, 1])
        new_model = col_m.text_input("Model name", placeholder="gpt-4o", key="pricing_model_name")
        is_free = col_p.checkbox("🆓 Local / Ollama (free)", key="pricing_is_free")

        with st.form("add_pricing_form"):
            provider = st.text_input("Provider (optional)", placeholder="openai / anthropic / local …")
            col1, col2 = st.columns(2)
            prompt_rate = col1.number_input(
                "Prompt cost ($ per 1,000 tokens)",
                min_value=0.0, value=0.005, step=0.0001, format="%.6f",
                disabled=is_free, key="pricing_prompt_rate",
            )
            completion_rate = col2.number_input(
                "Completion cost ($ per 1,000 tokens)",
                min_value=0.0, value=0.015, step=0.0001, format="%.6f",
                disabled=is_free, key="pricing_completion_rate",
            )
            notes = st.text_input("Notes (optional)", placeholder="Negotiated enterprise rate")

            if st.form_submit_button("💾 Save Override"):
                if not new_model:
                    st.error("Model name is required.")
                else:
                    try:
                        client.post("/api/pricing/custom", json={
                            "model": new_model.strip(),
                            "provider": provider.strip() or None,
                            "prompt_cost_per_1k": 0.0 if is_free else prompt_rate,
                            "completion_cost_per_1k": 0.0 if is_free else completion_rate,
                            "is_free": is_free,
                            "notes": notes.strip() or None,
                        })
                        st.success(f"✅ Override saved for **{new_model}**.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        st.divider()

        # ── Built-in pricing reference ────────────────────────────────────────
        with st.expander("📋 Built-in Pricing Reference (read-only)", expanded=False):
            try:
                all_pricing = client.get("/api/pricing") or []
                if all_pricing:
                    df_all = pd.DataFrame(all_pricing)
                    provider_filter = st.selectbox(
                        "Filter by provider",
                        ["All"] + sorted(set(r.get("provider", "unknown") for r in all_pricing)),
                        key="ref_pricing_provider",
                    )
                    if provider_filter != "All":
                        df_all = df_all[df_all["provider"] == provider_filter]
                    df_all = df_all.rename(columns={
                        "model": "Model",
                        "provider": "Provider",
                        "prompt_cost_per_1k_tokens": "Prompt ($/1k)",
                        "completion_cost_per_1k_tokens": "Completion ($/1k)",
                        "is_free": "Free",
                    })
                    st.dataframe(df_all, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Could not load reference table: {e}")

    # ── Alerts ───────────────────────────────────────────────────────────────
    with tab_alerts:
        st.subheader("🔔 Alert Rules")
        st.caption("Fire webhooks when a metric crosses a threshold (e.g. error rate > 10%).")

        try:
            alerts = client.get(f"/api/automations/alerts?project_id={project_id}")
        except Exception as e:
            st.error(f"Error loading alerts: {e}")
            alerts = []

        if alerts:
            df = pd.DataFrame([
                {
                    "Name": a["name"],
                    "Metric": a["metric"],
                    "Condition": a["condition"],
                    "Threshold": a["threshold"],
                    "Window (min)": a["window_minutes"],
                    "Webhook": "✅" if a.get("webhook_url") else "—",
                    "Active": "✅" if a["is_active"] else "❌",
                    "Last Fired": (a.get("last_fired_at") or "never")[:19],
                    "ID": a["id"],
                }
                for a in alerts
            ])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

            toggle_alert = st.selectbox("Toggle alert on/off", [""] + [a["name"] for a in alerts], key="toggle_alert")
            if toggle_alert and st.button("🔄 Toggle", key="toggle_btn"):
                alert = next(a for a in alerts if a["name"] == toggle_alert)
                try:
                    client.patch(f"/api/automations/alerts/{alert['id']}", json={"is_active": not alert["is_active"]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No alert rules configured.")

        st.divider()
        st.subheader("Create Alert Rule")
        metrics = ["avg_score", "error_rate", "latency_p99", "latency_avg", "cost_usd", "trace_count"]
        with st.form("create_alert"):
            al_name = st.text_input("Alert name", placeholder="Score drops below 0.7")
            al_metric = st.selectbox("Metric", metrics)
            al_cond = st.selectbox("Condition", ["lt", "gt", "eq"], format_func=lambda x: {"lt": "< less than", "gt": "> greater than", "eq": "= equals"}[x])
            al_threshold = st.number_input("Threshold", value=0.7, step=0.01, format="%.3f")
            al_window = st.number_input("Window (minutes)", value=60, min_value=1, max_value=10080)
            al_webhook = st.text_input("Webhook URL (optional)", placeholder="https://hooks.slack.com/...")
            if st.form_submit_button("🔔 Create Alert"):
                if not al_name:
                    st.error("Name is required")
                else:
                    try:
                        client.post("/api/automations/alerts", json={
                            "project_id": project_id,
                            "name": al_name,
                            "metric": al_metric,
                            "condition": al_cond,
                            "threshold": al_threshold,
                            "window_minutes": int(al_window),
                            "webhook_url": al_webhook or None,
                        })
                        st.success(f"✅ Alert '{al_name}' created.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── Webhooks ──────────────────────────────────────────────────────────────
    with tab_webhooks:
        st.subheader("🔗 Outbound Webhooks")
        st.caption("Receive real-time event notifications when traces, evals, or alerts fire.")

        try:
            webhooks = client.get(f"/api/automations/webhooks?project_id={project_id}")
        except Exception as e:
            st.error(f"Error loading webhooks: {e}")
            webhooks = []

        if webhooks:
            df = pd.DataFrame([
                {
                    "Name": w["name"],
                    "URL": w["url"][:60] + ("…" if len(w["url"]) > 60 else ""),
                    "Events": ", ".join(w.get("events") or []),
                    "Secret": "🔒 set" if w.get("has_secret") else "—",
                    "Active": "✅" if w["is_active"] else "❌",
                    "ID": w["id"],
                }
                for w in webhooks
            ])
            st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

            test_wh = st.selectbox("Test webhook", [""] + [w["name"] for w in webhooks], key="test_wh_sel")
            if test_wh and st.button("📡 Send test ping", key="test_wh_btn"):
                wh = next(w for w in webhooks if w["name"] == test_wh)
                try:
                    result = client.post(f"/api/automations/webhooks/{wh['id']}/test", json={})
                    if result.get("success"):
                        st.success(f"✅ Test ping sent (HTTP {result.get('status_code')})")
                    else:
                        st.warning(f"Webhook responded with HTTP {result.get('status_code')}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No webhooks configured.")

        st.divider()
        st.subheader("Register Webhook")
        all_events = ["trace.created", "eval.completed", "alert.fired", "experiment.completed", "annotation.created"]
        with st.form("create_webhook"):
            wh_name = st.text_input("Name", placeholder="My Slack Webhook")
            wh_url = st.text_input("URL", placeholder="https://hooks.slack.com/services/...")
            wh_secret = st.text_input("Signing Secret (optional)", type="password")
            wh_events = st.multiselect("Events to subscribe", all_events, default=["eval.completed", "alert.fired"])
            if st.form_submit_button("🔗 Register Webhook"):
                if not wh_name or not wh_url:
                    st.error("Name and URL are required")
                else:
                    try:
                        client.post("/api/automations/webhooks", json={
                            "project_id": project_id,
                            "name": wh_name,
                            "url": wh_url,
                            "secret": wh_secret or None,
                            "events": wh_events,
                        })
                        st.success(f"✅ Webhook '{wh_name}' registered.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ── Export ────────────────────────────────────────────────────────────────
    with tab_export:
        st.subheader("📤 Data Export")
        st.caption("Download traces, datasets, or experiment results as JSON, JSONL, or CSV.")

        export_type = st.radio("What to export", ["Traces", "Dataset", "Experiment"], horizontal=True)

        if export_type == "Traces":
            col1, col2 = st.columns(2)
            with col1:
                ex_format = st.selectbox("Format", ["json", "jsonl", "csv"], key="ex_fmt_traces")
                ex_limit = st.number_input("Max rows", 100, 10000, 1000, key="ex_limit")
            with col2:
                ex_status = st.selectbox("Status filter", ["", "success", "error", "partial"], key="ex_status")
            export_url = f"/api/export/traces?project_id={project_id}&format={ex_format}&limit={ex_limit}"
            if ex_status:
                export_url += f"&status={ex_status}"
            if st.button("⬇️ Download Traces", key="dl_traces"):
                try:
                    data = client.get_raw(export_url)
                    ext = "jsonl" if ex_format == "jsonl" else ex_format
                    st.download_button(f"Save traces.{ext}", data, file_name=f"traces.{ext}")
                except Exception as e:
                    st.error(f"Error: {e}")

        elif export_type == "Dataset":
            try:
                datasets_list = client.get(f"/api/datasets?project_id={project_id}")
            except Exception:
                datasets_list = []
            if not datasets_list:
                st.info("No datasets found in this project.")
            else:
                ds_names = {d["name"]: d["id"] for d in datasets_list}
                ds_name = st.selectbox("Dataset", list(ds_names.keys()))
                ds_id = ds_names[ds_name]
                ex_format = st.selectbox("Format", ["json", "jsonl", "csv"], key="ex_fmt_ds")
                if st.button("⬇️ Download Dataset", key="dl_ds"):
                    try:
                        data = client.get_raw(f"/api/export/datasets/{ds_id}?format={ex_format}")
                        ext = "jsonl" if ex_format == "jsonl" else ex_format
                        st.download_button(f"Save {ds_name}.{ext}", data, file_name=f"{ds_name}.{ext}")
                    except Exception as e:
                        st.error(f"Error: {e}")

        else:  # Experiment
            try:
                exps_list = client.get(f"/api/experiments?project_id={project_id}")
            except Exception:
                exps_list = []
            if not exps_list:
                st.info("No experiments found in this project.")
            else:
                exp_names = {e["name"]: e["id"] for e in exps_list}
                exp_name = st.selectbox("Experiment", list(exp_names.keys()))
                exp_id = exp_names[exp_name]
                ex_format = st.selectbox("Format", ["json", "jsonl", "csv"], key="ex_fmt_exp")
                if st.button("⬇️ Download Experiment", key="dl_exp"):
                    try:
                        data = client.get_raw(f"/api/export/experiments/{exp_id}?format={ex_format}")
                        ext = "jsonl" if ex_format == "jsonl" else ex_format
                        st.download_button(f"Save {exp_name}.{ext}", data, file_name=f"{exp_name}.{ext}")
                    except Exception as e:
                        st.error(f"Error: {e}")


if __name__ == "__main__":
    import os
    _base_url = os.getenv("BACKEND_API_URL", "http://traciq_backend:8000")
    if "jwt_token" not in st.session_state or not st.session_state.jwt_token:
        st.warning("⚠️ Please login from the main **app** page first.")
        st.stop()
    _client = st.session_state.client
    _project_id = st.session_state.selected_project.get("id", "")
    render(_client, _project_id)

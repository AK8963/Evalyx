"""
SSO Settings page — Phase 3 Enterprise.
"""

import streamlit as st
from api_client import APIClient


def render(client: APIClient):
    st.header("🔐 SSO / OIDC Settings")
    st.caption("Configure Single Sign-On for your organisation via OIDC (OpenID Connect).")

    org_id = st.text_input("Organisation ID", help="The organisation you want to configure SSO for.")
    if not org_id:
        st.info("Enter your Organisation ID above to manage SSO settings.")
        return

    tab_cfg, tab_login = st.tabs(["Configuration", "Test & Login URL"])

    with tab_cfg:
        st.subheader("OIDC Configuration")

        # Fetch existing config
        existing = {}
        try:
            existing = client.get(f"/api/sso/{org_id}/config") or {}
        except Exception:
            pass

        with st.form("sso_config_form"):
            provider_type = st.selectbox("Provider Type", ["oidc", "saml"],
                                         index=0 if existing.get("provider_type", "oidc") == "oidc" else 1)
            issuer_url = st.text_input("OIDC Issuer URL",
                                       value=existing.get("oidc_issuer_url", ""),
                                       placeholder="https://accounts.google.com")
            client_id = st.text_input("Client ID",
                                      value=existing.get("oidc_client_id", ""))
            client_secret = st.text_input("Client Secret",
                                          value="",
                                          type="password",
                                          placeholder="Leave blank to keep existing")
            scopes_raw = st.text_input("Scopes (space-separated)",
                                       value=" ".join(existing.get("oidc_scopes") or ["openid", "email", "profile"]))
            allowed_domains_raw = st.text_input(
                "Allowed Email Domains (comma-separated, blank = all)",
                value=", ".join(existing.get("allowed_domains") or [])
            )
            auto_provision = st.checkbox("Auto-provision new users",
                                         value=existing.get("auto_provision_users", True))
            default_role = st.selectbox("Default role for new users",
                                        ["viewer", "member", "admin"],
                                        index=["viewer", "member", "admin"].index(
                                            existing.get("default_role", "viewer")))
            is_enabled = st.checkbox("Enable SSO", value=existing.get("is_enabled", True))

            submitted = st.form_submit_button("💾 Save Configuration")
            if submitted:
                payload = {
                    "provider_type": provider_type,
                    "oidc_issuer_url": issuer_url,
                    "oidc_client_id": client_id,
                    "oidc_scopes": scopes_raw.split() if scopes_raw else ["openid", "email", "profile"],
                    "allowed_domains": [d.strip() for d in allowed_domains_raw.split(",") if d.strip()],
                    "auto_provision_users": auto_provision,
                    "default_role": default_role,
                    "is_enabled": is_enabled,
                }
                if client_secret:
                    payload["oidc_client_secret"] = client_secret
                try:
                    result = client.post(f"/api/sso/{org_id}/config", payload)
                    st.success("SSO configuration saved!")
                    st.json(result)
                except Exception as e:
                    st.error(f"Failed to save: {e}")

        if existing:
            if st.button("🗑 Disable SSO for this organisation", type="secondary"):
                try:
                    client.delete(f"/api/sso/{org_id}/config")
                    st.success("SSO disabled.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_login:
        st.subheader("Test & Login URL")
        if st.button("🔍 Test OIDC Metadata Fetch"):
            try:
                result = client.post(f"/api/sso/{org_id}/test", {})
                if result.get("ok"):
                    st.success("OIDC provider reachable!")
                    st.json(result)
                else:
                    st.error(f"Error: {result.get('error')}")
            except Exception as e:
                st.error(str(e))

        base_url = st.text_input("Backend base URL", value="http://localhost:8000")
        login_url = f"{base_url}/api/sso/{org_id}/login"
        st.markdown(f"**Login URL:** [{login_url}]({login_url})")
        st.code(login_url)
        saml_url = f"{base_url}/api/sso/saml/{org_id}/metadata"
        st.markdown(f"**SAML SP Metadata:** [{saml_url}]({saml_url})")

    st.divider()
    st.subheader("Active SSO Providers")
    try:
        providers = client.get("/api/sso/providers") or {}
        items = providers.get("providers", [])
        if items:
            import pandas as pd
            st.dataframe(pd.DataFrame(items), use_container_width=True)
        else:
            st.info("No active SSO providers configured.")
    except Exception as e:
        st.warning(f"Could not load providers: {e}")

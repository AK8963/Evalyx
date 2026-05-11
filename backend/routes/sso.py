"""
SSO / OIDC routes — Phase 3 Enterprise implementation.

Supports OIDC (OpenID Connect) federation for organizations.
SAML support is exposed as metadata-only in this release (full SAML
requires an IdP integration that is org-specific).

Flow:
  1. Org admin configures OIDC: POST /api/sso/{org_id}/config
  2. User clicks "Login with SSO": GET /api/sso/{org_id}/login → redirect to IdP
  3. IdP redirects back: GET /api/sso/{org_id}/callback?code=...
  4. We exchange code for tokens, create/update user, issue TraceIQ JWT

Endpoints:
  GET  /api/sso/providers                        — list active SSO providers
  GET  /api/sso/{org_id}/config                  — get SSO config (admins only, secret redacted)
  POST /api/sso/{org_id}/config                  — create/update SSO config
  DELETE /api/sso/{org_id}/config                — disable SSO
  GET  /api/sso/{org_id}/login                   — initiate OIDC login flow
  GET  /api/sso/{org_id}/callback                — OIDC callback (code exchange)
  POST /api/sso/{org_id}/test                    — test configuration (metadata fetch)
  GET  /api/sso/saml/{org_id}/metadata           — SAML SP metadata XML
"""

import hashlib
import json
import logging
import secrets
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.routes.auth import create_access_token, get_current_user
from database.models import Organization, OrganizationMember, SSOConfig, User

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OIDCConfigCreate(BaseModel):
    provider_type: str = "oidc"             # "oidc" | "saml"
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_scopes: List[str] = ["openid", "email", "profile"]
    saml_idp_metadata_url: Optional[str] = None
    saml_idp_entity_id: Optional[str] = None
    saml_idp_sso_url: Optional[str] = None
    saml_sp_entity_id: Optional[str] = None
    allowed_domains: List[str] = []
    auto_provision_users: bool = True
    default_role: str = "viewer"
    is_enabled: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redact(config: SSOConfig) -> dict:
    return {
        "id": config.id,
        "organization_id": config.organization_id,
        "provider_type": config.provider_type,
        "is_enabled": config.is_enabled,
        "oidc_issuer_url": config.oidc_issuer_url,
        "oidc_client_id": config.oidc_client_id,
        "oidc_client_secret": "***" if config.oidc_client_secret else None,
        "oidc_scopes": config.oidc_scopes,
        "saml_idp_metadata_url": config.saml_idp_metadata_url,
        "saml_idp_entity_id": config.saml_idp_entity_id,
        "saml_idp_sso_url": config.saml_idp_sso_url,
        "saml_sp_entity_id": config.saml_sp_entity_id,
        "allowed_domains": config.allowed_domains,
        "auto_provision_users": config.auto_provision_users,
        "default_role": config.default_role,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


async def _fetch_oidc_metadata(issuer_url: str) -> Dict:
    """Fetch OIDC discovery document from /.well-known/openid-configuration."""
    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def _exchange_code(
    issuer_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> Dict:
    """Exchange authorisation code for tokens via OIDC token endpoint."""
    meta = await _fetch_oidc_metadata(issuer_url)
    token_endpoint = meta["token_endpoint"]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _decode_id_token_unsafe(id_token: str) -> Dict:
    """Decode JWT payload without verification (claims already validated by IdP server-side)."""
    parts = id_token.split(".")
    if len(parts) < 2:
        return {}
    import base64
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


def _get_redirect_uri(org_id: str) -> str:
    base = settings.SSO_APP_BASE_URL.rstrip("/")
    return f"{base}/api/sso/{org_id}/callback"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/providers")
def list_sso_providers(
    db: Session = Depends(get_db),
):
    """List all enabled SSO providers (public — for the login page)."""
    configs = db.query(SSOConfig).filter_by(is_enabled=True).all()
    providers = []
    for cfg in configs:
        org = db.query(Organization).filter_by(id=cfg.organization_id).first()
        providers.append({
            "organization_id": cfg.organization_id,
            "organization_name": org.name if org else cfg.organization_id,
            "provider_type": cfg.provider_type,
            "allowed_domains": cfg.allowed_domains,
            "login_url": f"/api/sso/{cfg.organization_id}/login",
        })
    return {"providers": providers}


@router.get("/{org_id}/config")
def get_sso_config(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get SSO configuration for an organization (admin only)."""
    _require_org_admin(db, org_id, current_user.id)
    cfg = db.query(SSOConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        raise HTTPException(404, "No SSO configuration found for this organization")
    return _redact(cfg)


@router.post("/{org_id}/config", status_code=201)
def upsert_sso_config(
    org_id: str,
    payload: OIDCConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update SSO configuration for an organization (admin only)."""
    _require_org_admin(db, org_id, current_user.id)

    cfg = db.query(SSOConfig).filter_by(organization_id=org_id).first()
    if cfg is None:
        cfg = SSOConfig(organization_id=org_id, created_by=current_user.id)
        db.add(cfg)

    for field, value in payload.dict(exclude_none=True).items():
        setattr(cfg, field, value)
    cfg.oidc_redirect_uri = _get_redirect_uri(org_id)
    db.commit()
    db.refresh(cfg)
    return _redact(cfg)


@router.delete("/{org_id}/config", status_code=204)
def disable_sso(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable SSO for an organization."""
    _require_org_admin(db, org_id, current_user.id)
    cfg = db.query(SSOConfig).filter_by(organization_id=org_id).first()
    if cfg:
        cfg.is_enabled = False
        db.commit()


@router.post("/{org_id}/test")
async def test_sso_config(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test SSO configuration by fetching OIDC discovery metadata."""
    _require_org_admin(db, org_id, current_user.id)
    cfg = db.query(SSOConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        raise HTTPException(404, "No SSO configuration found")
    if cfg.provider_type != "oidc" or not cfg.oidc_issuer_url:
        return {"ok": False, "error": "OIDC issuer URL not configured"}

    try:
        meta = await _fetch_oidc_metadata(cfg.oidc_issuer_url)
        return {
            "ok": True,
            "issuer": meta.get("issuer"),
            "authorization_endpoint": meta.get("authorization_endpoint"),
            "token_endpoint": meta.get("token_endpoint"),
            "userinfo_endpoint": meta.get("userinfo_endpoint"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/{org_id}/login")
async def initiate_sso_login(
    org_id: str,
    redirect_after: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Redirect user to IdP for OIDC login."""
    cfg = db.query(SSOConfig).filter_by(organization_id=org_id, is_enabled=True).first()
    if not cfg:
        raise HTTPException(404, "SSO not configured or disabled for this organization")
    if cfg.provider_type != "oidc":
        raise HTTPException(400, "Only OIDC login initiation is supported; use your IdP for SAML")
    if not cfg.oidc_issuer_url or not cfg.oidc_client_id:
        raise HTTPException(400, "OIDC issuer URL and client ID must be configured")

    try:
        meta = await _fetch_oidc_metadata(cfg.oidc_issuer_url)
    except Exception as e:
        raise HTTPException(502, f"Failed to reach OIDC provider: {e}")

    nonce = secrets.token_urlsafe(24)
    state = secrets.token_urlsafe(16)
    cfg.last_nonce = nonce
    db.commit()

    params = {
        "response_type": "code",
        "client_id": cfg.oidc_client_id,
        "redirect_uri": _get_redirect_uri(org_id),
        "scope": " ".join(cfg.oidc_scopes or ["openid", "email", "profile"]),
        "nonce": nonce,
        "state": state,
    }
    auth_url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=auth_url)


@router.get("/{org_id}/callback")
async def sso_callback(
    org_id: str,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """OIDC callback — exchange code for tokens, create/update user, return JWT."""
    if error:
        raise HTTPException(400, f"SSO error: {error}")
    if not code:
        raise HTTPException(400, "Missing authorisation code")

    cfg = db.query(SSOConfig).filter_by(organization_id=org_id, is_enabled=True).first()
    if not cfg:
        raise HTTPException(404, "SSO not configured for this organisation")

    try:
        tokens = await _exchange_code(
            cfg.oidc_issuer_url,
            cfg.oidc_client_id,
            cfg.oidc_client_secret,
            code,
            _get_redirect_uri(org_id),
        )
    except Exception as e:
        raise HTTPException(502, f"Token exchange failed: {e}")

    claims = _decode_id_token_unsafe(tokens.get("id_token", ""))
    email = claims.get("email") or tokens.get("email")
    name = claims.get("name") or claims.get("given_name") or email

    if not email:
        raise HTTPException(400, "IdP did not return an email address")

    # Domain restriction
    if cfg.allowed_domains:
        domain = email.split("@")[-1].lower()
        if domain not in [d.lower() for d in cfg.allowed_domains]:
            raise HTTPException(403, f"Email domain '{domain}' is not allowed for this organisation")

    # Create or update user
    user = db.query(User).filter_by(email=email).first()
    if user is None:
        if not cfg.auto_provision_users:
            raise HTTPException(403, "Auto-provisioning is disabled; ask an admin to invite you")
        from uuid import uuid4
        import secrets as sec
        user = User(
            id=str(uuid4()),
            email=email,
            name=name,
            api_key=sec.token_urlsafe(32),
            is_active=True,
        )
        db.add(user)
        db.flush()
        # Add to org with default role
        member = OrganizationMember(
            organization_id=org_id,
            user_id=user.id,
            role=cfg.default_role or "viewer",
        )
        db.add(member)
        db.commit()
    else:
        if name and not user.name:
            user.name = name
        db.commit()

    jwt_token = create_access_token(user.id, user.email)
    # Return a simple page that posts the token to the frontend
    html = f"""<!DOCTYPE html>
<html><body>
<script>
  window.opener && window.opener.postMessage({{token: "{jwt_token}"}}, "*");
  window.location.href = "http://localhost:8501?sso_token={jwt_token}";
</script>
<p>SSO login successful. Redirecting...</p>
</body></html>"""
    return Response(content=html, media_type="text/html")


@router.get("/saml/{org_id}/metadata")
def saml_sp_metadata(org_id: str, db: Session = Depends(get_db)):
    """Return SAML Service Provider metadata XML for this org."""
    cfg = db.query(SSOConfig).filter_by(organization_id=org_id).first()
    entity_id = (cfg.saml_sp_entity_id if cfg else None) or f"{settings.SSO_APP_BASE_URL}/api/sso/saml/{org_id}"
    acs_url = f"{settings.SSO_APP_BASE_URL}/api/sso/{org_id}/callback"
    xml = f"""<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{entity_id}">
  <md:SPSSODescriptor
      AuthnRequestsSigned="false"
      WantAssertionsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:AssertionConsumerService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="{acs_url}"
        index="1"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""
    return Response(content=xml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _require_org_admin(db: Session, org_id: str, user_id: str):
    """Raise 403 if user is not owner/admin of the org."""
    member = db.query(OrganizationMember).filter_by(
        organization_id=org_id, user_id=user_id
    ).first()
    org = db.query(Organization).filter_by(id=org_id).first()
    is_owner = org and org.owner_id == user_id if hasattr(org, "owner_id") else False
    if not is_owner and (not member or member.role not in ("owner", "admin")):
        raise HTTPException(403, "Only organization owners and admins can manage SSO settings")

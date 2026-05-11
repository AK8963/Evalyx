"""
Data Masking / PII Protection — Phase 3 Enterprise implementation.

Manages per-project masking rules. Rules are applied at trace ingestion
time (and optionally at retrieval time) to redact, hash, or partially
mask sensitive values before storage.

Built-in detectors (match_type=builtin):
  email        — RFC-like email addresses
  phone        — US/international phone numbers
  credit_card  — 13–16 digit card numbers
  ssn          — US Social Security Numbers
  ip_address   — IPv4 and IPv6 addresses
  api_key      — Common API key patterns (sk-..., pk-..., AKIA...)

Endpoints:
  GET/POST        /api/masking/rules            — list / create rules
  GET/PATCH/DELETE /api/masking/rules/{id}      — manage a rule
  POST            /api/masking/preview          — preview masking on sample data
  GET             /api/masking/builtin-types    — list available built-in types
"""

import hashlib
import json
import logging
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import MaskingRule, User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Built-in PII regex patterns
# ---------------------------------------------------------------------------

BUILTIN_PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "phone": re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "credit_card": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|"
        r"3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|"
        r"(?:2131|1800|35\d{3})\d{11})\b"
    ),
    "ssn": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
    ),
    "ip_address": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b|"
        r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
    ),
    "api_key": re.compile(
        r"\b(?:sk|pk|rk|ek|ak|AKIA)[_\-][A-Za-z0-9]{16,64}\b|"
        r"\bghp_[A-Za-z0-9]{36}\b|"
        r"\bxoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+\b"
    ),
}

BUILTIN_DESCRIPTIONS = {
    "email": "Email addresses (e.g. user@example.com)",
    "phone": "Phone numbers (US / international)",
    "credit_card": "Credit card numbers (Visa, MC, Amex, etc.)",
    "ssn": "US Social Security Numbers (XXX-XX-XXXX)",
    "ip_address": "IPv4 and IPv6 addresses",
    "api_key": "API keys (OpenAI sk-..., GitHub ghp_..., Slack xoxb-...)",
}


# ---------------------------------------------------------------------------
# Masking engine
# ---------------------------------------------------------------------------

def _mask_value(value: str, action: str, token: str) -> str:
    if action == "hash":
        return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:16]
    if action == "partial":
        s = str(value)
        if len(s) <= 4:
            return token
        return s[:2] + "*" * (len(s) - 4) + s[-2:]
    return token  # default: redact


def _apply_builtin(text: str, builtin_type: str, action: str, token: str) -> str:
    pattern = BUILTIN_PATTERNS.get(builtin_type)
    if not pattern:
        return text

    def replace_match(m):
        matched = m.group(0)
        return _mask_value(matched, action, token)

    return pattern.sub(replace_match, text)


def _apply_regex(text: str, pattern_str: str, action: str, token: str) -> str:
    try:
        pattern = re.compile(pattern_str)
        def replace_match(m):
            return _mask_value(m.group(0), action, token)
        return pattern.sub(replace_match, text)
    except re.error:
        return text


def _mask_dict(obj: Any, rules: List[MaskingRule]) -> Any:
    """
    Recursively apply masking rules to a nested dict/list/str.
    Field-name rules apply when the key matches; regex/builtin rules
    apply to all string values.
    """
    if isinstance(obj, dict):
        result = {}
        for key, val in obj.items():
            # Field-name rules: check if key matches any field_name rule
            field_rules = [r for r in rules if r.match_type == "field_name" and r.match_value == key]
            if field_rules:
                rule = field_rules[0]
                result[key] = _mask_value(str(val), rule.mask_action, rule.mask_token)
            else:
                result[key] = _mask_dict(val, rules)
        return result

    if isinstance(obj, list):
        return [_mask_dict(item, rules) for item in obj]

    if isinstance(obj, str):
        text = obj
        for rule in rules:
            if rule.match_type == "builtin" and rule.builtin_type:
                text = _apply_builtin(text, rule.builtin_type, rule.mask_action, rule.mask_token)
            elif rule.match_type == "regex" and rule.match_value:
                text = _apply_regex(text, rule.match_value, rule.mask_action, rule.mask_token)
        return text

    return obj


def apply_masking_rules(data: Any, rules: List[MaskingRule]) -> Any:
    """Public entrypoint: apply a list of masking rules to any JSON-serialisable value."""
    if not rules:
        return data
    active_rules = [r for r in rules if r.is_active]
    if not active_rules:
        return data
    return _mask_dict(data, active_rules)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MaskingRuleCreate(BaseModel):
    project_id: str
    name: str
    match_type: str = "builtin"   # "field_name" | "regex" | "builtin"
    match_value: Optional[str] = None
    builtin_type: Optional[str] = None
    mask_action: str = "redact"   # "redact" | "hash" | "partial"
    mask_token: str = "[REDACTED]"
    apply_to: List[str] = ["input_data", "output_data"]


class MaskingRuleUpdate(BaseModel):
    name: Optional[str] = None
    match_type: Optional[str] = None
    match_value: Optional[str] = None
    builtin_type: Optional[str] = None
    mask_action: Optional[str] = None
    mask_token: Optional[str] = None
    apply_to: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PreviewRequest(BaseModel):
    project_id: str
    sample_data: Any    # The JSON payload to preview masking on


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/builtin-types")
def list_builtin_types(current_user: User = Depends(get_current_user)):
    """List all available built-in PII detector types."""
    return {
        "builtin_types": [
            {"type": k, "description": v}
            for k, v in BUILTIN_DESCRIPTIONS.items()
        ]
    }


@router.get("/rules")
def list_rules(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all masking rules for a project."""
    rules = db.query(MaskingRule).filter_by(project_id=project_id).all()
    return [_rule_dict(r) for r in rules]


@router.post("/rules", status_code=201)
def create_rule(
    payload: MaskingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new masking rule."""
    if payload.match_type == "builtin" and payload.builtin_type not in BUILTIN_PATTERNS:
        raise HTTPException(400, f"Unknown builtin type '{payload.builtin_type}'. "
                            f"Available: {list(BUILTIN_PATTERNS)}")
    if payload.match_type == "regex" and payload.match_value:
        try:
            re.compile(payload.match_value)
        except re.error as e:
            raise HTTPException(400, f"Invalid regex: {e}")

    rule = MaskingRule(
        project_id=payload.project_id,
        created_by=current_user.id,
        name=payload.name,
        match_type=payload.match_type,
        match_value=payload.match_value,
        builtin_type=payload.builtin_type,
        mask_action=payload.mask_action,
        mask_token=payload.mask_token,
        apply_to=payload.apply_to,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.get("/rules/{rule_id}")
def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(MaskingRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Masking rule not found")
    return _rule_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    payload: MaskingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(MaskingRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Masking rule not found")
    for k, v in payload.dict(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return _rule_dict(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.query(MaskingRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(404, "Masking rule not found")
    db.delete(rule)
    db.commit()


@router.post("/preview")
def preview_masking(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview what masking rules would produce on sample data (without saving)."""
    rules = db.query(MaskingRule).filter_by(
        project_id=payload.project_id, is_active=True
    ).all()
    original = payload.sample_data
    masked = apply_masking_rules(deepcopy(original), rules)
    return {
        "original": original,
        "masked": masked,
        "rules_applied": len(rules),
        "changed": original != masked,
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _rule_dict(r: MaskingRule) -> dict:
    return {
        "id": r.id,
        "project_id": r.project_id,
        "name": r.name,
        "match_type": r.match_type,
        "match_value": r.match_value,
        "builtin_type": r.builtin_type,
        "mask_action": r.mask_action,
        "mask_token": r.mask_token,
        "apply_to": r.apply_to,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

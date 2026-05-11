"""
Organizations, Teams, and RBAC routes.
"""



import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import (
    Organization, OrganizationMember, Team, TeamMember, User, ProjectMember
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OrgCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class TeamCreate(BaseModel):
    organization_id: str
    name: str
    description: Optional[str] = None


class MemberInvite(BaseModel):
    email: str
    role: str = "viewer"


class ProjectMemberAdd(BaseModel):
    user_id: str
    role: str = "viewer"


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

@router.post("/organizations", status_code=201)
def create_organization(
    payload: OrgCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slug = payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")
    org = Organization(name=payload.name, slug=slug, owner_id=current_user.id)
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=current_user.id, role="owner"))
    db.commit()
    db.refresh(org)
    return _org_dict(org)


@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = db.query(OrganizationMember).filter_by(user_id=current_user.id).all()
    org_ids = [m.organization_id for m in memberships]
    orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()
    return [_org_dict(o) for o in orgs]


@router.get("/organizations/{org_id}")
def get_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _get_org_or_404(db, org_id)
    _require_membership(db, org_id, current_user.id)
    return _org_dict(org)


@router.get("/organizations/{org_id}/members")
def list_org_members(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_membership(db, org_id, current_user.id)
    members = db.query(OrganizationMember).filter_by(organization_id=org_id).all()
    return [
        {"user_id": m.user_id, "role": m.role, "joined_at": str(m.joined_at or "")}
        for m in members
    ]


@router.post("/organizations/{org_id}/members")
def invite_member(
    org_id: str,
    payload: MemberInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(db, org_id, current_user.id, {"owner", "admin"})
    user = db.query(User).filter_by(email=payload.email).first()
    if not user:
        raise HTTPException(404, "User not found")
    existing = db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user.id).first()
    if existing:
        existing.role = payload.role
    else:
        db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=payload.role, invited_by=current_user.id))
    db.commit()
    return {"message": f"{user.email} added with role {payload.role}"}


@router.delete("/organizations/{org_id}/members/{user_id}")
def remove_member(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(db, org_id, current_user.id, {"owner", "admin"})
    m = db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
    if not m:
        raise HTTPException(404, "Member not found")
    db.delete(m)
    db.commit()
    return {"removed": True}


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@router.post("/teams", status_code=201)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_membership(db, payload.organization_id, current_user.id)
    team = Team(
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=current_user.id, role="owner"))
    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "organization_id": team.organization_id}


@router.get("/organizations/{org_id}/teams")
def list_teams(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_membership(db, org_id, current_user.id)
    teams = db.query(Team).filter_by(organization_id=org_id).all()
    return [{"id": t.id, "name": t.name, "description": t.description} for t in teams]


# ---------------------------------------------------------------------------
# Project membership (direct access)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/members")
def add_project_member(
    project_id: str,
    payload: ProjectMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(ProjectMember).filter_by(project_id=project_id, user_id=payload.user_id).first()
    if existing:
        existing.role = payload.role
    else:
        db.add(ProjectMember(project_id=project_id, user_id=payload.user_id, role=payload.role))
    db.commit()
    return {"message": "Member added"}


@router.get("/projects/{project_id}/members")
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    members = db.query(ProjectMember).filter_by(project_id=project_id).all()
    return [{"user_id": m.user_id, "role": m.role} for m in members]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_org_or_404(db: Session, org_id: str) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


def _require_membership(db: Session, org_id: str, user_id: str) -> OrganizationMember:
    m = db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
    if not m:
        raise HTTPException(403, "Not a member of this organization")
    return m


def _require_role(db: Session, org_id: str, user_id: str, allowed: set) -> None:
    m = _require_membership(db, org_id, user_id)
    if m.role not in allowed:
        raise HTTPException(403, f"Role '{m.role}' is not allowed for this action")


def _org_dict(o: Organization) -> Dict:
    return {
        "id": o.id,
        "name": o.name,
        "slug": o.slug,
        "owner_id": o.owner_id,
        "plan": o.plan,
        "is_active": o.is_active,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }

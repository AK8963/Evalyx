"""
Granular ACL (Access Control List) routes — Phase 1 implementation.

Permission levels per resource:
  owner   – full control (create, read, update, delete, manage members)
  admin   – create, read, update, delete (no member management)
  editor  – create, read, update
  viewer  – read only
  reviewer – read + annotate (add scores/comments)

Resources covered:
  - project   (project-level permissions via ProjectMember)
  - org       (org-level permissions via OrganizationMember)
"""

from typing import Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import (
    OrganizationMember, ProjectMember, User, Organization, Project
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Permission matrix — what each role can do
# ---------------------------------------------------------------------------

ROLE_HIERARCHY: Dict[str, int] = {
    "owner": 5,
    "admin": 4,
    "editor": 3,
    "reviewer": 2,
    "viewer": 1,
}

RESOURCE_PERMISSIONS: Dict[str, Dict[str, Set[str]]] = {
    "project": {
        "read":            {"viewer", "reviewer", "editor", "admin", "owner"},
        "create_trace":    {"reviewer", "editor", "admin", "owner"},
        "update":          {"editor", "admin", "owner"},
        "delete":          {"admin", "owner"},
        "manage_members":  {"owner"},
        "manage_settings": {"admin", "owner"},
    },
    "org": {
        "read":            {"viewer", "reviewer", "editor", "admin", "owner"},
        "create_project":  {"editor", "admin", "owner"},
        "manage_members":  {"admin", "owner"},
        "billing":         {"owner"},
    },
}


# ---------------------------------------------------------------------------
# Permission helper functions (used by other routes as imports)
# ---------------------------------------------------------------------------

def get_project_role(db: Session, project_id: str, user_id: str) -> Optional[str]:
    """Return the user's role on a project, or None if no membership."""
    # Check direct project membership
    member = db.query(ProjectMember).filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if member:
        return member.role

    # Check if user is the project owner
    project = db.query(Project).filter_by(id=project_id).first()
    if project and project.owner_id == user_id:
        return "owner"

    return None


def require_project_permission(
    db: Session,
    project_id: str,
    user_id: str,
    permission: str,
) -> None:
    """Raise HTTP 403 if the user lacks the required permission on a project."""
    role = get_project_role(db, project_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Access denied: not a project member")
    allowed_roles = RESOURCE_PERMISSIONS["project"].get(permission, set())
    if role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: role '{role}' cannot '{permission}' on this project"
        )


def get_org_role(db: Session, org_id: str, user_id: str) -> Optional[str]:
    """Return the user's role in an organization, or None."""
    member = db.query(OrganizationMember).filter_by(
        organization_id=org_id, user_id=user_id
    ).first()
    return member.role if member else None


def require_org_permission(
    db: Session,
    org_id: str,
    user_id: str,
    permission: str,
) -> None:
    """Raise HTTP 403 if the user lacks the required permission in an org."""
    role = get_org_role(db, org_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Access denied: not an org member")
    allowed_roles = RESOURCE_PERMISSIONS["org"].get(permission, set())
    if role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: role '{role}' cannot '{permission}' in this org"
        )


def has_project_permission(
    db: Session, project_id: str, user_id: str, permission: str
) -> bool:
    """Boolean check — does user have permission on project?"""
    role = get_project_role(db, project_id, user_id)
    if role is None:
        return False
    allowed_roles = RESOURCE_PERMISSIONS["project"].get(permission, set())
    return role in allowed_roles


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProjectMemberCreate(BaseModel):
    user_id: str
    role: str = "viewer"  # viewer | reviewer | editor | admin | owner


class ProjectMemberUpdate(BaseModel):
    role: str


class OrgMemberUpdate(BaseModel):
    role: str


class BatchACLUpdate(BaseModel):
    """Batch-update ACLs in one call (add or update, idempotent)."""
    grants: List[Dict] = []    # [{"user_id": ..., "role": ...}, ...]
    revokes: List[str] = []    # [user_id, ...]


# ---------------------------------------------------------------------------
# Project ACL endpoints
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/members")
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all members of a project."""
    require_project_permission(db, project_id, current_user.id, "read")
    members = db.query(ProjectMember).filter_by(project_id=project_id).all()

    # Also include the project owner
    project = db.query(Project).filter_by(id=project_id).first()
    result = []
    if project:
        owner = db.query(User).filter_by(id=project.owner_id).first()
        if owner:
            result.append({
                "user_id": owner.id,
                "email": owner.email,
                "name": owner.name,
                "role": "owner",
                "is_owner": True,
            })

    for m in members:
        if project and m.user_id == project.owner_id:
            continue  # already added above
        user = db.query(User).filter_by(id=m.user_id).first()
        result.append({
            "user_id": m.user_id,
            "email": user.email if user else None,
            "name": user.name if user else None,
            "role": m.role,
            "is_owner": False,
        })
    return result


@router.post("/projects/{project_id}/members", status_code=201)
def add_project_member(
    project_id: str,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant a user access to a project."""
    require_project_permission(db, project_id, current_user.id, "manage_members")

    if payload.role not in ROLE_HIERARCHY:
        raise HTTPException(400, detail=f"Invalid role '{payload.role}'")

    user = db.query(User).filter_by(id=payload.user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")

    existing = db.query(ProjectMember).filter_by(
        project_id=project_id, user_id=payload.user_id
    ).first()
    if existing:
        existing.role = payload.role
        db.commit()
        return {"message": f"Updated {user.email} to role '{payload.role}'"}

    db.add(ProjectMember(
        project_id=project_id,
        user_id=payload.user_id,
        role=payload.role,
    ))
    db.commit()
    return {"message": f"Added {user.email} as '{payload.role}'"}


@router.patch("/projects/{project_id}/members/{user_id}")
def update_project_member_role(
    project_id: str,
    user_id: str,
    payload: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user's role on a project."""
    require_project_permission(db, project_id, current_user.id, "manage_members")

    if payload.role not in ROLE_HIERARCHY:
        raise HTTPException(400, detail=f"Invalid role '{payload.role}'")

    member = db.query(ProjectMember).filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if not member:
        raise HTTPException(404, detail="Member not found")

    member.role = payload.role
    db.commit()
    return {"message": "Role updated"}


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_project_member(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a user's access from a project."""
    require_project_permission(db, project_id, current_user.id, "manage_members")

    member = db.query(ProjectMember).filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if not member:
        raise HTTPException(404, detail="Member not found")

    db.delete(member)
    db.commit()


@router.post("/projects/{project_id}/members/batch")
def batch_update_project_acls(
    project_id: str,
    payload: BatchACLUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch grant/revoke project access. Idempotent."""
    require_project_permission(db, project_id, current_user.id, "manage_members")

    added, updated, revoked, skipped = [], [], [], []

    for grant in payload.grants:
        uid = grant.get("user_id")
        role = grant.get("role", "viewer")
        if role not in ROLE_HIERARCHY:
            skipped.append({"user_id": uid, "reason": f"invalid role '{role}'"})
            continue
        existing = db.query(ProjectMember).filter_by(project_id=project_id, user_id=uid).first()
        if existing:
            existing.role = role
            updated.append(uid)
        else:
            db.add(ProjectMember(project_id=project_id, user_id=uid, role=role))
            added.append(uid)

    for uid in payload.revokes:
        member = db.query(ProjectMember).filter_by(project_id=project_id, user_id=uid).first()
        if member:
            db.delete(member)
            revoked.append(uid)

    db.commit()
    return {"added": added, "updated": updated, "revoked": revoked, "skipped": skipped}


@router.get("/projects/{project_id}/my-role")
def get_my_project_role(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's role on a project."""
    role = get_project_role(db, project_id, current_user.id)
    permissions = {
        perm: (role in roles)
        for perm, roles in RESOURCE_PERMISSIONS["project"].items()
    } if role else {}
    return {
        "role": role,
        "permissions": permissions,
        "has_access": role is not None,
    }


# ---------------------------------------------------------------------------
# Org ACL endpoints
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/members")
def list_org_members(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all members in an organization."""
    require_org_permission(db, org_id, current_user.id, "read")
    members = db.query(OrganizationMember).filter_by(organization_id=org_id).all()
    result = []
    for m in members:
        user = db.query(User).filter_by(id=m.user_id).first()
        result.append({
            "user_id": m.user_id,
            "email": user.email if user else None,
            "name": user.name if user else None,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        })
    return result


@router.patch("/organizations/{org_id}/members/{user_id}")
def update_org_member_role(
    org_id: str,
    user_id: str,
    payload: OrgMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a member's role in an organization."""
    require_org_permission(db, org_id, current_user.id, "manage_members")

    member = db.query(OrganizationMember).filter_by(
        organization_id=org_id, user_id=user_id
    ).first()
    if not member:
        raise HTTPException(404, detail="Member not found")

    member.role = payload.role
    db.commit()
    return {"message": "Role updated"}


@router.delete("/organizations/{org_id}/members/{user_id}", status_code=204)
def remove_org_member(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a user from an organization."""
    require_org_permission(db, org_id, current_user.id, "manage_members")
    member = db.query(OrganizationMember).filter_by(
        organization_id=org_id, user_id=user_id
    ).first()
    if not member:
        raise HTTPException(404, detail="Member not found")
    db.delete(member)
    db.commit()


# ---------------------------------------------------------------------------
# Permission check helper endpoint (useful for UIs)
# ---------------------------------------------------------------------------

@router.get("/check")
def check_permission(
    resource_type: str,  # "project" | "org"
    resource_id: str,
    permission: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if the current user has a specific permission on a resource."""
    if resource_type == "project":
        role = get_project_role(db, resource_id, current_user.id)
        allowed_roles = RESOURCE_PERMISSIONS["project"].get(permission, set())
    elif resource_type == "org":
        role = get_org_role(db, resource_id, current_user.id)
        allowed_roles = RESOURCE_PERMISSIONS["org"].get(permission, set())
    else:
        raise HTTPException(400, detail="resource_type must be 'project' or 'org'")

    allowed = bool(role and role in allowed_roles)
    return {
        "allowed": allowed,
        "role": role,
        "permission": permission,
        "resource_type": resource_type,
        "resource_id": resource_id,
    }

"""
Project routes - manage projects for organizing traces and evals.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from database.models import Project, Environment, User
from backend.database import get_db
from backend.routes.auth import get_current_user
import uuid

router = APIRouter()


class ProjectCreate(BaseModel):
    """Create project request."""
    name: str
    description: str = None


class ProjectResponse(BaseModel):
    """Project response."""
    id: str
    name: str
    description: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    project: ProjectCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project."""
    from backend.routes.audit import log_action

    existing_project = db.query(Project).filter(
        Project.owner_id == current_user.id,
        Project.name == project.name
    ).first()

    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project with this name already exists"
        )

    new_project = Project(
        id=str(uuid.uuid4()),
        owner_id=current_user.id,
        name=project.name,
        description=project.description
    )

    db.add(new_project)
    db.flush()  # get id before seeding environments

    # Auto-seed default environments: dev, staging, production
    for env_name, env_slug, is_prod in [
        ("Development", "dev", False),
        ("Staging", "staging", False),
        ("Production", "production", True),
    ]:
        db.add(Environment(
            project_id=new_project.id,
            created_by=current_user.id,
            name=env_name,
            slug=env_slug,
            is_production=is_prod,
            config={},
        ))

    db.commit()
    db.refresh(new_project)

    log_action(
        db, current_user.id, "project.create",
        resource_type="project", resource_id=new_project.id,
        metadata={"name": new_project.name},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return new_project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for current user."""
    projects = db.query(Project).filter(
        Project.owner_id == current_user.id,
        Project.is_active == True
    ).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get project by ID."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

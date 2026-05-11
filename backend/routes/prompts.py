"""
Prompts routes — versioned prompt registry with deployment tracking.
"""



from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.auth import get_current_user
from database.models import Prompt, PromptDeployment, PromptVersion, User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PromptCreate(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    template: str
    variables: Dict = {}
    default_model: Optional[str] = None
    default_params: Dict = {}


class PromptUpdate(BaseModel):
    template: str
    variables: Optional[Dict] = None
    default_model: Optional[str] = None
    default_params: Optional[Dict] = None
    commit_message: Optional[str] = None


class DeploymentCreate(BaseModel):
    prompt_id: str
    version_number: int
    environment: str = "production"


# ---------------------------------------------------------------------------
# Prompt endpoints
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
def create_prompt(
    payload: PromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = Prompt(
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        template=payload.template,
        variables=payload.variables,
        default_model=payload.default_model,
        default_params=payload.default_params,
        created_by=current_user.id,
        latest_version=1,
    )
    db.add(prompt)
    db.flush()

    # Create version 1
    v1 = PromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        template=payload.template,
        variables=payload.variables,
        model=payload.default_model,
        params=payload.default_params,
        commit_message="Initial version",
        created_by=current_user.id,
    )
    db.add(v1)
    db.commit()
    db.refresh(prompt)
    return _prompt_dict(prompt)


@router.get("/")
def list_prompts(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompts = (
        db.query(Prompt)
        .filter_by(project_id=project_id, is_active=True)
        .order_by(Prompt.updated_at.desc())
        .all()
    )
    return [_prompt_dict(p) for p in prompts]


@router.get("/{prompt_id}")
def get_prompt(
    prompt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = _get_or_404(db, prompt_id)
    return _prompt_dict(p)


@router.put("/{prompt_id}")
def update_prompt(
    prompt_id: str,
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new version of the prompt (immutable versioning)."""
    p = _get_or_404(db, prompt_id)
    new_version_num = (p.latest_version or 0) + 1

    new_version = PromptVersion(
        prompt_id=p.id,
        version_number=new_version_num,
        template=payload.template,
        variables=payload.variables or p.variables,
        model=payload.default_model or p.default_model,
        params=payload.default_params or p.default_params,
        commit_message=payload.commit_message,
        created_by=current_user.id,
    )
    db.add(new_version)
    p.template = payload.template
    if payload.variables is not None:
        p.variables = payload.variables
    if payload.default_model is not None:
        p.default_model = payload.default_model
    if payload.default_params is not None:
        p.default_params = payload.default_params
    p.latest_version = new_version_num
    db.commit()
    return _prompt_dict(p)


@router.delete("/{prompt_id}")
def delete_prompt(
    prompt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = _get_or_404(db, prompt_id)
    p.is_active = False
    db.commit()
    return {"deleted": True}


@router.get("/{prompt_id}/versions")
def list_versions(
    prompt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_or_404(db, prompt_id)
    versions = (
        db.query(PromptVersion)
        .filter_by(prompt_id=prompt_id)
        .order_by(PromptVersion.version_number.desc())
        .all()
    )
    return [_version_dict(v) for v in versions]


@router.get("/{prompt_id}/versions/{version_number}")
def get_version(
    prompt_id: str,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    v = db.query(PromptVersion).filter_by(prompt_id=prompt_id, version_number=version_number).first()
    if not v:
        raise HTTPException(404, "Version not found")
    return _version_dict(v)


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------

@router.post("/deploy", status_code=201)
def deploy_prompt(
    payload: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deploy a specific prompt version to an environment."""
    version = db.query(PromptVersion).filter_by(
        prompt_id=payload.prompt_id,
        version_number=payload.version_number,
    ).first()
    if not version:
        raise HTTPException(404, "Prompt version not found")

    # Deactivate any existing deployment in the same env
    existing = db.query(PromptDeployment).filter_by(
        prompt_id=payload.prompt_id,
        environment=payload.environment,
        status="active",
    ).all()
    for d in existing:
        d.status = "inactive"
        d.retired_at = datetime.utcnow()

    deployment = PromptDeployment(
        prompt_id=payload.prompt_id,
        prompt_version_id=version.id,
        environment=payload.environment,
        status="active",
        deployed_by=current_user.id,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return {"id": deployment.id, "environment": deployment.environment, "status": deployment.status}


@router.get("/{prompt_id}/deployments")
def list_deployments(
    prompt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_or_404(db, prompt_id)
    deployments = db.query(PromptDeployment).filter_by(prompt_id=prompt_id).order_by(
        PromptDeployment.deployed_at.desc()
    ).all()
    return [
        {
            "id": d.id,
            "environment": d.environment,
            "status": d.status,
            "prompt_version_id": d.prompt_version_id,
            "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
        }
        for d in deployments
    ]


# ---------------------------------------------------------------------------
# Render (variable substitution)
# ---------------------------------------------------------------------------

@router.post("/{prompt_id}/render")
def render_prompt(
    prompt_id: str,
    variables: Dict[str, Any],
    version_number: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the prompt template with provided variable values."""
    p = _get_or_404(db, prompt_id)
    template = p.template

    if version_number:
        v = db.query(PromptVersion).filter_by(prompt_id=prompt_id, version_number=version_number).first()
        if v:
            template = v.template

    for key, val in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(val))

    return {"rendered": template, "prompt_id": prompt_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, prompt_id: str) -> Prompt:
    p = db.query(Prompt).filter_by(id=prompt_id).first()
    if not p:
        raise HTTPException(404, "Prompt not found")
    return p


def _prompt_dict(p: Prompt) -> Dict:
    return {
        "id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "description": p.description,
        "template": p.template,
        "variables": p.variables,
        "default_model": p.default_model,
        "default_params": p.default_params,
        "latest_version": p.latest_version,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _version_dict(v: PromptVersion) -> Dict:
    return {
        "id": v.id,
        "prompt_id": v.prompt_id,
        "version_number": v.version_number,
        "template": v.template,
        "model": v.model,
        "params": v.params,
        "commit_message": v.commit_message,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }

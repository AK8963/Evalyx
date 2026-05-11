"""
Settings routes - manage user settings and API keys.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database.models import APIKeySetting, User
from backend.database import get_db
from backend.routes.auth import get_current_user
import uuid

router = APIRouter()


class APIKeySettingCreate(BaseModel):
    """Create API key setting request."""
    service: str  # 'openai', 'anthropic', 'google', 'ollama'
    api_key: str
    model: Optional[str] = None  # For ollama, specify model name


class APIKeySettingResponse(BaseModel):
    """API key setting response (masked key for security)."""
    id: str
    service: str
    model: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Don't return actual API key!
    
    class Config:
        from_attributes = True


class APIKeySettingWithKey(APIKeySettingResponse):
    """API key setting with actual key (only for initial creation)."""
    api_key: str


@router.post("/api-keys", response_model=APIKeySettingWithKey, status_code=201)
async def create_api_key_setting(
    setting: APIKeySettingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save an API key for a service.
    Service must be one of: openai, anthropic, google, ollama
    """
    
    # Validate service
    valid_services = ["openai", "anthropic", "google", "ollama"]
    if setting.service not in valid_services:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service. Must be one of: {', '.join(valid_services)}"
        )

    # Check if already exists
    existing = db.query(APIKeySetting).filter(
        APIKeySetting.user_id == current_user.id,
        APIKeySetting.service == setting.service
    ).first()

    if existing:
        existing.api_key = setting.api_key
        existing.model = setting.model
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return APIKeySettingWithKey.from_orm(existing)

    new_setting = APIKeySetting(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        service=setting.service,
        api_key=setting.api_key,
        model=setting.model,
        is_active=True
    )
    db.add(new_setting)
    db.commit()
    db.refresh(new_setting)
    return APIKeySettingWithKey.from_orm(new_setting)


@router.get("/api-keys", response_model=List[APIKeySettingResponse])
async def list_api_key_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API key settings (without actual keys)."""
    settings_list = db.query(APIKeySetting).filter(
        APIKeySetting.user_id == current_user.id
    ).all()
    return [APIKeySettingResponse.from_orm(s) for s in settings_list]


@router.get("/api-keys/{service}", response_model=APIKeySettingResponse)
async def get_api_key_setting(
    service: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific API key setting (without actual key)."""
    setting = db.query(APIKeySetting).filter(
        APIKeySetting.user_id == current_user.id,
        APIKeySetting.service == service
    ).first()
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for service '{service}' not found"
        )
    
    return APIKeySettingResponse.from_orm(setting)


@router.delete("/api-keys/{service}", status_code=204)
async def delete_api_key_setting(
    service: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an API key setting."""
    setting = db.query(APIKeySetting).filter(
        APIKeySetting.user_id == current_user.id,
        APIKeySetting.service == service
    ).first()
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for service '{service}' not found"
        )
    
    db.delete(setting)
    db.commit()


@router.put("/api-keys/{service}", response_model=APIKeySettingResponse)
async def update_api_key_setting(
    service: str,
    setting: APIKeySettingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing API key setting."""
    existing = db.query(APIKeySetting).filter(
        APIKeySetting.user_id == current_user.id,
        APIKeySetting.service == service
    ).first()
    
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for service '{service}' not found"
        )
    
    existing.api_key = setting.api_key
    existing.model = setting.model
    existing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    
    return APIKeySettingResponse.from_orm(existing)

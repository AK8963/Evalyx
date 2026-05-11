"""
Authentication routes - user login, JWT token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.database import get_db
from backend.config import settings
from database.models import User
import uuid
import secrets
from datetime import datetime, timedelta
import jwt
from typing import Optional

router = APIRouter()


def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token."""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    name: str


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr


class UserResponse(BaseModel):
    """User response."""
    id: str
    email: str
    name: str
    api_key: str
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    message: str


class APIKeyResponse(BaseModel):
    """API key response."""
    api_key: str
    message: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register_user(user: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user and automatically log them in with JWT token.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user (API key will be generated later, not now)
    new_user = User(
        id=str(uuid.uuid4()),
        email=user.email,
        name=user.name,
        api_key=None  # Not needed for dashboard auth, only for SDK
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate and return JWT token (auto-login on register)
    access_token = create_access_token(new_user.id, new_user.email)
    
    return TokenResponse(
        access_token=access_token,
        message="User registered successfully! You are now logged in."
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(login: UserLogin, db: Session = Depends(get_db)):
    """
    Login user with email and return JWT token.
    """
    user = db.query(User).filter(User.email == login.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please register first."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Generate API key on first login if needed (for SDK use)
    if not user.api_key:
        user.api_key = f"traciq_{secrets.token_urlsafe(32)}"
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Generate and return JWT token for dashboard access
    access_token = create_access_token(user.id, user.email)
    
    return TokenResponse(
        access_token=access_token,
        message="Login successful!"
    )


def _decode_jwt(token: str, db: Session) -> User:
    """Validate a raw JWT string and return the User — shared helper."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — accepts JWT Bearer token OR static API key.

    Priority:
      1. X-API-Key header  (for SDK / external apps)
      2. Authorization: Bearer <api_key>  (static key in Bearer slot)
      3. Authorization: Bearer <jwt>      (dashboard / interactive)
    """
    # 1. X-API-Key header
    if x_api_key:
        user = db.query(User).filter(User.api_key == x_api_key, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]

    # 2. Bearer <api_key> — static keys start with "traciq_"
    if token.startswith("traciq_"):
        user = db.query(User).filter(User.api_key == token, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user

    # 3. Bearer <jwt>
    return _decode_jwt(token, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info from JWT."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        api_key=current_user.api_key or "",
    )


@router.post("/verify-api-key", response_model=dict)
async def verify_api_key(api_key: str, db: Session = Depends(get_db)):
    """Verify if API key is valid."""
    user = db.query(User).filter(User.api_key == api_key).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return {
        "valid": True,
        "user_id": user.id,
        "email": user.email
    }


def get_current_user_by_api_key(api_key: str, db: Session = Depends(get_db)) -> User:
    """Dependency to get current user from API key."""
    user = db.query(User).filter(User.api_key == api_key).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return user


@router.get("/api-key")
async def get_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the caller's static API key (generate one on first call)."""
    if not current_user.api_key:
        current_user.api_key = f"traciq_{secrets.token_urlsafe(32)}"
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return {
        "api_key": current_user.api_key,
        "hint": "Use as: Authorization: Bearer <api_key>  OR  X-API-Key: <api_key>",
    }


@router.post("/api-key/regenerate")
async def regenerate_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke and regenerate the caller's static API key."""
    current_user.api_key = f"traciq_{secrets.token_urlsafe(32)}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {
        "api_key": current_user.api_key,
        "message": "API key regenerated. Update all SDK integrations.",
    }

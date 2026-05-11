"""
Loop AI agent routes.
"""



from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.loop_agent import loop_agent
from backend.routes.auth import get_current_user
from database.models import APIKeySetting, User

router = APIRouter()


class LoopQuestion(BaseModel):
    question: str
    project_id: str
    model: str = "gpt-3.5-turbo"


@router.post("/ask")
def ask_loop(
    payload: LoopQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask Loop a natural-language question about project traces."""
    # Retrieve user's stored API keys
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None

    for svc in ("openai", "anthropic"):
        setting = (
            db.query(APIKeySetting)
            .filter_by(user_id=current_user.id, service=svc, is_active=True)
            .first()
        )
        if setting:
            if svc == "openai":
                openai_key = setting.api_key
            else:
                anthropic_key = setting.api_key

    # Fall back to global env keys
    if not openai_key:
        try:
            from backend.config import settings
            openai_key = settings.OPENAI_API_KEY
        except Exception:
            pass
    if not anthropic_key:
        try:
            from backend.config import settings
            anthropic_key = settings.ANTHROPIC_API_KEY
        except Exception:
            pass

    result = loop_agent.ask(
        question=payload.question,
        project_id=payload.project_id,
        db=db,
        openai_key=openai_key,
        anthropic_key=anthropic_key,
        model=payload.model,
    )
    return result

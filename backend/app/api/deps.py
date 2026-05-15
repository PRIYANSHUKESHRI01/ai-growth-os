"""
app/api/deps.py
────────────────
FastAPI shared dependencies.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id


# Re-export for convenience in routes
__all__ = ["get_db", "get_current_user_id"]

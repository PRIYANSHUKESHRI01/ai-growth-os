"""
app/models/user.py
───────────────────
User model — the multi-tenant anchor.
Every piece of data (leads, campaigns, messages) is scoped to a user_id.
"""
import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Clerk identity — single source of truth for who this user is
    clerk_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=True, index=True  # nullable for migration safety
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # api_key kept nullable for backward compatibility — no longer used for auth
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="user", cascade="all, delete-orphan")
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} clerk_id={self.clerk_user_id}>"

"""
app/repositories/campaign_repository.py
─────────────────────────────────────────
Campaign CRUD — scoped to user_id.
"""
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class CampaignRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: str, name: str, total_leads: int) -> Campaign:
        campaign = Campaign(
            user_id=user_id,
            name=name,
            total_leads=total_leads,
            status=CampaignStatus.PENDING,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def get_by_id(self, campaign_id: str, user_id: str) -> Optional[Campaign]:
        return (
            self.db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.user_id == user_id)
            .first()
        )

    def get_all(self, user_id: str, page: int = 1, page_size: int = 20) -> tuple[List[Campaign], int]:
        query = self.db.query(Campaign).filter(Campaign.user_id == user_id)
        total = query.count()
        campaigns = (
            query.order_by(Campaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return campaigns, total

    def update_status(
        self,
        campaign_id: str,
        status: CampaignStatus,
        celery_task_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Campaign]:
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return None
        campaign.status = status
        if celery_task_id:
            campaign.celery_task_id = celery_task_id
        if error_message:
            campaign.error_message = error_message
        if status == CampaignStatus.COMPLETED:
            campaign.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def increment_processed(self, campaign_id: str, success: bool = True) -> None:
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return
        if success:
            campaign.processed_leads += 1
        else:
            campaign.failed_leads += 1
        self.db.commit()

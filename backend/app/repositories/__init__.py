# app/repositories/__init__.py
from app.repositories.lead_repository import LeadRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.score_repository import ScoreRepository
from app.repositories.message_repository import MessageRepository

__all__ = ["LeadRepository", "CampaignRepository", "ScoreRepository", "MessageRepository"]

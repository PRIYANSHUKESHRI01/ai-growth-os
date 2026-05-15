"""
app/modules/outreach_engine/services/personalization_service.py
────────────────────────────────────────────────────────────────
Multi-step AI message generation for the outreach sequence.
Reuses the LangChain/OpenAI stack from Automation 1's LLMService
but adds step-specific prompt variants.
"""
from typing import Tuple
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OutreachOutput(BaseModel):
    subject: str = Field(description="Email subject line (max 80 chars)")
    body: str = Field(description="Email body in plain text (150-250 words)")


_parser = PydanticOutputParser(pydantic_object=OutreachOutput)

# ── Step-specific system prompts ──────────────────────────────────────────────

_STEP_SYSTEM = {
    1: (
        "You are an expert B2B sales copywriter. Write a personalized cold outreach email "
        "that feels genuine, concise, and value-focused. Never use generic templates. "
        "This is the FIRST touchpoint — make a strong but low-pressure first impression.\n"
        "{format_instructions}"
    ),
    2: (
        "You are an expert B2B sales copywriter writing a FOLLOW-UP email. "
        "The recipient did not reply to the first email. Keep it very short (3-4 sentences), "
        "add a new angle or value hint, and make it easy to reply.\n"
        "{format_instructions}"
    ),
    3: (
        "You are writing a final 'break-up' follow-up email — this is the LAST outreach attempt. "
        "Keep it ultra-short (2-3 sentences), acknowledge they may not be interested, "
        "leave the door gently open for the future. No pressure.\n"
        "{format_instructions}"
    ),
}

_HUMAN_TEMPLATE = """\
Sender Information (YOU):
- Name: {sender_name}
- Company: {sender_company}
- Contact Info: {sender_contact}

Lead Information:
- Name: {first_name} {last_name}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Company Size: {company_size}

Lead Score: {final_score:.0%} (reply probability: {reply_prob:.0%})

Requirements:
- Reference their specific role and industry
- Mention a concrete, relevant value proposition
- Clear, low-friction call-to-action
- Subject line under 80 characters
- Use the provided Sender Information for the email signature.
"""


def _build_chain(step: int):
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.7,
        api_key=settings.OPENAI_API_KEY,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", _STEP_SYSTEM.get(step, _STEP_SYSTEM[1])),
        ("human", _HUMAN_TEMPLATE),
    ])
    return prompt | llm | _parser


class PersonalizationService:
    """
    Generates personalized outreach emails for each sequence step.
    Step 1: Initial cold pitch
    Step 2: Follow-up nudge
    Step 3: Final breakup email
    """

    def generate(self, lead, score, step_number: int = 1) -> Tuple[str, str]:
        """
        Returns (subject, body) for the given lead, score, and step.
        Falls back to a simple template if OpenAI fails.
        """
        chain = _build_chain(step_number)
        try:
            result: OutreachOutput = chain.invoke({
                "sender_name": "Priyanshu",
                "sender_company": "Ai Growth OS",
                "sender_contact": "priyanshu@aigrowthos.com",
                "first_name": getattr(lead, "first_name", "") or "",
                "last_name": getattr(lead, "last_name", "") or "",
                "title": getattr(lead, "title", "Professional") or "Professional",
                "company": getattr(lead, "company", "your company") or "your company",
                "industry": getattr(lead, "industry", "your industry") or "your industry",
                "company_size": getattr(lead, "company_size", "a growing company") or "a growing company",
                "reply_prob": getattr(score, "reply_probability", 0.5) if score else 0.5,
                "final_score": getattr(score, "final_score", 0.5) if score else 0.5,
                "format_instructions": _parser.get_format_instructions(),
            })
            logger.info(
                "[Outreach] message generated lead_id=%s step=%d subject=%r",
                lead.id, step_number, result.subject[:50],
            )
            return result.subject, result.body

        except Exception as exc:
            logger.error(
                "[Outreach] LLM generation failed lead_id=%s step=%d: %s",
                lead.id, step_number, exc,
            )
            return self._fallback(lead, step_number)

    @staticmethod
    def _fallback(lead, step: int) -> Tuple[str, str]:
        name = getattr(lead, "first_name", "there") or "there"
        company = getattr(lead, "company", "your company") or "your company"

        if step == 1:
            subject = f"Quick thought for {name} at {company}"
            body = (
                f"Hi {name},\n\nI came across {company} and wanted to share how we've helped "
                f"similar teams accelerate their pipeline.\n\nWould you be open to a quick 15-min call?\n\nBest,\nAI Growth OS"
            )
        elif step == 2:
            subject = f"Following up — {company}"
            body = (
                f"Hi {name},\n\nJust circling back on my previous note. Happy to keep it brief — "
                f"would a quick call this week work?\n\nBest,\nAI Growth OS"
            )
        else:
            subject = f"Last note — {company}"
            body = (
                f"Hi {name},\n\nI won't keep reaching out if the timing isn't right. "
                f"Feel free to reach me whenever it makes sense.\n\nBest,\nAI Growth OS"
            )
        return subject, body

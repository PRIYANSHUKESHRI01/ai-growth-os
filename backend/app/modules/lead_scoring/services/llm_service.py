"""
app/services/llm_service.py
────────────────────────────
LLM-powered outreach generation using LangChain + OpenAI.

Uses a structured PromptTemplate to produce subject + body
tailored to the lead's role, industry, and score tier.
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
    body: str = Field(description="Email body in plain text (200-300 words)")


_parser = PydanticOutputParser(pydantic_object=OutreachOutput)

_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert B2B sales copywriter. Generate highly personalized outreach emails "
        "that feel genuine, concise, and value-focused. Never use generic templates.\n"
        "{format_instructions}",
    ),
    (
        "human",
        """Generate a personalized cold outreach email for the following lead:

Lead Information:
- Name: {first_name} {last_name}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Company Size: {company_size}

Engagement Scores:
- Reply Probability: {reply_prob:.0%}
- Conversion Probability: {conversion_prob:.0%}
- Overall Score: {final_score:.0%}

Tone guidance:
- Score >= 0.7: confident and direct — they're a hot lead
- Score 0.4–0.7: curious and educational — nurture with value
- Score < 0.4: gentle and low-pressure — soft introduction

Requirements:
- Reference their industry/role specifically
- Mention a concrete value proposition
- End with a clear, easy call-to-action
- Subject line must be compelling, under 80 characters
""",
    ),
])


class LLMService:
    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
        )
        self._chain = _PROMPT | self._llm | _parser

    def generate_outreach(self, lead, score) -> Tuple[str, str]:
        """
        Generate (subject, body) for a lead + its score.
        `lead` is a Lead ORM object; `score` is a LeadScore ORM object.
        """
        try:
            result: OutreachOutput = self._chain.invoke({
                "first_name": getattr(lead, "first_name", "") or "",
                "last_name": getattr(lead, "last_name", "") or "",
                "title": getattr(lead, "title", "Professional") or "Professional",
                "company": getattr(lead, "company", "your company") or "your company",
                "industry": getattr(lead, "industry", "your industry") or "your industry",
                "company_size": getattr(lead, "company_size", "a growing company") or "a growing company",
                "reply_prob": score.reply_probability,
                "conversion_prob": score.conversion_probability,
                "final_score": score.final_score,
                "format_instructions": _parser.get_format_instructions(),
            })
            logger.info(
                "Generated outreach for lead_id=%s subject=%r",
                lead.id, result.subject[:40],
            )
            return result.subject, result.body
        except Exception as e:
            logger.error("LLM generation failed for lead_id=%s: %s", lead.id, e)
            # Fallback template
            subject = f"Quick question for {getattr(lead, 'first_name', 'you') or 'you'}"
            body = (
                f"Hi {getattr(lead, 'first_name', 'there') or 'there'},\n\n"
                f"I came across {getattr(lead, 'company', 'your company') or 'your company'} "
                f"and wanted to reach out about how we can help teams in the "
                f"{getattr(lead, 'industry', 'industry') or 'industry'} space.\n\n"
                f"Would you be open to a quick 15-minute call this week?\n\n"
                f"Best,\nAI Growth OS"
            )
            return subject, body

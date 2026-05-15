"""
app/ml/features.py
───────────────────
Feature engineering from Lead data.
Converts raw lead fields into a numeric vector for ML models,
and extracts named signals for the multi-signal scoring engine.
"""
from typing import List, Dict
import hashlib


# ── Free email providers (30+) ─────────────────────────────────────────────
FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com",
    "aol.com", "icloud.com", "mail.com", "protonmail.com", "zoho.com",
    "yandex.com", "gmx.com", "gmx.net", "live.com", "msn.com",
    "me.com", "inbox.com", "fastmail.com", "tutanota.com", "mailinator.com",
    "guerrillamail.com", "tempmail.com", "rediffmail.com", "qq.com",
    "163.com", "126.com", "sina.com", "yeah.net", "foxmail.com",
    "web.de", "t-online.de", "laposte.net", "free.fr",
})

# ── Decision-maker keywords (50+ patterns) ────────────────────────────────
# Organised by seniority tier for potential future weighting
DECISION_MAKER_KEYWORDS = frozenset({
    # C-suite
    "chief", "ceo", "cto", "cfo", "coo", "cmo", "cio", "cro", "cso", "cpo",
    "chief executive", "chief technology", "chief financial", "chief operating",
    "chief marketing", "chief information", "chief revenue", "chief strategy",
    "chief product",
    # Board / ownership
    "chairman", "chairwoman", "chairperson", "board member", "board director",
    "founder", "co-founder", "cofounder", "owner", "partner",
    "managing partner", "general partner", "principal",
    # President / GM
    "president", "general manager", "gm",
    # VP tier
    "vp", "vice president", "svp", "evp", "avp",
    "senior vice president", "executive vice president",
    # Director tier
    "director", "managing director", "executive director", "group director",
    "regional director", "country director",
    # Head tier
    "head of", "head", "global head", "department head",
})

# ── Encoding mappings ──────────────────────────────────────────────────────

INDUSTRY_MAP = {
    "technology": 0, "tech": 0, "software": 0, "saas": 0,
    "finance": 1, "financial": 1, "banking": 1,
    "healthcare": 2, "health": 2, "medical": 2,
    "retail": 3, "ecommerce": 3, "e-commerce": 3,
    "manufacturing": 4,
    "education": 5,
    "marketing": 6, "advertising": 6,
    "consulting": 7,
    "real estate": 8,
    "other": 9,
}

COMPANY_SIZE_MAP = {
    "1-10": 0,
    "11-50": 1,
    "51-200": 2,
    "201-500": 3,
    "501-1000": 4,
    "1001-5000": 5,
    "5001-10000": 6,
    "10001+": 7,
}

TITLE_SCORE_MAP = {
    "ceo": 1.0, "cto": 0.95, "coo": 0.9, "cfo": 0.85, "cmo": 0.85,
    "cio": 0.82, "cro": 0.82, "cpo": 0.82,
    "founder": 0.95, "co-founder": 0.95, "cofounder": 0.95,
    "owner": 0.90, "partner": 0.85, "managing partner": 0.90,
    "president": 0.88, "chairman": 0.90,
    "general manager": 0.75, "gm": 0.75,
    "vp": 0.80, "vice president": 0.80, "svp": 0.85, "evp": 0.85,
    "director": 0.70, "managing director": 0.80, "head": 0.65, "head of": 0.65,
    "manager": 0.50, "lead": 0.45,
    "senior": 0.40, "principal": 0.55,
    "engineer": 0.30, "developer": 0.28,
    "analyst": 0.25, "associate": 0.20,
    "intern": 0.10, "assistant": 0.15,
}


# ── Encoding functions ─────────────────────────────────────────────────────

def encode_industry(industry: str | None) -> int:
    if not industry:
        return 9  # "other"
    return INDUSTRY_MAP.get(industry.lower().strip(), 9)


def encode_company_size(size: str | None) -> int:
    if not size:
        return 1  # assume small
    return COMPANY_SIZE_MAP.get(size.strip(), 1)


def encode_title(title: str | None) -> float:
    if not title:
        return 0.3
    title_lower = title.lower()
    for key, score in TITLE_SCORE_MAP.items():
        if key in title_lower:
            return score
    return 0.3


def detect_business_email(email: str | None) -> float:
    """Returns 1.0 for business email, 0.0 for free/personal/missing."""
    if not email or "@" not in email:
        return 0.0
    domain = email.split("@")[-1].strip().lower()
    return 0.0 if domain in FREE_EMAIL_DOMAINS else 1.0


def detect_decision_maker(title: str | None) -> float:
    """Returns 1.0 if the title matches decision-maker patterns, 0.0 otherwise."""
    if not title:
        return 0.0
    title_lower = title.lower().strip()
    for keyword in DECISION_MAKER_KEYWORDS:
        if keyword in title_lower:
            return 1.0
    return 0.0


def compute_name_quality(first_name: str | None, last_name: str | None) -> float:
    """
    Score name quality 0.0–1.0 based on:
    - Both names present (0.4)
    - Each name length > 1 char (0.15 each)
    - Not a placeholder like 'test', 'unknown', 'n/a' (0.15 each)
    """
    score = 0.0
    placeholders = {"test", "unknown", "n/a", "na", "none", "null", ".", "-", "xxx", "tbd"}

    fn = (first_name or "").strip()
    ln = (last_name or "").strip()

    has_first = len(fn) > 0
    has_last = len(ln) > 0

    if has_first and has_last:
        score += 0.40
    elif has_first or has_last:
        score += 0.15

    if has_first and len(fn) > 1:
        score += 0.15
    if has_last and len(ln) > 1:
        score += 0.15

    if has_first and fn.lower() not in placeholders:
        score += 0.15
    if has_last and ln.lower() not in placeholders:
        score += 0.15

    return min(round(score, 4), 1.0)


def compute_engagement_score(email: str | None, first_name: str | None, last_name: str | None) -> float:
    """
    Simulated engagement score — deterministic via hash of lead identity.
    Produces a value in [0.1, 0.9] that is reproducible across calls.
    In production, replace with real engagement data (open rates, clicks, etc.).
    """
    seed_str = f"{(email or '').lower()}|{(first_name or '').lower()}|{(last_name or '').lower()}"
    digest = hashlib.md5(seed_str.encode()).hexdigest()
    # Use first 8 hex chars → integer → normalize to [0.1, 0.9]
    hash_int = int(digest[:8], 16)
    normalized = 0.1 + (hash_int / 0xFFFFFFFF) * 0.8
    return round(normalized, 4)


def compute_email_domain_score(email: str | None) -> float:
    """
    Score email domain quality:
    - .edu / .gov → 0.9
    - .org → 0.7
    - .com / .io / .co → 0.6
    - free mail → 0.2
    - unknown → 0.3
    """
    if not email or "@" not in email:
        return 0.3
    domain = email.split("@")[-1].strip().lower()
    if domain in FREE_EMAIL_DOMAINS:
        return 0.2
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    if tld in ("edu", "gov", "mil"):
        return 0.9
    if tld == "org":
        return 0.7
    if tld in ("com", "io", "co", "ai", "dev", "tech"):
        return 0.6
    return 0.5


# ── Main extraction functions ──────────────────────────────────────────────

def _lead_to_dict(lead) -> dict:
    """Normalize Lead ORM object or dict to a plain dict."""
    if isinstance(lead, dict):
        return lead
    return {
        "email": getattr(lead, "email", None),
        "first_name": getattr(lead, "first_name", None),
        "last_name": getattr(lead, "last_name", None),
        "company": getattr(lead, "company", None),
        "title": getattr(lead, "title", None),
        "industry": getattr(lead, "industry", None),
        "company_size": getattr(lead, "company_size", None),
        "source": getattr(lead, "source", None),
        "linkedin_url": getattr(lead, "linkedin_url", None),
    }


def extract_signals(lead) -> Dict[str, float]:
    """
    Extract named signal dict from a Lead for signal scoring + explanation.
    All values are normalized to [0, 1].
    """
    data = _lead_to_dict(lead)
    return {
        "is_business_email": detect_business_email(data.get("email")),
        "is_decision_maker": detect_decision_maker(data.get("title")),
        "title_score": encode_title(data.get("title")),
        "name_quality": compute_name_quality(data.get("first_name"), data.get("last_name")),
        "has_company": 1.0 if data.get("company") else 0.0,
        "has_linkedin": 1.0 if data.get("linkedin_url") else 0.0,
        "is_referral": 1.0 if data.get("source") == "referral" else 0.0,
        "engagement_score": compute_engagement_score(
            data.get("email"), data.get("first_name"), data.get("last_name")
        ),
        "email_domain_score": compute_email_domain_score(data.get("email")),
    }


def extract_features(lead) -> List[float]:
    """
    Extract a fixed-length feature vector from a Lead ORM object or dict.
    Returns a list of 12 floats for ML model consumption.
    """
    data = _lead_to_dict(lead)
    signals = extract_signals(lead)

    features = [
        # Original 6 features
        float(encode_industry(data.get("industry"))),
        float(encode_company_size(data.get("company_size"))),
        signals["title_score"],
        signals["has_linkedin"],
        signals["has_company"],
        signals["is_referral"],
        # New 6 features
        signals["is_business_email"],
        signals["is_decision_maker"],
        signals["name_quality"],
        signals["engagement_score"],
        signals["email_domain_score"],
        float(encode_company_size(data.get("company_size"))) / 7.0,  # normalized company size
    ]
    return features

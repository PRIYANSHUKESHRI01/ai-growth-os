"""
app/modules/outreach_engine/services/deliverability_service.py
───────────────────────────────────────────────────────────────
Email deliverability checks:
  - Basic format validation
  - Disposable domain detection
  - Domain structure for SPF/DKIM future integration
"""
import re
from typing import Tuple

# Known disposable/temporary email providers
_DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwam.com",
    "yopmail.com", "trashmail.com", "maildrop.cc", "dispostable.com",
    "fakeinbox.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "guerrillamail.info", "guerrillamail.biz", "guerrillamail.de",
    "guerrillamail.net", "guerrillamail.org", "spam4.me", "getairmail.com",
    "filzmail.com", "throwam.com", "0-mail.com", "0815.ru", "10mail.org",
    "20mail.it", "20minutemail.com", "21cn.com", "binkmail.com",
    "crap.2flani.com", "despam.it", "discard.email", "discardmail.com",
    "EmailTemp.com", "garliclife.com", "get2mail.fr", "Getonemail.com",
    "haltospam.com", "ieh-mail.de", "inoutmail.de", "inoutmail.eu",
    "jetable.fr.nf", "jetable.net", "jetable.org", "kasmail.com",
    "koszmail.pl", "kurzepost.de", "lavabit.com", "lol.ovpn.to",
    "mailexpire.com", "mailin8r.com", "mailme.lv", "mailnew.com",
    "mailnull.com", "mailscrap.com", "mailsiphon.com", "mailtemp.info",
    "mintemail.com", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    "mt2009.com", "mt2014.com", "nomail2me.com", "nospamfor.us",
    "nowmymail.com", "objectmail.com", "obobbo.com", "onepausetime.com",
    "ordinaryamerican.net", "pookmail.com", "proxymail.eu", "rcpt.at",
    "rklips.com", "rmqkr.net", "royal.net", "s0ny.net", "safe-mail.net",
    "shortmail.net", "sibmail.com", "soodonims.com", "speakasy.net",
    "suremail.info", "teleworm.com", "teleworm.us", "tempe-mail.com",
    "tempr.email", "test.com", "thanksnospam.com", "thisisnotmyrealemail.com",
    "throwam.com", "throwam.com", "tilien.com", "tmailinator.com",
    "turual.com", "twinmail.de", "tyldd.com", "uggsrock.com", "uroid.com",
    "deadaddress.com", "spamgourmet.com", "mailnesia.com", "spamex.com",
    "spamgob.com", "spamhole.com", "spamify.com", "spaml.com",
})

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


class DeliverabilityService:
    """
    Checks email validity before sending.
    All checks are synchronous and CPU-only (no external API calls).
    """

    def check(self, email: str) -> Tuple[bool, str]:
        """
        Returns (is_valid: bool, reason: str).
        reason is empty string when valid.
        """
        if not email or not email.strip():
            return False, "Empty email address"

        email = email.strip().lower()

        # ── Format check ─────────────────────────────────────────────────
        if not _EMAIL_REGEX.match(email):
            return False, f"Invalid email format: {email}"

        # ── Domain check ─────────────────────────────────────────────────
        domain = email.split("@", 1)[1]

        if domain in _DISPOSABLE_DOMAINS:
            return False, f"Disposable email domain blocked: {domain}"

        # ── Basic structural checks ────────────────────────────────────────
        if len(email) > 254:
            return False, "Email exceeds maximum length (254 chars)"

        local = email.split("@", 1)[0]
        if len(local) > 64:
            return False, "Email local part exceeds 64 characters"

        return True, ""

    def get_domain(self, email: str) -> str:
        """Extract sending domain from email."""
        if "@" not in email:
            return ""
        return email.split("@", 1)[1].lower()

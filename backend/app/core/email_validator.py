"""Comprehensive email validation and risk verification.

Enforces:
1. RFC syntax and structure integrity.
2. Rejection of disposable and temporary email domains (e.g. 10minutemail, mailinator, guerrillamail).
3. Rejection of bot-generated, spam-patterned, or scam-impersonating emails.
"""

import re
from typing import Final

from app.core.errors import ValidationAppError

# Standard RFC syntax check
_EMAIL_REGEX: Final = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

# Known disposable & temporary email services
DISPOSABLE_DOMAINS: Final[set[str]] = {
    # Mailinator family
    "mailinator.com",
    "mailinator.net",
    "mailinator2.com",
    "mailin8r.com",
    "suremail.info",
    "notmailinator.com",
    "reconmail.com",
    "safetymail.info",
    # 10 Minute Mail family
    "10minutemail.com",
    "10minutemail.net",
    "10minutemail.org",
    "10minutemail.co.uk",
    "10minmail.com",
    "10minutemailbox.com",
    "minuteinbox.com",
    # Guerrilla Mail family
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamail.biz",
    "guerrillamail.de",
    "guerrillamailblock.com",
    "grr.la",
    "sharklasers.com",
    "spam4.me",
    "pokemail.net",
    # TempMail / Temp-Mail family
    "tempmail.com",
    "temp-mail.org",
    "tempmail.net",
    "tempmail.io",
    "temp-mail.io",
    "tempmailo.com",
    "tempail.com",
    "mytempmail.com",
    "mytemp.email",
    # YOPmail family
    "yopmail.com",
    "yopmail.fr",
    "yopmail.net",
    "cool.fr.nf",
    "courriel.fr.nf",
    "jetable.fr.nf",
    "nospam.ze.tc",
    "nomail.xl.cx",
    "mega.zik.dj",
    "speed.1s.fr",
    # TrashMail family
    "trashmail.com",
    "trashmail.net",
    "trashmail.org",
    "trashmail.me",
    "trashmail.io",
    "trash-mail.com",
    # ThrowAway family
    "throwawaymail.com",
    "throwawayemailaddress.com",
    "throwawayemail.com",
    # DropMail / AirMail family
    "dropmail.me",
    "getairmail.com",
    "airmail.cc",
    "inboxbear.com",
    "dispostable.com",
    "fakeinbox.com",
    "burnermail.io",
    "nada.ltd",
    "moakt.com",
    "mohmal.com",
    "crazymailing.com",
    "mintemail.com",
    "emailondeck.com",
    "generator.email",
    "fakemailgenerator.com",
    "fakemail.net",
    "fakemail.io",
    "temporary-mail.net",
    "disposablemail.com",
    "tempinbox.com",
    "maildrop.cc",
    "harakirimail.com",
    "trbvm.com",
    "inboxkitten.com",
    "discard.email",
    "spambog.com",
    "spambox.us",
    "smailpro.com",
    "luxusmail.org",
    "generator.email",
    # Fake name generator domains
    "armyspy.com",
    "cuvox.de",
    "dayrep.com",
    "einrot.com",
    "fleckens.hu",
    "gustr.com",
    "jourrapide.com",
    "rhyta.com",
    "superrito.com",
    "teleworm.us",
    "vomoto.com",
}

# Substring stems inside domain name that identify disposable services
DISPOSABLE_STEM_KEYWORDS: Final[tuple[str, ...]] = (
    "tempmail",
    "temp-mail",
    "disposab",
    "throwaway",
    "fakeinbox",
    "10minut",
    "trashmail",
    "fakemail",
    "burnermail",
    "dropmail",
    "guerrillamail",
    "fake-mail",
    "fakeemail",
    "spam4me",
    "sharklasers",
    "yopmail",
    "mailinator",
    "minuteinbox",
)

# Reserved or invalid TLDs
BLOCKED_TLDS: Final[set[str]] = {
    "test",
    "example",
    "invalid",
    "localhost",
}

# Bot patterns in local part
_BOT_PREFIXES: Final[tuple[str, ...]] = (
    "bot_",
    "bot-",
    "testbot",
    "spambot",
    "crawler_",
    "scraper_",
    "fakeuser_",
)

# High-entropy hex or numeric sequence typical of spam generator scripts
_BOT_HEX_OR_DIGIT_PATTERN: Final = re.compile(r"^[a-zA-Z0-9_-]*[0-9a-fA-F]{14,}[a-zA-Z0-9_-]*$")

# Suspicious scam / financial phishing impersonation keywords when on generic free webmail
_SCAM_IMPERSONATION_KEYWORDS: Final[tuple[str, ...]] = (
    "paypal_billing",
    "paypal_security",
    "paypal_support",
    "bank_security",
    "account_verification",
    "security_alert",
    "crypto_support",
    "binance_support",
    "coinbase_support",
    "irs_refund",
    "tax_refund",
)

_COMMON_FREE_WEBMAIL: Final[set[str]] = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


def is_disposable_domain(domain: str) -> bool:
    """Check if the domain or its parent domain belongs to known disposable email services."""
    norm_domain = domain.lower().strip()
    if norm_domain in DISPOSABLE_DOMAINS:
        return True

    # Check for subdomains like test.mailinator.com
    parts = norm_domain.split(".")
    if len(parts) > 2:
        parent_domain = ".".join(parts[-2:])
        if parent_domain in DISPOSABLE_DOMAINS:
            return True

    # Check for disposable stem patterns (e.g. tempmail-online.net)
    domain_stem = parts[0] if parts else norm_domain
    for stem in DISPOSABLE_STEM_KEYWORDS:
        if stem in domain_stem:
            return True

    return False


def validate_email_safety(email: str) -> tuple[bool, str | None]:
    """Validate email syntax, check against disposable domains, and detect bot/scam patterns.

    Returns (is_valid, error_reason).
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required."

    cleaned = email.strip()
    if len(cleaned) < 5 or len(cleaned) > 320:
        return False, "Email must be between 5 and 320 characters."

    # Seeded demo exemption
    if cleaned.lower() == "demo@recall.local":
        return True, None

    if "@" not in cleaned:
        return False, "Invalid email address format (missing @)."

    parts = cleaned.split("@")
    if len(parts) != 2:
        return False, "Email address cannot contain multiple @ characters."

    local_part, domain = parts[0], parts[1].lower()

    if not local_part or not domain:
        return False, "Email must contain both username and domain."

    if len(local_part) > 64:
        return False, "Email username part exceeds 64 characters."

    if local_part.startswith(".") or local_part.endswith("."):
        return False, "Email username cannot start or end with a period."

    if ".." in local_part:
        return False, "Email username cannot contain consecutive periods."

    # Reject excessive plus-tagging often used by spammers/bots
    if local_part.count("+") > 1:
        return False, "Email addresses with multiple plus (+) tags are not permitted."

    if not _EMAIL_REGEX.match(cleaned):
        return False, "Please enter a valid email address."

    # Validate domain structure
    if "." not in domain:
        return False, "Domain must contain a valid top-level domain."

    domain_parts = domain.split(".")
    tld = domain_parts[-1]

    if len(tld) < 2 or not tld.isalpha():
        return False, "Email domain top-level extension is invalid."

    if tld in BLOCKED_TLDS:
        return False, f"Domain extension .{tld} is not permitted for registration."

    # 1. Disposable / Temporary Email Check
    if is_disposable_domain(domain):
        return (
            False,
            "Temporary and disposable email services (like 10minutemail, mailinator, etc.) "
            "are not allowed. Please use your personal or work email address.",
        )

    # 2. Bot / automated script heuristics
    local_lower = local_part.lower()
    for prefix in _BOT_PREFIXES:
        if local_lower.startswith(prefix):
            return False, "Automated or bot-patterned email addresses are not permitted."

    # Long random hex/digit sequences generated by bots (e.g. user_872346872364872364)
    if _BOT_HEX_OR_DIGIT_PATTERN.match(local_part) and len(local_part) >= 18:
        return (
            False,
            "This email appears to be an automated or generated account. "
            "Please use a recognizable personal or work email.",
        )

    # 3. Phishing / scam impersonation on free public webmail
    if domain in _COMMON_FREE_WEBMAIL:
        for keyword in _SCAM_IMPERSONATION_KEYWORDS:
            if keyword in local_lower:
                return (
                    False,
                    "This email address matches restricted high-risk impersonation patterns. "
                    "Please provide a legitimate personal email.",
                )

    return True, None


def ensure_valid_email(email: str) -> str:
    """Validate email safety and return the normalized email, or raise ValidationAppError."""
    valid, reason = validate_email_safety(email)
    if not valid:
        raise ValidationAppError(reason or "Invalid email address.")
    return email.strip().lower()


import pytest

from app.core.email_validator import (
    ensure_valid_email,
    is_disposable_domain,
    validate_email_safety,
)
from app.core.errors import ValidationAppError


def test_valid_emails():
    valid = [
        "user@gmail.com",
        "alex.smith@company.org",
        "priya.nair@subdomain.example.co.in",
        "founder@startup.io",
        "dev@recall.ai",
        "demo@recall.local",
    ]
    for email in valid:
        ok, reason = validate_email_safety(email)
        assert ok is True, f"Expected {email} to be valid, got {reason}"
        assert ensure_valid_email(email) == email.lower()


def test_disposable_and_temp_emails():
    disposable = [
        "john@mailinator.com",
        "bob@sub.mailinator.com",
        "speedy@10minutemail.com",
        "anonymous@guerrillamail.com",
        "temp@temp-mail.org",
        "trash@trashmail.com",
        "quick@sharklasers.com",
        "dispo@yopmail.com",
        "fake@fakeinbox.com",
        "burner@burnermail.io",
        "drop@dropmail.me",
        "user@tempmail-online.net",
    ]
    for email in disposable:
        ok, reason = validate_email_safety(email)
        assert ok is False, f"Expected {email} to be rejected"
        assert "temporary" in reason.lower() or "disposable" in reason.lower()
        with pytest.raises(ValidationAppError):
            ensure_valid_email(email)


def test_bot_and_automated_patterns():
    bots = [
        "bot_1892837198273@gmail.com",
        "bot-crawler-99@yahoo.com",
        "testbot_0192830192@hotmail.com",
        "crawler_google_bot@gmail.com",
        "scraper_user@outlook.com",
        "a98b7c6d5e4f3a2b1c@gmail.com",
    ]
    for email in bots:
        ok, reason = validate_email_safety(email)
        assert ok is False, f"Expected bot email {email} to be rejected"
        assert "bot" in reason.lower() or "automated" in reason.lower()


def test_scam_impersonation_patterns():
    scams = [
        "paypal_billing_dept@gmail.com",
        "bank_security_update@yahoo.com",
        "crypto_support_desk@outlook.com",
        "account_verification_team@gmail.com",
    ]
    for email in scams:
        ok, reason = validate_email_safety(email)
        assert ok is False, f"Expected scam email {email} to be rejected"
        assert "high-risk" in reason.lower() or "impersonation" in reason.lower()


def test_invalid_syntax_and_tlds():
    invalid = [
        "",
        "not-an-email",
        "@domain.com",
        "user@",
        "user@domain",
        "user@domain.",
        "user..name@domain.com",
        ".user@domain.com",
        "user.@domain.com",
        "user+tag1+tag2@domain.com",  # excessive plus tagging
        "user@domain.invalid",
        "user@domain.test",
    ]
    for email in invalid:
        ok, reason = validate_email_safety(email)
        assert ok is False, f"Expected invalid email {email} to fail"


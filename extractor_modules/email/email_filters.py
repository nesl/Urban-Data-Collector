"""Deterministic source filters for email-backed collectors."""

from email.utils import parseaddr


def is_citizen_notification(email: dict) -> bool:
    """Accept the ``noreply`` mailbox at citizen.com or its subdomains."""
    _display_name, address = parseaddr(email.get("sender", ""))
    local, separator, domain = address.strip().lower().partition("@")
    return (
        bool(separator)
        and local == "noreply"
        and (domain == "citizen.com" or domain.endswith(".citizen.com"))
    )

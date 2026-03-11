from datetime import datetime, timezone
from pathlib import Path
from langchain_core.tools import tool

_KB_PATH = Path(__file__).parent.parent / "KNOWLEDGE_BASE.md"
_KB_CONTENT: str | None = None


def _load_kb() -> str:
    global _KB_CONTENT
    if _KB_CONTENT is None:
        _KB_CONTENT = _KB_PATH.read_text(encoding="utf-8")
    return _KB_CONTENT


@tool
def get_clinic_info() -> str:
    """Returns general information about Acme Dental clinic: hours, address, phone, and what we offer."""
    return (
        "Acme Dental Clinic — routine dental check-ups only (30 min per appointment, one dentist). "
        "Price: €60 standard | €50 students/seniors (65+). "
        "Hours: Mon–Fri 8am–6pm, Sat 9am–2pm. "
        "No walk-ins — all visits must be booked in advance. "
        "No emergency dental treatment offered. "
        "Payment: card, contactless, or cash in-clinic. No deposit required to book."
    )


@tool
def get_services() -> str:
    """Returns the services offered at Acme Dental."""
    return (
        "Acme Dental offers routine dental check-ups only. "
        "Each check-up (30 min) includes: full oral examination, gum health check, "
        "review of any concerns, and basic recommendations. "
        "X-rays are NOT included — the dentist will advise if needed. "
        "We do not offer fillings, whitening, orthodontics, or emergency care."
    )


@tool
def search_faq(question: str) -> str:
    """
    Search the Acme Dental knowledge base to answer patient questions about
    pricing, policies, cancellations, what to bring, insurance, discounts, etc.
    Args:
        question: The patient's question or topic to look up.
    """
    return _load_kb()


@tool
def get_current_datetime() -> str:
    """Returns the current date and time in GMT. Use this whenever the patient refers to
    relative dates like 'today', 'tomorrow', 'next Thursday', or 'this weekend'."""
    now = datetime.now(timezone.utc)
    return (
        f"Current date and time (GMT): {now.strftime('%A, %d %B %Y %H:%M')} UTC. "
        f"Day of week: {now.strftime('%A')}."
    )


clinic_tools = [get_clinic_info, get_services, search_faq, get_current_datetime]

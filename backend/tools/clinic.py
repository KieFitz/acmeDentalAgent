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
    return _load_kb()


@tool
def get_services() -> str:
    """Returns the services offered at Acme Dental."""
    return _load_kb()


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

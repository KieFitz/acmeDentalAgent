from datetime import datetime, timezone
from langchain_core.tools import tool


@tool
def get_clinic_info() -> str:
    """Returns general information about Acme Dental clinic including hours, address, and phone number."""
    return (
        "Acme Dental Clinic - Hours: Mon-Fri 8am-6pm, Sat 9am-2pm. "
        "Phone: (555) 123-4567. Address: 123 Main St."
    )


@tool
def get_services() -> str:
    """Returns the list of dental services offered at Acme Dental clinic."""
    return (
        "Acme Dental offers: general dentistry, routine cleanings, fillings, "
        "tooth extractions, teeth whitening, orthodontics (braces & Invisalign), "
        "crowns & bridges, root canals, and emergency dental care."
    )


@tool
def get_current_datetime() -> str:
    """Returns the current date and time in GMT. Use this whenever the patient refers to
    relative dates like 'today', 'tomorrow', 'next Thursday', or 'this weekend'."""
    now = datetime.now(timezone.utc)
    return (
        f"Current date and time (GMT): {now.strftime('%A, %d %B %Y %H:%M')} UTC. "
        f"Day of week: {now.strftime('%A')}."
    )


clinic_tools = [get_clinic_info, get_services, get_current_datetime]

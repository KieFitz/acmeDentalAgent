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


clinic_tools = [get_clinic_info, get_services]

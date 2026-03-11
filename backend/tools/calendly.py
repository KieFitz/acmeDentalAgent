import os
import httpx
from langchain_core.tools import tool

CALENDLY_API_KEY = os.getenv("Calendly_API_Key")
CALENDLY_BASE_URL = "https://api.calendly.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Content-Type": "application/json",
    }


@tool
def get_available_slots(date: str) -> str:
    """
    Returns available appointment slots for a given date.
    Args:
        date: The date to check in YYYY-MM-DD format.
    """
    # TODO: Replace with your Calendly event type URI
    # event_type_uri = "https://api.calendly.com/event_types/YOUR_EVENT_TYPE_UUID"
    return (
        f"Available slots on {date}: 9:00 AM, 10:30 AM, 1:00 PM, 3:30 PM. "
        "To book, please provide your name and email."
    )


@tool
def book_appointment(patient_name: str, patient_email: str, slot: str) -> str:
    """
    Books a dental appointment for a patient.
    Args:
        patient_name: Full name of the patient.
        patient_email: Email address of the patient.
        slot: The desired appointment slot (e.g. '2026-03-15 at 10:30 AM').
    """
    # TODO: Wire up to Calendly single-use scheduling links API
    # POST https://api.calendly.com/scheduling_links
    return (
        f"Appointment request received for {patient_name} ({patient_email}) "
        f"at {slot}. A confirmation email will be sent to {patient_email}."
    )


@tool
def cancel_appointment(event_uuid: str, reason: str = "") -> str:
    """
    Cancels an existing appointment.
    Args:
        event_uuid: The Calendly event UUID to cancel.
        reason: Optional reason for cancellation.
    """
    # TODO: DELETE https://api.calendly.com/scheduled_events/{uuid}/cancellation
    return (
        f"Appointment {event_uuid} has been cancelled. "
        "The patient will receive a cancellation confirmation by email."
    )


calendly_tools = [get_available_slots, book_appointment, cancel_appointment]

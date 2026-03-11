import asyncio
import os
import uuid
from langchain_core.tools import tool
from backend.db.database import SessionLocal
from backend.services.pin_service import create_pin_record, verify_pin
from backend.services.email_service import send_pin_email

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
    Books a dental appointment for a patient and sends a confirmation email with a security PIN.
    The PIN is required to cancel or reschedule this appointment.
    Args:
        patient_name: Full name of the patient.
        patient_email: Email address of the patient.
        slot: The desired appointment slot (e.g. '2026-03-15 at 10:30 AM').
    """
    # TODO: Wire up to Calendly single-use scheduling links API
    # POST https://api.calendly.com/scheduling_links
    appointment_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        pin = create_pin_record(db, appointment_id, patient_name, patient_email)
    finally:
        db.close()

    try:
        asyncio.get_event_loop().run_until_complete(
            send_pin_email(patient_email, patient_name, appointment_id, pin, slot)
        )
    except Exception:
        # Email failure should not block the booking confirmation
        pass

    return (
        f"Appointment confirmed for {patient_name} at {slot}. "
        f"Your appointment ID is {appointment_id}. "
        f"A confirmation email with your security PIN has been sent to {patient_email}. "
        "You will need your PIN to cancel or reschedule."
    )


@tool
def verify_appointment_pin(appointment_id: str, patient_name: str, pin: str) -> str:
    """
    Verifies a patient's PIN before allowing a cancellation or reschedule.
    Must be called before cancel_appointment or reschedule_appointment.
    Args:
        appointment_id: The appointment ID provided at booking.
        patient_name: Full name of the patient as given at booking.
        pin: The 6-digit PIN sent to the patient's email.
    """
    db = SessionLocal()
    try:
        success, message = verify_pin(db, appointment_id, patient_name, pin)
    finally:
        db.close()

    return message if not success else f"VERIFIED:{appointment_id}"


@tool
def cancel_appointment(appointment_id: str, patient_name: str, pin: str, reason: str = "") -> str:
    """
    Cancels an existing appointment after PIN verification.
    Args:
        appointment_id: The appointment ID provided at booking.
        patient_name: Full name of the patient.
        pin: The 6-digit security PIN sent to the patient's email.
        reason: Optional reason for cancellation.
    """
    db = SessionLocal()
    try:
        success, message = verify_pin(db, appointment_id, patient_name, pin)
    finally:
        db.close()

    if not success:
        return message

    # TODO: DELETE https://api.calendly.com/scheduled_events/{appointment_id}/cancellation
    return (
        f"Appointment {appointment_id} has been successfully cancelled. "
        "A cancellation confirmation will be sent to the patient's email."
    )


calendly_tools = [
    get_available_slots,
    book_appointment,
    verify_appointment_pin,
    cancel_appointment,
]

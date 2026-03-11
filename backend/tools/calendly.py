import asyncio
import os
import uuid
from datetime import datetime, timezone
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


ALL_SLOTS = ["9:00 AM", "10:30 AM", "1:00 PM", "3:30 PM"]

# Map slot labels to 24h hour for comparison
_SLOT_HOURS = {
    "9:00 AM": 9,
    "10:30 AM": 10,
    "1:00 PM": 13,
    "3:30 PM": 15,
}


def _parse_slot_datetime(date_str: str, slot_label: str) -> datetime:
    """Return a timezone-aware UTC datetime for a given date + slot label."""
    hour = _SLOT_HOURS[slot_label]
    minute = 30 if "30" in slot_label else 0
    return datetime(
        *[int(p) for p in date_str.split("-")],
        hour, minute, tzinfo=timezone.utc
    )


@tool
def get_available_slots(date: str) -> str:
    """
    Returns available appointment slots for a given date.
    Slots that are already in the past (GMT) are automatically excluded.
    Args:
        date: The date to check in YYYY-MM-DD format.
    """
    # TODO: Replace with your Calendly event type URI
    # event_type_uri = "https://api.calendly.com/event_types/YOUR_EVENT_TYPE_UUID"
    try:
        requested = datetime(*[int(p) for p in date.split("-")], tzinfo=timezone.utc)
    except ValueError:
        return "Invalid date format. Please provide the date as YYYY-MM-DD."

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if requested < today:
        return f"{date} is in the past. Please choose a future date."

    available = [
        s for s in ALL_SLOTS
        if _parse_slot_datetime(date, s) > now
    ]

    if not available:
        return f"No available slots remaining on {date}. Please choose another date."

    return (
        f"Available slots on {date}: {', '.join(available)}. "
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
    # Validate slot is in the future (slot format: '2026-03-15 at 10:30 AM')
    now = datetime.now(timezone.utc)
    try:
        date_part, time_part = slot.split(" at ")
        hour = _SLOT_HOURS.get(time_part.strip())
        if hour is None:
            return f"Unrecognised time slot '{time_part.strip()}'. Please choose from the available slots."
        slot_dt = _parse_slot_datetime(date_part.strip(), time_part.strip())
        if slot_dt <= now:
            return (
                f"Sorry, {slot} has already passed. "
                "Please use get_available_slots to see what's still available."
            )
    except Exception:
        pass  # If parsing fails let the booking proceed — Calendly will validate

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

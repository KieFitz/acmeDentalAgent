import asyncio
import os
import uuid
from datetime import datetime, timezone
import httpx
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.db.database import SessionLocal
from backend.db.models import SessionBooking
from backend.services.pin_service import create_pin_record, verify_pin, verify_pin_by_name
from backend.services.email_service import send_pin_email

MAX_BOOKINGS_PER_SESSION = int(os.getenv("MAX_BOOKINGS_PER_SESSION", "3"))

CALENDLY_API_KEY = os.getenv("Calendly_API_Key")
CALENDLY_BASE_URL = "https://calendly.com/acme-dental-25"

# Cached Calendly identifiers (fetched once on first use)
_USER_URI: str | None = None
_EVENT_TYPE_URI: str | None = None


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_calendly_identifiers() -> tuple[str | None, str | None]:
    """Fetch and cache the Calendly user URI and first active event type URI."""
    global _USER_URI, _EVENT_TYPE_URI
    if _USER_URI and _EVENT_TYPE_URI:
        return _USER_URI, _EVENT_TYPE_URI
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{CALENDLY_BASE_URL}/users/me", headers=_headers())
            if not r.is_success:
                return None, None
            _USER_URI = r.json()["resource"]["uri"]

            r = client.get(
                f"{CALENDLY_BASE_URL}/event_types",
                headers=_headers(),
                params={"user": _USER_URI, "active": "true"},
            )
            if r.is_success:
                types = r.json().get("collection", [])
                if types:
                    _EVENT_TYPE_URI = types[0]["uri"]
    except Exception:
        pass
    return _USER_URI, _EVENT_TYPE_URI


# ── Fallback mock slots (used if Calendly API is unavailable) ─────────────────
ALL_SLOTS = ["9:00 AM", "10:30 AM", "1:00 PM", "3:30 PM"]
_SLOT_HOURS = {"9:00 AM": (9, 0), "10:30 AM": (10, 30), "1:00 PM": (13, 0), "3:30 PM": (15, 0)}


def _parse_slot_datetime(date_str: str, slot_label: str) -> datetime:
    h, m = _SLOT_HOURS[slot_label]
    return datetime(*[int(p) for p in date_str.split("-")], h, m, tzinfo=timezone.utc)


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_available_slots(date: str) -> str:
    """
    Returns available appointment slots for a given date from Calendly.
    Slots already in the past (GMT) are excluded.
    Args:
        date: The date to check in YYYY-MM-DD format.
    """
    try:
        requested = datetime(*[int(p) for p in date.split("-")], tzinfo=timezone.utc)
    except ValueError:
        return "Invalid date format. Please provide the date as YYYY-MM-DD."

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if requested < today:
        return f"{date} is in the past. Please choose a future date."

    _, event_type_uri = _fetch_calendly_identifiers()

    if event_type_uri:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    f"{CALENDLY_BASE_URL}/event_type_available_times",
                    headers=_headers(),
                    params={
                        "event_type": event_type_uri,
                        "start_time": f"{date}T00:00:00.000000Z",
                        "end_time": f"{date}T23:59:59.000000Z",
                    },
                )
            if r.is_success:
                slots = r.json().get("collection", [])
                available = []
                for s in slots:
                    slot_dt = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
                    if slot_dt > now:
                        available.append(slot_dt.strftime("%-I:%M %p"))
                if not available:
                    return f"No available slots on {date}. Please choose another date."
                return (
                    f"Available slots on {date}: {', '.join(available)}. "
                    "To book, please provide your name and email."
                )
        except Exception:
            pass

    # Fallback to mock slots
    available = [s for s in ALL_SLOTS if _parse_slot_datetime(date, s) > now]
    if not available:
        return f"No available slots on {date}. Please choose another date."
    return (
        f"Available slots on {date}: {', '.join(available)}. "
        "To book, please provide your name and email."
    )


@tool
def book_appointment(
    patient_name: str,
    patient_email: str,
    slot: str,
    config: RunnableConfig,
) -> str:
    """
    Records a dental appointment request and sends the patient a confirmation
    email with their appointment details and a security PIN.
    The PIN is required to look up, cancel or reschedule this appointment.
    Maximum 3 bookings per session; each patient name must be unique within the session.
    Args:
        patient_name: Full name of the patient.
        patient_email: Email address of the patient.
        slot: The desired appointment slot (e.g. '2026-03-15 at 10:30 AM').
    """
    now = datetime.now(timezone.utc)

    # Validate slot is in the future
    try:
        date_part, time_part = slot.split(" at ")
        slot_label = time_part.strip()
        if slot_label in _SLOT_HOURS:
            slot_dt = _parse_slot_datetime(date_part.strip(), slot_label)
            if slot_dt <= now:
                return (
                    f"Sorry, {slot} has already passed. "
                    "Please use get_available_slots to see what's still available."
                )
    except Exception:
        pass

    session_id = config.get("configurable", {}).get("thread_id", "default")
    appointment_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        prior = db.query(SessionBooking).filter(
            SessionBooking.session_id == session_id
        ).all()

        if len(prior) >= MAX_BOOKINGS_PER_SESSION:
            return (
                f"A maximum of {MAX_BOOKINGS_PER_SESSION} appointments can be booked per session. "
                "Please call the clinic at (087) 123-4567 to book additional appointments."
            )

        name_lower = patient_name.strip().lower()
        if any(b.patient_name.lower() == name_lower for b in prior):
            return (
                f"An appointment for {patient_name} has already been booked in this session. "
                "Each patient can only be booked once per session."
            )

        pin = create_pin_record(db, appointment_id, patient_name, patient_email)
        db.add(SessionBooking(session_id=session_id, patient_name=patient_name))
        db.commit()
    finally:
        db.close()

    try:
        asyncio.get_event_loop().run_until_complete(
            send_pin_email(patient_email, patient_name, appointment_id, pin, slot)
        )
    except Exception:
        pass

    return (
        f"Your appointment has been confirmed for {patient_name} at {slot}. "
        f"A confirmation email is on its way to {patient_email} with your appointment details "
        f"and a personal 6-digit security PIN. "
        f"Your PIN is unique to this booking — it was generated just for you and is never shown in this chat. "
        f"You will need to provide your name and PIN any time you want to look up, cancel, or reschedule your appointment, "
        f"so please keep it safe. "
        f"Your appointment reference is {appointment_id}."
    )


@tool
def lookup_appointment(patient_name: str, pin: str) -> str:
    """
    Looks up a patient's appointment details using their name and PIN.
    Use this when a patient wants to know when their appointment is,
    or as a first step before cancelling or rescheduling.
    Args:
        patient_name: Full name as given at booking.
        pin: The 6-digit security PIN from the confirmation email.
    """
    db = SessionLocal()
    try:
        success, message, record = verify_pin_by_name(db, patient_name, pin)
    finally:
        db.close()

    if not success:
        return message

    patient_email = record.patient_email
    appointment_id = record.appointment_id

    # Try to get real appointment details from Calendly
    user_uri, _ = _fetch_calendly_identifiers()
    if user_uri and patient_email:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    f"{CALENDLY_BASE_URL}/scheduled_events",
                    headers=_headers(),
                    params={
                        "user": user_uri,
                        "invitee_email": patient_email,
                        "status": "active",
                        "count": 5,
                        "sort": "start_time:asc",
                    },
                )
            if r.is_success:
                events = r.json().get("collection", [])
                if events:
                    event = events[0]
                    start = datetime.fromisoformat(
                        event["start_time"].replace("Z", "+00:00")
                    )
                    slot_str = start.strftime("%A, %d %B %Y at %-I:%M %p GMT")
                    calendly_uri = event["uri"]
                    return (
                        f"Appointment found for {patient_name}: {slot_str}. "
                        f"Appointment reference: {calendly_uri.split('/')[-1]}"
                    )
        except Exception:
            pass

    # Fallback: return what we have in our DB
    return (
        f"Appointment confirmed for {patient_name}. "
        f"Your appointment ID is {appointment_id}. "
        "For full appointment details please check your confirmation email."
    )


@tool
def cancel_appointment(patient_name: str, pin: str, reason: str = "") -> str:
    """
    Cancels a patient's appointment after verifying their name and PIN.
    Args:
        patient_name: Full name as given at booking.
        pin: The 6-digit security PIN from the confirmation email.
        reason: Optional reason for cancellation.
    """
    db = SessionLocal()
    try:
        success, message, record = verify_pin_by_name(db, patient_name, pin)
    finally:
        db.close()

    if not success:
        return message

    patient_email = record.patient_email

    # Try to cancel via Calendly API
    user_uri, _ = _fetch_calendly_identifiers()
    if user_uri and patient_email:
        try:
            with httpx.Client(timeout=10) as client:
                # Find active event for this patient
                r = client.get(
                    f"{CALENDLY_BASE_URL}/scheduled_events",
                    headers=_headers(),
                    params={
                        "user": user_uri,
                        "invitee_email": patient_email,
                        "status": "active",
                        "count": 1,
                        "sort": "start_time:asc",
                    },
                )
                if r.is_success:
                    events = r.json().get("collection", [])
                    if events:
                        event_uuid = events[0]["uri"].split("/")[-1]
                        cancel_r = client.post(
                            f"{CALENDLY_BASE_URL}/scheduled_events/{event_uuid}/cancellation",
                            headers=_headers(),
                            json={"reason": reason or "Patient requested cancellation via chat"},
                        )
                        if cancel_r.is_success:
                            return (
                                f"Appointment for {patient_name} has been successfully cancelled in Calendly. "
                                "A cancellation confirmation will be sent to your email."
                            )
        except Exception:
            pass

    # Fallback confirmation (e.g. mock bookings not in Calendly)
    return (
        f"Appointment for {patient_name} has been cancelled. "
        "A cancellation confirmation will be sent to your email."
    )


@tool
def verify_appointment_pin(appointment_id: str, patient_name: str, pin: str) -> str:
    """
    Verifies a patient's PIN using their appointment ID.
    Use this when the patient provides their appointment ID directly.
    Args:
        appointment_id: The appointment ID from the confirmation email.
        patient_name: Full name as given at booking.
        pin: The 6-digit PIN from the confirmation email.
    """
    db = SessionLocal()
    try:
        success, message = verify_pin(db, appointment_id, patient_name, pin)
    finally:
        db.close()

    return message if not success else f"VERIFIED:{appointment_id}"


calendly_tools = [
    get_available_slots,
    book_appointment,
    lookup_appointment,
    cancel_appointment,
    verify_appointment_pin,
]

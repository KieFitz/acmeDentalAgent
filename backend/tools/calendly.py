import os
from datetime import datetime, timezone
import httpx
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.db.database import SessionLocal
from backend.db.models import SessionBooking
from backend.services.pin_service import create_pin_record, generate_pin, verify_pin, verify_pin_by_name

MAX_BOOKINGS_PER_SESSION = int(os.getenv("MAX_BOOKINGS_PER_SESSION", "3"))

CALENDLY_API_KEY = os.getenv("CALENDLY_API_KEY")
CALENDLY_BASE_URL = "https://api.calendly.com"

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

    return "Unable to reach the booking system. Please call us at (087) 123-4567 to check availability."


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
    # Confirm slot is available via Calendly — this also catches past slots
    _, event_type_uri = _fetch_calendly_identifiers()
    if not event_type_uri:
        return "Unable to reach the booking system. Please call us at (087) 123-4567 to book your appointment."

    session_id = config.get("configurable", {}).get("thread_id", "default")

    # Check session booking limits before doing anything else
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

        # Check if this patient already has an active Calendly appointment
        from backend.db.models import AppointmentPin
        existing = (
            db.query(AppointmentPin)
            .filter(AppointmentPin.patient_name.ilike(patient_name.strip()))
            .order_by(AppointmentPin.created_at.desc())
            .first()
        )
    finally:
        db.close()

    # If a record exists, verify with Calendly whether the appointment is still active
    if existing:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(
                    f"{CALENDLY_BASE_URL}/scheduled_events/{existing.appointment_id}",
                    headers=_headers(),
                )
            if r.is_success:
                event = r.json().get("resource", {})
                if event.get("status") == "active":
                    start = datetime.fromisoformat(
                        event["start_time"].replace("Z", "+00:00")
                    )
                    slot_str = start.strftime("%A, %d %B %Y at %-I:%M %p GMT")
                    return (
                        f"{patient_name} already has an active appointment booked for {slot_str}. "
                        "Would you like to reschedule it to a different time instead? "
                        "If this booking is for a different person, please provide their full name."
                    )
        except Exception:
            pass  # Calendly unreachable — allow booking to proceed

    # Generate PIN before creating the Calendly booking so it can be embedded
    pin = generate_pin()

    try:
        date_part = slot.split(" at ")[0].strip()
        time_label = slot.split(" at ")[1].strip()
    except (ValueError, IndexError):
        return "Invalid slot format. Please use a slot from get_available_slots (e.g. '2026-03-20 at 9:00 AM')."

    with httpx.Client(timeout=15) as client:
        # Find the exact ISO start_time matching the requested slot label
        r = client.get(
            f"{CALENDLY_BASE_URL}/event_type_available_times",
            headers=_headers(),
            params={
                "event_type": event_type_uri,
                "start_time": f"{date_part}T00:00:00.000000Z",
                "end_time": f"{date_part}T23:59:59.000000Z",
            },
        )
        if not r.is_success:
            return "Unable to verify slot availability. Please call us at (087) 123-4567."

        matching_start_time = None
        available_labels = []
        for s in r.json().get("collection", []):
            slot_dt = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
            label = slot_dt.strftime("%-I:%M %p")
            available_labels.append(label)
            if label == time_label:
                matching_start_time = s["start_time"]

        if not matching_start_time:
            if available_labels:
                return (
                    f"Sorry, {slot} is not available. "
                    f"Available slots on {date_part}: {', '.join(available_labels)}."
                )
            return f"No available slots on {date_part}. Please choose another date."

        # Get location from event type
        et_r = client.get(
            f"{CALENDLY_BASE_URL}/event_types/{event_type_uri.split('/')[-1]}",
            headers=_headers(),
        )
        booking_location = {"kind": "physical", "location": "Acme Dental Clinic"}
        if et_r.is_success:
            locs = et_r.json().get("resource", {}).get("locations", [])
            if locs:
                booking_location = {
                    "kind": locs[0].get("kind", "physical"),
                    "location": locs[0].get("location", "Acme Dental Clinic"),
                }

        name_parts = patient_name.strip().split(" ", 1)
        booking_r = client.post(
            f"{CALENDLY_BASE_URL}/invitees",
            headers=_headers(),
            json={
                "event_type": event_type_uri,
                "start_time": matching_start_time,
                "invitee": {
                    "name": patient_name,
                    "first_name": name_parts[0],
                    "last_name": name_parts[1] if len(name_parts) > 1 else "",
                    "email": patient_email,
                    "timezone": "Europe/Dublin",
                },
                "location": booking_location,
                "booking_source": "ai_scheduling_assistant",
                "questions_and_answers": [
                    {"question": "Your PIN", "answer": pin, "position": 0}
                ],
            },
        )

    if not booking_r.is_success:
        return (
            f"The booking could not be completed in Calendly ({booking_r.status_code}). "
            "Please call us at (087) 123-4567 to book your appointment."
        )

    # Use Calendly's scheduled event UUID as our appointment_id
    # Response field is "event", not "scheduled_event"
    scheduled_event_uri = booking_r.json().get("resource", {}).get("event", "")
    appointment_id = scheduled_event_uri.split("/")[-1] if scheduled_event_uri else patient_email

    # Store PIN record in DB
    db = SessionLocal()
    try:
        create_pin_record(db, appointment_id, patient_name, patient_email, pin=pin)
        db.add(SessionBooking(session_id=session_id, patient_name=patient_name))
        db.commit()
    finally:
        db.close()

    return (
        f"Appointment confirmed for {patient_name} on {slot}.\n\n"
        f"Your security PIN is: **{pin}**\n\n"
        f"Please save this PIN — you will need it along with your name to look up, "
        f"amend, or cancel your appointment in a new session. "
        f"Calendly will also send a confirmation email to {patient_email}.\n\n"
        f"Appointment reference: {appointment_id}"
    )


@tool
def lookup_appointment(patient_name: str, config: RunnableConfig, pin: str = "") -> str:
    """
    Looks up a patient's appointment details.
    If the booking was made in the current session, no PIN is needed.
    If this is a new session, the patient must provide their 6-digit PIN.
    Use this when a patient wants to know when their appointment is,
    or as a first step before cancelling or rescheduling.
    Args:
        patient_name: Full name as given at booking.
        pin: The 6-digit security PIN from the confirmation email (only needed in a new session).
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")

    db = SessionLocal()
    try:
        # Check if this booking was made in the current session — no PIN needed
        session_match = db.query(SessionBooking).filter(
            SessionBooking.session_id == session_id,
            SessionBooking.patient_name.ilike(patient_name.strip()),
        ).first()

        if session_match:
            from backend.db.models import AppointmentPin
            record = db.query(AppointmentPin).filter(
                AppointmentPin.patient_name.ilike(patient_name.strip())
            ).order_by(AppointmentPin.created_at.desc()).first()
            if not record:
                return f"No appointment record found for {patient_name}."
            appointment_id = record.appointment_id
        else:
            # New session — PIN required
            if not pin:
                return (
                    "To look up your appointment from a new session, "
                    "please provide your 6-digit security PIN from your confirmation email."
                )
            success, message, record = verify_pin_by_name(db, patient_name, pin)
            if not success:
                return message
            appointment_id = record.appointment_id
    finally:
        db.close()

    # Fetch appointment details directly from Calendly using the stored event UUID
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{CALENDLY_BASE_URL}/scheduled_events/{appointment_id}",
                headers=_headers(),
            )
        if r.is_success:
            event = r.json().get("resource", {})
            start = datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
            slot_str = start.strftime("%A, %d %B %Y at %-I:%M %p GMT")
            return (
                f"Appointment found for {patient_name}: {slot_str}. "
                f"Appointment reference: {appointment_id}"
            )
    except Exception:
        pass

    return (
        f"Could not retrieve appointment details from Calendly for {patient_name}. "
        "Please check your confirmation email or call us at (087) 123-4567."
    )


@tool
def cancel_appointment(patient_name: str, config: RunnableConfig, pin: str = "", reason: str = "") -> str:
    """
    Cancels a patient's appointment.
    If the booking was made in the current session, no PIN is needed.
    If this is a new session, the patient must provide their 6-digit PIN.
    Args:
        patient_name: Full name as given at booking.
        pin: The 6-digit security PIN from the confirmation email (only needed in a new session).
        reason: Optional reason for cancellation.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")

    db = SessionLocal()
    try:
        # Check if this booking was made in the current session — no PIN needed
        session_match = db.query(SessionBooking).filter(
            SessionBooking.session_id == session_id,
            SessionBooking.patient_name.ilike(patient_name.strip()),
        ).first()

        if session_match:
            from backend.db.models import AppointmentPin
            record = db.query(AppointmentPin).filter(
                AppointmentPin.patient_name.ilike(patient_name.strip())
            ).order_by(AppointmentPin.created_at.desc()).first()
            if not record:
                return f"No appointment record found for {patient_name}."
            appointment_id = record.appointment_id
        else:
            # New session — PIN required
            if not pin:
                return (
                    "To cancel your appointment from a new session, "
                    "please provide your 6-digit security PIN from your confirmation email."
                )
            success, message, record = verify_pin_by_name(db, patient_name, pin)
            if not success:
                return message
            appointment_id = record.appointment_id
    finally:
        db.close()

    # Cancel directly using the stored Calendly event UUID
    try:
        with httpx.Client(timeout=10) as client:
            cancel_r = client.post(
                f"{CALENDLY_BASE_URL}/scheduled_events/{appointment_id}/cancellation",
                headers=_headers(),
                json={"reason": reason or "Patient requested cancellation via chat"},
            )
        if cancel_r.is_success:
            return (
                f"Appointment for {patient_name} has been successfully cancelled. "
                "A cancellation confirmation will be sent to your email."
            )
    except Exception:
        pass

    return (
        "Cancellation could not be completed. "
        "Please call us at (087) 123-4567 to cancel your appointment."
    )


@tool
def reschedule_appointment(
    patient_name: str,
    new_slot: str,
    config: RunnableConfig,
    pin: str = "",
) -> str:
    """
    Reschedules a patient's appointment to a new slot.
    Cancels the existing Calendly booking and creates a new one.
    The patient's PIN remains the same — only the appointment reference changes.
    If the booking was made in the current session, no PIN is needed.
    If this is a new session, the patient must provide their 6-digit PIN.
    Args:
        patient_name: Full name as given at booking.
        new_slot: The new desired slot (e.g. '2026-03-20 at 10:30 AM').
        pin: The 6-digit security PIN (only needed in a new session).
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")

    # Verify identity and get existing record
    db = SessionLocal()
    try:
        session_match = db.query(SessionBooking).filter(
            SessionBooking.session_id == session_id,
            SessionBooking.patient_name.ilike(patient_name.strip()),
        ).first()

        if session_match:
            from backend.db.models import AppointmentPin
            record = db.query(AppointmentPin).filter(
                AppointmentPin.patient_name.ilike(patient_name.strip())
            ).order_by(AppointmentPin.created_at.desc()).first()
            if not record:
                return f"No appointment record found for {patient_name}."
        else:
            if not pin:
                return (
                    "To reschedule from a new session, "
                    "please provide your 6-digit security PIN from your confirmation email."
                )
            success, message, record = verify_pin_by_name(db, patient_name, pin)
            if not success:
                return message

        old_appointment_id = record.appointment_id
        patient_email = record.patient_email
        record_id = record.id
    finally:
        db.close()

    # Get event type for new booking
    _, event_type_uri = _fetch_calendly_identifiers()
    if not event_type_uri:
        return "Unable to reach the booking system. Please call us at (087) 123-4567."

    try:
        date_part = new_slot.split(" at ")[0].strip()
        time_label = new_slot.split(" at ")[1].strip()
    except (ValueError, IndexError):
        return "Invalid slot format. Please use a format like '2026-03-20 at 9:00 AM'."

    with httpx.Client(timeout=15) as client:
        # Confirm new slot is available
        r = client.get(
            f"{CALENDLY_BASE_URL}/event_type_available_times",
            headers=_headers(),
            params={
                "event_type": event_type_uri,
                "start_time": f"{date_part}T00:00:00.000000Z",
                "end_time": f"{date_part}T23:59:59.000000Z",
            },
        )
        if not r.is_success:
            return "Unable to check slot availability. Please call us at (087) 123-4567."

        matching_start_time = None
        available_labels = []
        for s in r.json().get("collection", []):
            slot_dt = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
            label = slot_dt.strftime("%-I:%M %p")
            available_labels.append(label)
            if label == time_label:
                matching_start_time = s["start_time"]

        if not matching_start_time:
            if available_labels:
                return (
                    f"Sorry, {new_slot} is not available. "
                    f"Available slots on {date_part}: {', '.join(available_labels)}."
                )
            return f"No available slots on {date_part}. Please choose another date."

        # Cancel the old booking
        cancel_r = client.post(
            f"{CALENDLY_BASE_URL}/scheduled_events/{old_appointment_id}/cancellation",
            headers=_headers(),
            json={"reason": "Patient requested reschedule via chat"},
        )
        if not cancel_r.is_success:
            return (
                "Could not cancel the existing appointment. "
                "Please call us at (087) 123-4567 to reschedule."
            )

        # Get location from event type
        et_r = client.get(
            f"{CALENDLY_BASE_URL}/event_types/{event_type_uri.split('/')[-1]}",
            headers=_headers(),
        )
        booking_location = {"kind": "physical", "location": "Acme Dental Clinic"}
        if et_r.is_success:
            locs = et_r.json().get("resource", {}).get("locations", [])
            if locs:
                booking_location = {
                    "kind": locs[0].get("kind", "physical"),
                    "location": locs[0].get("location", "Acme Dental Clinic"),
                }

        # Book the new slot — PIN stays the same, not included again
        name_parts = patient_name.strip().split(" ", 1)
        booking_r = client.post(
            f"{CALENDLY_BASE_URL}/invitees",
            headers=_headers(),
            json={
                "event_type": event_type_uri,
                "start_time": matching_start_time,
                "invitee": {
                    "name": patient_name,
                    "first_name": name_parts[0],
                    "last_name": name_parts[1] if len(name_parts) > 1 else "",
                    "email": patient_email,
                    "timezone": "Europe/Dublin",
                },
                "location": booking_location,
                "booking_source": "ai_scheduling_assistant",
            },
        )

    if not booking_r.is_success:
        return (
            f"The old appointment was cancelled but the new booking failed ({booking_r.status_code}). "
            "Please call us at (087) 123-4567 to complete your reschedule."
        )

    # Update AppointmentPin with new Calendly event UUID — PIN stays the same
    new_event_uri = booking_r.json().get("resource", {}).get("event", "")
    new_appointment_id = new_event_uri.split("/")[-1] if new_event_uri else old_appointment_id

    db = SessionLocal()
    try:
        from backend.db.models import AppointmentPin
        record = db.query(AppointmentPin).filter(AppointmentPin.id == record_id).first()
        if record:
            record.appointment_id = new_appointment_id
            record.failed_attempts = 0
            db.commit()
    finally:
        db.close()

    return (
        f"Appointment for {patient_name} has been rescheduled to {new_slot}. "
        f"Your PIN remains the same — keep it safe for future amendments. "
        f"Calendly will send a confirmation email to {patient_email}. "
        f"New appointment reference: {new_appointment_id}"
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
    reschedule_appointment,
    verify_appointment_pin,
]

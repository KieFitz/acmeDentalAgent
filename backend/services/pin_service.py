import secrets
import bcrypt
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.db.models import AppointmentPin

MAX_ATTEMPTS = 3


def generate_pin() -> str:
    """Generate a cryptographically secure 6-digit PIN."""
    return str(secrets.randbelow(1_000_000)).zfill(6)


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def _check_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def create_pin_record(
    db: Session,
    appointment_id: str,
    patient_name: str,
    patient_email: str,
) -> str:
    """
    Generate a PIN, store its hash, and return the plaintext PIN.
    The plaintext PIN is never persisted — only the hash is stored.
    """
    pin = generate_pin()
    record = AppointmentPin(
        appointment_id=appointment_id,
        patient_name=patient_name,
        patient_email=patient_email,
        pin_hash=_hash_pin(pin),
    )
    db.add(record)
    db.commit()
    return pin


def verify_pin(
    db: Session,
    appointment_id: str,
    patient_name: str,
    pin: str,
) -> tuple[bool, str]:
    """
    Verify a patient's PIN for a given appointment.
    Returns (success, message).
    Locks the record after MAX_ATTEMPTS failed tries.
    """
    record: AppointmentPin | None = (
        db.query(AppointmentPin)
        .filter(AppointmentPin.appointment_id == appointment_id)
        .first()
    )

    if record is None:
        return False, "Appointment not found. Please check your appointment ID."

    if record.locked:
        return False, (
            "This appointment is locked due to too many failed PIN attempts. "
            "Please call the clinic at (555) 123-4567 for assistance."
        )

    if record.patient_name.lower() != patient_name.strip().lower():
        return False, "The name provided does not match our records."

    if not _check_pin(pin, record.pin_hash):
        record.failed_attempts += 1
        if record.failed_attempts >= MAX_ATTEMPTS:
            record.locked = True
            db.commit()
            return False, (
                "Incorrect PIN. This appointment is now locked after too many failed attempts. "
                "Please call us at (555) 123-4567."
            )
        remaining = MAX_ATTEMPTS - record.failed_attempts
        db.commit()
        return False, f"Incorrect PIN. {remaining} attempt(s) remaining."

    # Success — reset failed attempts
    record.failed_attempts = 0
    db.commit()
    return True, "PIN verified successfully."


def verify_pin_by_name(
    db: Session,
    patient_name: str,
    pin: str,
) -> tuple[bool, str, AppointmentPin | None]:
    """
    Verify a PIN by searching for the patient by name (case-insensitive).
    Used when the patient doesn't have their appointment_id handy.
    Returns (success, message, record_or_None).
    """
    records = (
        db.query(AppointmentPin)
        .filter(func.lower(AppointmentPin.patient_name) == patient_name.strip().lower())
        .order_by(AppointmentPin.created_at.desc())
        .all()
    )

    if not records:
        return False, "No appointment found for that name and PIN.", None

    for record in records:
        if record.locked:
            continue

        if _check_pin(pin, record.pin_hash):
            record.failed_attempts = 0
            db.commit()
            return True, "Verified.", record

        record.failed_attempts += 1
        if record.failed_attempts >= MAX_ATTEMPTS:
            record.locked = True
        db.commit()
        remaining = MAX_ATTEMPTS - record.failed_attempts
        if remaining > 0:
            return False, f"Incorrect PIN. {remaining} attempt(s) remaining.", None
        return False, (
            "This appointment is now locked due to too many failed PIN attempts. "
            "Please call the clinic at (087) 123-4567 for assistance."
        ), None

    return False, "No appointment found for that name and PIN.", None

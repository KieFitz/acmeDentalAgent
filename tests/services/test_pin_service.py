import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.database import Base
from backend.db.models import AppointmentPin
from backend.services.pin_service import generate_pin, create_pin_record, verify_pin

# In-memory SQLite DB for tests — no file created, no cleanup needed
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
TestSession = sessionmaker(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()
    # Clear rows between tests
    session.query(AppointmentPin).delete()
    session.commit()


# ── generate_pin ─────────────────────────────────────────────────────────────

def test_pin_is_six_digits():
    pin = generate_pin()
    assert len(pin) == 6
    assert pin.isdigit()


def test_pin_is_zero_padded():
    # Run many times to probabilistically hit low numbers
    for _ in range(50):
        pin = generate_pin()
        assert len(pin) == 6


# ── create_pin_record ─────────────────────────────────────────────────────────

def test_create_pin_record_returns_plaintext(db):
    pin = create_pin_record(db, "appt-001", "John Smith", "john@example.com")
    assert len(pin) == 6
    assert pin.isdigit()


def test_create_pin_record_stores_hash(db):
    create_pin_record(db, "appt-002", "Jane Doe", "jane@example.com")
    record = db.query(AppointmentPin).filter_by(appointment_id="appt-002").first()
    assert record is not None
    assert record.pin_hash != ""
    assert record.pin_hash != "123456"  # hash is never plaintext


# ── verify_pin ────────────────────────────────────────────────────────────────

def test_verify_correct_pin(db):
    pin = create_pin_record(db, "appt-003", "John Smith", "john@example.com")
    success, msg = verify_pin(db, "appt-003", "John Smith", pin)
    assert success is True


def test_verify_wrong_pin(db):
    create_pin_record(db, "appt-004", "John Smith", "john@example.com")
    success, msg = verify_pin(db, "appt-004", "John Smith", "000000")
    assert success is False
    assert "incorrect" in msg.lower()


def test_verify_case_insensitive_name(db):
    pin = create_pin_record(db, "appt-005", "John Smith", "john@example.com")
    success, _ = verify_pin(db, "appt-005", "john smith", pin)
    assert success is True


def test_verify_wrong_name(db):
    pin = create_pin_record(db, "appt-006", "John Smith", "john@example.com")
    success, msg = verify_pin(db, "appt-006", "Jane Doe", pin)
    assert success is False
    assert "name" in msg.lower()


def test_verify_unknown_appointment(db):
    success, msg = verify_pin(db, "does-not-exist", "John Smith", "123456")
    assert success is False
    assert "not found" in msg.lower()


def test_lock_after_three_failed_attempts(db):
    create_pin_record(db, "appt-007", "John Smith", "john@example.com")
    for _ in range(3):
        verify_pin(db, "appt-007", "John Smith", "000000")
    success, msg = verify_pin(db, "appt-007", "John Smith", "000000")
    assert success is False
    assert "locked" in msg.lower()


def test_locked_record_blocks_correct_pin(db):
    pin = create_pin_record(db, "appt-008", "John Smith", "john@example.com")
    for _ in range(3):
        verify_pin(db, "appt-008", "John Smith", "000000")
    # Even correct PIN is rejected when locked
    success, msg = verify_pin(db, "appt-008", "John Smith", pin)
    assert success is False
    assert "locked" in msg.lower()

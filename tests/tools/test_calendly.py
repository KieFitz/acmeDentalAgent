from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from backend.tools.calendly import get_available_slots, book_appointment, get_opening_hours


# ── get_available_slots ──────────────────────────────────────────────────────

def test_past_date_rejected():
    result = get_available_slots.invoke({"date": "2020-01-01"})
    assert "past" in result.lower()


def test_invalid_date_format():
    result = get_available_slots.invoke({"date": "not-a-date"})
    assert "invalid" in result.lower()


def test_future_date_returns_all_slots():
    # Fix "now" to midnight so no slots are filtered
    fixed_now = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    with patch("backend.tools.calendly.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_available_slots.invoke({"date": "2026-03-21"})
    assert "9:00 AM" in result
    assert "10:30 AM" in result
    assert "1:00 PM" in result
    assert "3:30 PM" in result


def test_today_filters_past_slots():
    # It's 14:00 UTC — only 3:30 PM should remain
    fixed_now = datetime(2026, 3, 11, 14, 0, tzinfo=timezone.utc)
    with patch("backend.tools.calendly.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_available_slots.invoke({"date": "2026-03-11"})
    assert "9:00 AM" not in result
    assert "10:30 AM" not in result
    assert "1:00 PM" not in result
    assert "3:30 PM" in result


def test_all_slots_gone_today():
    # It's 22:00 UTC — all slots have passed
    fixed_now = datetime(2026, 3, 11, 22, 0, tzinfo=timezone.utc)
    with patch("backend.tools.calendly.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_available_slots.invoke({"date": "2026-03-11"})
    assert "No available slots" in result


# ── book_appointment ─────────────────────────────────────────────────────────

def test_book_rejects_past_slot():
    fixed_now = datetime(2026, 3, 11, 14, 0, tzinfo=timezone.utc)
    with patch("backend.tools.calendly.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = book_appointment.invoke({
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "slot": "2026-03-11 at 9:00 AM",
        })
    assert "passed" in result.lower()


def test_book_rejects_unknown_slot():
    fixed_now = datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc)
    with patch("backend.tools.calendly.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = book_appointment.invoke({
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "slot": "2026-03-15 at 2:00 PM",
        })
    assert "unrecognised" in result.lower()


def test_book_future_slot_succeeds():
    fixed_now = datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc)
    mock_db = MagicMock()
    with patch("backend.tools.calendly.datetime") as mock_dt, \
         patch("backend.tools.calendly.SessionLocal", return_value=mock_db), \
         patch("backend.tools.calendly.create_pin_record", return_value="123456"), \
         patch("backend.tools.calendly.asyncio") as mock_asyncio:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_asyncio.get_event_loop.return_value.run_until_complete.return_value = None
        result = book_appointment.invoke({
            "patient_name": "Jane Doe",
            "patient_email": "jane@example.com",
            "slot": "2026-03-15 at 10:30 AM",
        })
    assert "confirmed" in result.lower()
    assert "Jane Doe" in result
    assert "jane@example.com" in result
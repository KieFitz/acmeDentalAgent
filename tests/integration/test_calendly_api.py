"""
Integration tests for the Calendly API.
These tests hit the REAL Calendly API and require a valid CALENDLY_API_KEY in .env.

Run with:
    uv run pytest tests/integration/test_calendly_api.py -v -s
"""
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

CALENDLY_API_KEY = os.getenv("CALENDLY_API_KEY")
BASE_URL = "https://api.calendly.com"


def headers():
    return {"Authorization": f"Bearer {CALENDLY_API_KEY}"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def next_weekday(days_ahead: int = 3) -> str:
    """Return a date string YYYY-MM-DD that is a weekday at least `days_ahead` from today."""
    d = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    while d.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_api_key_is_set():
    """Fail immediately if the API key is missing from .env."""
    assert CALENDLY_API_KEY, "CALENDLY_API_KEY is not set in .env"
    assert len(CALENDLY_API_KEY) > 10, "CALENDLY_API_KEY looks too short to be valid"


def test_get_current_user():
    """Verify the PAT token is valid and can fetch the current user."""
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.text[:500]}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()["resource"]
    print(f"User: {data.get('name')} ({data.get('email')})")
    print(f"User URI: {data.get('uri')}")
    assert "uri" in data


def test_get_event_types():
    """Verify there is at least one active event type (needed for bookings)."""
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    assert r.status_code == 200
    user_uri = r.json()["resource"]["uri"]

    r = httpx.get(f"{BASE_URL}/event_types", headers=headers(), params={"user": user_uri, "active": "true"})
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.text[:800]}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    types = r.json().get("collection", [])
    print(f"\nFound {len(types)} active event type(s):")
    for t in types:
        print(f"  - {t.get('name')} | URI: {t.get('uri')} | Duration: {t.get('duration')} min")

    assert len(types) > 0, (
        "No active event types found on this Calendly account. "
        "Create a dental check-up event type at calendly.com/event-types."
    )


def test_get_available_times():
    """Fetch real available slots for a future weekday."""
    # Get user + event type
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    assert r.status_code == 200
    user_uri = r.json()["resource"]["uri"]

    r = httpx.get(f"{BASE_URL}/event_types", headers=headers(), params={"user": user_uri, "active": "true"})
    assert r.status_code == 200
    types = r.json().get("collection", [])
    assert types, "No active event types — run test_get_event_types first"

    event_type_uri = types[0]["uri"]
    date = next_weekday(days_ahead=3)

    r = httpx.get(
        f"{BASE_URL}/event_type_available_times",
        headers=headers(),
        params={
            "event_type": event_type_uri,
            "start_time": f"{date}T00:00:00.000000Z",
            "end_time": f"{date}T23:59:59.000000Z",
        },
    )
    print(f"\nChecking availability for: {date}")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:800]}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    slots = r.json().get("collection", [])
    print(f"\nAvailable slots ({len(slots)}):")
    for s in slots:
        start = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
        print(f"  - {start.strftime('%I:%M %p')} GMT")

    # Not an error if there are no slots — just report it
    if not slots:
        print("No available slots on that date — try a different date or check Calendly availability settings.")


def test_create_scheduling_link():
    """Test that we can create a single-use scheduling link (needed for book_appointment)."""
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    assert r.status_code == 200
    user_uri = r.json()["resource"]["uri"]

    r = httpx.get(f"{BASE_URL}/event_types", headers=headers(), params={"user": user_uri, "active": "true"})
    assert r.status_code == 200
    types = r.json().get("collection", [])
    assert types, "No active event types found"
    event_type_uri = types[0]["uri"]

    r = httpx.post(
        f"{BASE_URL}/scheduling_links",
        headers={**headers(), "Content-Type": "application/json"},
        json={"max_event_count": 1, "owner": event_type_uri, "owner_type": "EventType"},
    )
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.text[:800]}")
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"

    link = r.json()["resource"]["booking_url"]
    print(f"\nScheduling link created: {link}")
    assert link.startswith("https://")


def test_create_invitee_booking():
    """
    Test programmatic booking via the Calendly Scheduling API.
    Tries the documented endpoint paths in order to find the correct one.
    REQUIRES a paid Calendly plan (Standard/Teams/Enterprise).
    """
    INVITEE_NAME = "Tester Test"
    INVITEE_EMAIL = "email@email.com"

    # Step 1: Get event type
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    assert r.status_code == 200
    user_uri = r.json()["resource"]["uri"]

    r = httpx.get(f"{BASE_URL}/event_types", headers=headers(), params={"user": user_uri, "active": "true"})
    assert r.status_code == 200
    types = r.json().get("collection", [])
    assert types, "No active event types found"
    event_type = types[0]
    event_type_uri = event_type["uri"]
    event_type_uuid = event_type_uri.split("/")[-1]
    print(f"\nEvent type: {event_type.get('name')} | UUID: {event_type_uuid}")

    # Extract location from event type (use first configured location)
    raw_locations = event_type.get("locations", [])
    print(f"\nConfigured locations on event type:")
    import json as _json
    print(_json.dumps(raw_locations, indent=2))

    booking_location = None
    if raw_locations:
        loc = raw_locations[0]
        booking_location = {
            "kind": loc.get("kind", "physical"),
            "location": loc.get("location", ""),
        }
        print(f"\nUsing location: {booking_location}")
    else:
        # Fall back to physical clinic location
        booking_location = {"kind": "physical", "location": "Acme Dental Clinic"}
        print(f"\nNo locations on event type — using default: {booking_location}")

    # Step 2: Get a real available slot
    date = next_weekday(days_ahead=5)
    r = httpx.get(
        f"{BASE_URL}/event_type_available_times",
        headers=headers(),
        params={
            "event_type": event_type_uri,
            "start_time": f"{date}T00:00:00.000000Z",
            "end_time": f"{date}T23:59:59.000000Z",
        },
    )
    assert r.status_code == 200
    slots = r.json().get("collection", [])
    assert slots, f"No available slots on {date} — try a different date"
    start_time = slots[0]["start_time"]
    print(f"\nSlot to book: {start_time}")

    # Step 3: POST /invitees with event_type URI + location from event type
    name_parts = INVITEE_NAME.split(" ", 1)
    payload = {
        "event_type": event_type_uri,
        "start_time": start_time,
        "invitee": {
            "name": INVITEE_NAME,
            "first_name": name_parts[0],
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "email": INVITEE_EMAIL,
            "timezone": "Europe/Dublin",
        },
        "location": booking_location,
        "booking_source": "ai_scheduling_assistant",
        "questions_and_answers": [
            {
                "question": "Your PIN",
                "answer": "string",
                "position": 1,
            }
        ],
    }

    print(f"\nPayload: {_json.dumps(payload, indent=2)}")

    r = httpx.post(
        f"{BASE_URL}/invitees",
        headers={**headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.text[:1000]}")

    if r.status_code == 403:
        pytest.skip("Calendly paid plan required for Scheduling API — upgrade to Standard/Teams/Enterprise.")
    if r.status_code == 402:
        pytest.skip("Calendly Scheduling API not available on this plan — upgrade required.")

    assert r.status_code in (200, 201), f"Unexpected {r.status_code}: {r.text}"
    booking = r.json()
    print(f"\nBooking created successfully!")
    print(f"Response: {booking}")


def test_get_scheduled_events():
    """Verify we can list scheduled events (for lookup/cancel flows)."""
    r = httpx.get(f"{BASE_URL}/users/me", headers=headers())
    assert r.status_code == 200
    user_uri = r.json()["resource"]["uri"]

    r = httpx.get(
        f"{BASE_URL}/scheduled_events",
        headers=headers(),
        params={"user": user_uri, "status": "active", "count": 5, "sort": "start_time:asc"},
    )
    print(f"\nStatus: {r.status_code}")
    print(f"Response: {r.text[:800]}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    events = r.json().get("collection", [])
    print(f"\nUpcoming events ({len(events)}):")
    for e in events:
        start = datetime.fromisoformat(e["start_time"].replace("Z", "+00:00"))
        print(f"  - {start.strftime('%A %d %B %Y at %I:%M %p')} | URI: {e['uri']}")

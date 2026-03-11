from datetime import datetime, timezone
from unittest.mock import patch
from backend.tools.clinic import get_clinic_info, get_services, get_current_datetime, search_faq


# ── get_clinic_info ───────────────────────────────────────────────────────────

def test_clinic_info_contains_hours():
    result = get_clinic_info.invoke({})
    assert "Mon" in result
    assert "8am" in result
    assert "Sat" in result


def test_clinic_info_correct_pricing():
    result = get_clinic_info.invoke({})
    assert "€60" in result


def test_clinic_info_student_senior_discount():
    result = get_clinic_info.invoke({})
    assert "€50" in result


def test_clinic_info_no_walk_ins():
    result = get_clinic_info.invoke({})
    assert "walk" in result.lower()


def test_clinic_info_no_emergency():
    result = get_clinic_info.invoke({})
    assert "emergency" in result.lower()


def test_clinic_info_no_deposit():
    result = get_clinic_info.invoke({})
    assert "deposit" in result.lower()


def test_clinic_info_payment_methods():
    result = get_clinic_info.invoke({})
    assert "card" in result.lower() or "cash" in result.lower()


# ── get_services ──────────────────────────────────────────────────────────────

def test_services_check_up_only():
    result = get_services.invoke({})
    assert "check-up" in result.lower() or "checkup" in result.lower()


def test_services_appointment_duration():
    result = get_services.invoke({})
    assert "30" in result


def test_services_no_whitening():
    result = get_services.invoke({})
    assert "whitening" not in result.lower() or "not" in result.lower()


def test_services_no_emergency():
    result = get_services.invoke({})
    assert "not" in result.lower()
    assert "emergency" in result.lower()


def test_services_xray_not_included():
    result = get_services.invoke({})
    assert "x-ray" in result.lower() or "xray" in result.lower()
    assert "not" in result.lower()


def test_services_oral_examination():
    result = get_services.invoke({})
    assert "oral" in result.lower() or "examination" in result.lower()


def test_services_gum_check():
    result = get_services.invoke({})
    assert "gum" in result.lower()


# ── search_faq ────────────────────────────────────────────────────────────────

def test_faq_returns_content():
    result = search_faq.invoke({"question": "What is the cancellation policy?"})
    assert len(result) > 100


def test_faq_contains_pricing():
    result = search_faq.invoke({"question": "How much does a check-up cost?"})
    assert "€60" in result


def test_faq_contains_cancellation_policy():
    result = search_faq.invoke({"question": "cancellation"})
    assert "24" in result
    assert "€20" in result


def test_faq_contains_no_show_fee():
    result = search_faq.invoke({"question": "no show"})
    assert "€20" in result


def test_faq_contains_discount_info():
    result = search_faq.invoke({"question": "discounts"})
    assert "student" in result.lower()
    assert "senior" in result.lower()


def test_faq_contains_insurance_info():
    result = search_faq.invoke({"question": "insurance"})
    assert "insurance" in result.lower()


def test_faq_contains_what_to_bring():
    result = search_faq.invoke({"question": "what should I bring"})
    assert "photo id" in result.lower() or "id" in result.lower()


def test_faq_content_is_cached():
    # Call twice — second should return identical cached content
    r1 = search_faq.invoke({"question": "pricing"})
    r2 = search_faq.invoke({"question": "pricing"})
    assert r1 == r2


# ── get_current_datetime ──────────────────────────────────────────────────────

def test_datetime_contains_utc():
    result = get_current_datetime.invoke({})
    assert "UTC" in result


def test_datetime_contains_gmt_label():
    result = get_current_datetime.invoke({})
    assert "GMT" in result


def test_datetime_contains_day_of_week():
    result = get_current_datetime.invoke({})
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert any(day in result for day in days)


def test_datetime_contains_year():
    result = get_current_datetime.invoke({})
    assert str(datetime.now(timezone.utc).year) in result


def test_datetime_correct_day_wednesday():
    fixed = datetime(2026, 3, 11, 14, 0, tzinfo=timezone.utc)  # Wednesday
    with patch("backend.tools.clinic.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.strftime = datetime.strftime
        result = get_current_datetime.invoke({})
    assert "Wednesday" in result
    assert "11" in result
    assert "2026" in result


def test_datetime_correct_day_friday():
    fixed = datetime(2026, 3, 13, 9, 30, tzinfo=timezone.utc)  # Friday
    with patch("backend.tools.clinic.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.strftime = datetime.strftime
        result = get_current_datetime.invoke({})
    assert "Friday" in result
    assert "13" in result

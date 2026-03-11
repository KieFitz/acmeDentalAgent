"""
Guardrails for the AcmeDental receptionist agent.

check_input  — called BEFORE the agent runs. Returns a rejection string if the
               message should be blocked, or None to allow it through.
check_output — called AFTER the agent responds. Sanitizes the response before
               returning it to the client.
"""

BLOCKED_TOPICS = [
    "prescription", "medication", "drug", "diagnos",
    "legal", "lawsuit", "sue", "refund", "insurance claim",
]

OFF_TOPIC_KEYWORDS = [
    "weather", "stock", "sports", "politic", "recipe",
    "movie", "music", "game", "crypto", "bitcoin",
]

DENTAL_REJECTION = (
    "I'm the Acme Dental receptionist and can only help with dental appointments "
    "and clinic questions. For medical advice or other topics, please contact the "
    "appropriate professional."
)

SENSITIVE_PATTERNS = [
    # Prevent leaking internal API keys or system details that may slip into output
    "GEMINI_API_KEY",
    "Calendly_API_Key",
    "Bearer ",
]


def check_input(message: str) -> str | None:
    """
    Validate incoming patient message.
    Returns a rejection string to send back to the user, or None to allow.
    """
    lower = message.lower()

    if any(kw in lower for kw in BLOCKED_TOPICS):
        return (
            "I'm not able to provide medical diagnoses or advice on prescriptions. "
            "Please consult your dentist directly or call the clinic at (555) 123-4567."
        )

    if any(kw in lower for kw in OFF_TOPIC_KEYWORDS):
        return DENTAL_REJECTION

    if len(message.strip()) < 2:
        return "Please enter a message so I can help you."

    return None


def check_output(response: str) -> str:
    """
    Sanitize agent output before returning to client.
    Strips any sensitive strings that should never appear in responses.
    """
    for pattern in SENSITIVE_PATTERNS:
        response = response.replace(pattern, "[REDACTED]")
    return response

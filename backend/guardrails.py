"""
Guardrails for the AcmeDental receptionist agent.

check_input  — called BEFORE the agent runs. Returns a rejection string if the
               message should be blocked, or None to allow it through.
check_output — called AFTER the agent responds. Sanitizes the response before
               returning it to the client.
"""

MAX_INPUT_LENGTH = 1000

PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore your instructions",
    "you are now",
    "act as a ",
    "system:",
    "[inst]",
    "repeat your instructions",
    "what are your instructions",
    "reveal your prompt",
    "disregard",
    "forget everything",
    "new persona",
    "pretend you are",
    "roleplay as",
    "run this command",
]

DATA_FISHING_PATTERNS = [
    "list all appointments",
    "show all emails",
    "dump the database",
    "all patients",
    "all records",
    "export data",
    "show me the database",
]

BLOCKED_TOPICS_MEDICAL = [
    "prescription", "medication", "drug", "diagnos",
    "legal",
]

BLOCKED_TOPICS_LEGAL = [
    "sue", "lawsuit", "legal trouble", "attorney", "lawyer", "court",
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
    "GEMINI_API_KEY",
    "Calendly_API_Key",
    "Bearer ",
]


def check_input(message: str) -> str | None:
    """
    Validate incoming patient message.
    Returns a rejection string to send back to the user, or None to allow.
    Checks run in fail-fast order (cheapest first).
    """
    # 1. Length limit
    if len(message) > MAX_INPUT_LENGTH:
        return "Sorry, your message is too long. Please keep it under 1,000 characters."

    # 2. Empty / too short
    if len(message.strip()) < 2:
        return "Sorry, your message is too short. Please enter more details so I can help you."

    lower = message.lower()

    # 3. Prompt injection
    if any(pattern in lower for pattern in PROMPT_INJECTION_PATTERNS):
        return (
            "Sorry, I'm not able to process that request. I can only help with booking or ammending check-up appointments and clinic queries you might have. "
            "I'm Aria, the Acme Dental receptionist — here to help with appointments and clinic queries."
        )

    # 4. Data fishing
    if any(pattern in lower for pattern in DATA_FISHING_PATTERNS):
        return (
            "I'm not able to access or share patient records. "
            "Please call the clinic directly at (087) 123-4567 for administrative queries."
        )

    # 5. Blocked medical topics
    if any(kw in lower for kw in BLOCKED_TOPICS_MEDICAL):
        return (
            "I'm not able to provide medical diagnoses or advice on prescriptions. "
            "Please consult your dentist directly or call the clinic at (087) 123-4567."
        )
    # 5.1 Blocked legal topics
    if any(kw in lower for kw in BLOCKED_TOPICS_LEGAL):
        return (
            "I'm sorry to hear you have a legal concern. "
            "I am not able to provide legal advice or process legal matters directly. "
            "Please contact us at (087) 123-4567 to speak with a representative who can assist you further. "
        )


    # 6. Off-topic
    if any(kw in lower for kw in OFF_TOPIC_KEYWORDS):
        return DENTAL_REJECTION

    return None


def check_output(response: str) -> str:
    """
    Sanitize agent output before returning to client.
    Strips any sensitive strings that should never appear in responses.
    """
    for pattern in SENSITIVE_PATTERNS:
        response = response.replace(pattern, "[REDACTED]")
    return response

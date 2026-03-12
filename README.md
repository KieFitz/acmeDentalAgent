# Acme Dental Agent — Aria

AI-powered receptionist chatbot for Acme Dental clinic. Aria handles appointment bookings,
cancellations, FAQs, and clinic queries via a chat interface backed by a LangGraph + FastAPI
agent and the Calendly API.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.0 Flash (via `langchain-google-genai`) |
| Agent | LangGraph `create_react_agent` with `MemorySaver` |
| API | FastAPI + Uvicorn |
| Appointments | Calendly API (v2) |
| Database | SQLite (SQLAlchemy) — persisted via Docker volume |
| Email | SMTP (Gmail/Outlook) via `aiosmtplib` |
| Security | bcrypt PIN hashing, 3-attempt lockout |
| Containerisation | Docker + Docker Compose |
| Package manager | uv |
| Testing | pytest |

---

## Project Structure

```
backend/
  agent.py               # LLM + LangGraph agent assembly
  guardrails.py          # Input/output validation (injection, length, topic)
  main.py                # FastAPI app + CORS + lifespan
  KNOWLEDGE_BASE.md      # Clinic FAQ loaded by search_faq tool
  db/
    database.py          # SQLAlchemy engine + session + init_db()
    models.py            # AppointmentPin, ConversationMessage, SessionBooking, SessionNote
  routes/
    chat.py              # POST /chat — main endpoint + conversation log endpoints
  services/
    email_service.py     # Async SMTP confirmation emails
    pin_service.py       # PIN generation, hashing, verification, lockout
  tools/
    __init__.py          # Exports all_tools
    calendly.py          # Booking, lookup, cancel, available slots (Calendly API)
    clinic.py            # Clinic info, services, FAQ search, datetime tool
frontend/
  index.html             # Single-file chat UI (HTML/CSS/JS)
  nginx.conf             # Nginx — serves frontend, proxies /chat/ to backend
tests/
  tools/
    test_clinic.py       # 26 tests for clinic tools
    test_calendly.py     # Slot filtering, booking validation tests
  services/
    test_pin_service.py  # PIN generation, verification, lockout tests
Dockerfile               # Backend image (uv + Python 3.13)
docker-compose.yml       # backend + nginx frontend + SQLite volume
```

---

## Getting Started

### Prerequisites
- Docker Desktop
- A Google Gemini API key (free tier: 1,500 req/day for gemini-2.0-flash)
- A Calendly account with a PAT token
- An email account with an App Password (for SMTP)

### 1. Configure environment
Copy `.env.example` to `.env` and fill in your keys:
```env
GEMINI_API_KEY=your_gemini_api_key
Calendly_API_Key=your_calendly_pat_token

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=you@gmail.com
```

### 2. Run with Docker
```bash
docker compose up --build
```

Open **http://localhost:3000** in your browser.

### 3. Run locally (development)
```bash
uv run uvicorn backend.main:app --reload
```
Open **frontend/index.html** directly in your browser.

---

## How It Works

### Booking flow
1. Patient asks for available slots → agent calls `get_available_slots(date)` → real Calendly API
2. Patient selects a slot → agent calls `book_appointment(name, email, slot)` → creates local record + bcrypt PIN
3. Confirmation email sent with appointment details, 6-digit security PIN, and appointment reference
4. PIN is never shown in chat — only delivered via email

### Cancel / Lookup flow
1. Patient provides name + PIN → agent calls `lookup_appointment` or `cancel_appointment`
2. PIN verified against bcrypt hash in DB (3-attempt lockout on failure)
3. Cancellation forwarded to Calendly API using the patient's email to find the active event
4. Works from any session — no session memory required

### Guardrails (pre-agent)
- Input length limit (1,000 chars)
- Prompt injection detection
- Data fishing detection
- Off-topic and sensitive medical topic blocking
- Max 3 bookings per session, unique patient names per session (this is to allow bookings for family members if convinient to book for kids at the same time.)

### Conversation logging
Every message pair is stored in `ConversationMessage` with a `session_id`.
View logs via:
```
GET /chat/conversations
GET /chat/conversations/{session_id}
```

---

## Running Tests
```bash
uv run pytest tests/ -v
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/chat/` | Send a message to Aria |
| GET | `/health` | Health check |
| GET | `/chat/conversations` | List all conversation sessions |
| GET | `/chat/conversations/{id}` | Full transcript for a session |

---

## TODO

### High priority
- [x] **Refine prompts** — review conversation logs to identify where Aria gives robotic or unclear responses; improve the system prompt and tool docstrings accordingly
- [x] **Confirm live bookings with Calendly** — wire up `book_appointment` to create a real Calendly event via the scheduling links API or a Calendly webhook flow; currently bookings are recorded locally only
- [x] **Test fraud prevention end-to-end** — manually test PIN lockout, wrong-name rejection, and 3-booking-per-session limit with live data; verify bcrypt timing is acceptable
- [X] **Agent to ammend bookings if session same** - Agent should be able to ammend or cancel bookings if the session is still the same, without requirment for PIN. PIN should only be for if there is a new session.
- [ ] **Make Sure AI doesn't invent opening hours**

### Medium priority
- [ ] **Edge case hunting** — test corner cases: same patient name different email, booking on a Saturday[failed], cancelling an already-cancelled appointment, lookup when Calendly API is down, rescheduling for same time and day.
- [X] **Wire up Calendly available slots** — confirm `get_available_slots` is returning real times from `GET /event_type_available_times` for the correct event type
- [X] **Reschedule flow** — implement `reschedule_appointment(patient_name, pin, new_slot)` tool; currently only cancel is supported. reschedule not supported in API from Calendly.

### Lower priority
- [ ] **Persistent MemorySaver** — replace in-memory `MemorySaver` with `langgraph-checkpoint-sqlite` so conversation context survives container restarts
- [ ] **Rate limiting** — add per-IP or per-session message rate limiting to prevent API abuse
- [X] **Admin dashboard** — simple UI to browse conversation logs and flag sessions for review
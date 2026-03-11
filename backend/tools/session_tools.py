from datetime import datetime, timezone
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from backend.db.database import SessionLocal
from backend.db.models import SessionNote


@tool
def write_session_note(content: str, config: RunnableConfig) -> str:
    """
    Write or update the running summary note for this session.
    Use this to remember important context across turns: patient names, email
    addresses, appointments already booked, and any stated preferences.
    The note replaces any previous note — always write the full updated summary.
    Args:
        content: The complete session summary to store.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    db = SessionLocal()
    try:
        existing = (
            db.query(SessionNote)
            .filter(SessionNote.session_id == session_id)
            .first()
        )
        if existing:
            existing.content = content
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(SessionNote(
                session_id=session_id,
                content=content,
                updated_at=datetime.now(timezone.utc),
            ))
        db.commit()
        return "Session note saved."
    except Exception as e:
        db.rollback()
        return f"Failed to save note: {e}"
    finally:
        db.close()


@tool
def read_session_note(config: RunnableConfig) -> str:
    """
    Read the current session summary note.
    Call this at the start of each turn to recall patient context from earlier
    in this conversation (names, emails, bookings made, preferences).
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    db = SessionLocal()
    try:
        note = (
            db.query(SessionNote)
            .filter(SessionNote.session_id == session_id)
            .first()
        )
        if note:
            return f"Session context:\n{note.content}"
        return "No session notes yet."
    finally:
        db.close()


session_tools = [read_session_note, write_session_note]

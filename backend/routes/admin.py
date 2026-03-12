from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func
from backend.db.database import SessionLocal
from backend.db.models import ConversationMessage, ConversationReview

router = APIRouter(prefix="/admin-api")


class ReviewUpdate(BaseModel):
    status: str   # "safe" | "risky" | "dangerous" | "unreviewed"
    notes: str = ""


@router.get("/conversations")
def list_conversations():
    """Return all sessions with message count, timestamps and review status."""
    db = SessionLocal()
    try:
        rows = (
            db.query(
                ConversationMessage.session_id,
                func.count(ConversationMessage.id).label("message_count"),
                func.min(ConversationMessage.created_at).label("started_at"),
                func.max(ConversationMessage.created_at).label("last_at"),
            )
            .group_by(ConversationMessage.session_id)
            .order_by(func.max(ConversationMessage.created_at).desc())
            .all()
        )

        # Fetch all review records
        review_map = {
            r.session_id: r
            for r in db.query(ConversationReview).all()
        }

        result = []
        for row in rows:
            # Grab the first human message as a preview
            first_msg = (
                db.query(ConversationMessage)
                .filter(
                    ConversationMessage.session_id == row.session_id,
                    ConversationMessage.role == "human",
                )
                .order_by(ConversationMessage.created_at)
                .first()
            )
            review = review_map.get(row.session_id)
            result.append({
                "session_id": row.session_id,
                "message_count": row.message_count,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "last_at": row.last_at.isoformat() if row.last_at else None,
                "preview": (first_msg.content[:120] + "…") if first_msg and len(first_msg.content) > 120 else (first_msg.content if first_msg else ""),
                "status": review.status if review else "unreviewed",
                "notes": review.notes if review else "",
            })
        return result
    finally:
        db.close()


@router.get("/conversations/{session_id}")
def get_conversation(session_id: str):
    """Return full message transcript for a session."""
    db = SessionLocal()
    try:
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
            .all()
        )
        review = db.query(ConversationReview).filter(
            ConversationReview.session_id == session_id
        ).first()

        return {
            "session_id": session_id,
            "status": review.status if review else "unreviewed",
            "notes": review.notes if review else "",
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
    finally:
        db.close()


@router.post("/conversations/{session_id}/review")
def review_conversation(session_id: str, body: ReviewUpdate):
    """Set the review status and optional notes for a session."""
    valid = {"unreviewed", "safe", "risky", "dangerous"}
    if body.status not in valid:
        return {"error": f"status must be one of {valid}"}

    db = SessionLocal()
    try:
        review = db.query(ConversationReview).filter(
            ConversationReview.session_id == session_id
        ).first()
        if review:
            review.status = body.status
            review.notes = body.notes
            review.reviewed_at = datetime.now(timezone.utc)
        else:
            review = ConversationReview(
                session_id=session_id,
                status=body.status,
                notes=body.notes,
                reviewed_at=datetime.now(timezone.utc),
            )
            db.add(review)
        db.commit()
        return {"ok": True, "status": body.status}
    finally:
        db.close()

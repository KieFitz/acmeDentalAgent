import logging
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from backend.agent import agent_executor
from backend.guardrails import check_input, check_output
from backend.db.database import SessionLocal
from backend.db.models import ConversationMessage

# Conversation browsing is handled by /admin-api — see backend/routes/admin.py

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    # chat_history removed — LangGraph MemorySaver manages conversation state per thread


class ChatResponse(BaseModel):
    response: str


def _log_messages(session_id: str, human: str, assistant: str) -> None:
    db = SessionLocal()
    try:
        db.add(ConversationMessage(session_id=session_id, role="human", content=human))
        db.add(ConversationMessage(session_id=session_id, role="assistant", content=assistant))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    rejection = check_input(request.message)
    if rejection:
        _log_messages(request.session_id, request.message, rejection)
        return ChatResponse(response=rejection)

    try:
        config = {"configurable": {"thread_id": request.session_id}}

        result = await agent_executor.ainvoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
        )

        raw = result["messages"][-1].content
        # Gemini returns a list of content blocks when tools are used
        if isinstance(raw, list):
            text = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw
            )
        else:
            text = raw

        response = check_output(text)
        _log_messages(request.session_id, request.message, response)
        return ChatResponse(response=response)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



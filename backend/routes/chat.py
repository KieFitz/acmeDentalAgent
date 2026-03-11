import logging
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from backend.agent import agent_executor
from backend.guardrails import check_input, check_output

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    chat_history: list[dict] = []


class ChatResponse(BaseModel):
    response: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    rejection = check_input(request.message)
    if rejection:
        return ChatResponse(response=rejection)

    try:
        messages = []
        for msg in request.chat_history:
            if msg.get("role") == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=request.message))

        result = await agent_executor.ainvoke({"messages": messages})
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
        return ChatResponse(response=response)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

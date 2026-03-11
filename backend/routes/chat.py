from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.agent import agent_executor

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    chat_history: list[dict] = []


class ChatResponse(BaseModel):
    response: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await agent_executor.ainvoke({
            "input": request.message,
            "chat_history": request.chat_history,
        })
        return ChatResponse(response=result["output"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.agent import agent_executor
from backend.guardrails import check_input, check_output

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
        result = await agent_executor.ainvoke({
            "input": request.message,
            "chat_history": request.chat_history,
        })
        response = check_output(result["output"])
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
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
        messages = []
        for msg in request.chat_history:
            if msg.get("role") == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=request.message))

        result = await agent_executor.ainvoke({"messages": messages})
        response = check_output(result["messages"][-1].content)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

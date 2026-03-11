from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.chat import router as chat_router

app = FastAPI(title="AcmeDental Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}

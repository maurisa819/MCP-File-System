from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import chat

app = FastAPI(title="LG-Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    threadId: str = "default"
    message: str


class ChatResponse(BaseModel):
    reply: str
    pendingAction: bool


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    result = await chat(req.threadId, req.message)
    return result

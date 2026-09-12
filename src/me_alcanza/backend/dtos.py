from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ChatRequest(BaseModel):
    mensaje: str


class ChatResponse(BaseModel):
    a2ui_messages: list[dict]


class ConfirmActionRequest(BaseModel):
    proposal_id: str


class ConfirmActionResponse(BaseModel):
    a2ui_messages: list[dict]

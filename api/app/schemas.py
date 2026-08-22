from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    idea: str = ""
    project_name: str = "Untitled App"
    audience: str = "General users"


class AnswersRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class MessageRequest(BaseModel):
    message: str

# schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Command(BaseModel):
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)

class Citation(BaseModel):
    doc_id: str
    page: int

class ModelResponse(BaseModel):
    answer: str
    commands: List[Command] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


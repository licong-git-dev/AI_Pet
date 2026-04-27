"""
PetPal · Wrapped 月报 Pydantic Schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WrappedQuery(BaseModel):
    year: Optional[int] = Field(None, ge=2024, le=2100)
    month: Optional[int] = Field(None, ge=1, le=12)
    pet_avatar_id: Optional[int] = None


class WrappedCard(BaseModel):
    kind: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    intro: Optional[str] = None
    metrics: Optional[List[Dict[str, Any]]] = None
    memories: Optional[List[Dict[str, Any]]] = None
    digests: Optional[List[Dict[str, Any]]] = None
    distribution: Optional[Dict[str, Any]] = None
    dominant_emotion: Optional[str] = None
    pet_name: Optional[str] = None
    footnote: Optional[str] = None
    index: Optional[int] = None
    tone: Optional[str] = None


class WrappedResponse(BaseModel):
    year: int
    month: int
    user_id: int
    pet_avatar_id: Optional[int] = None
    pet_name: str
    stats: Dict[str, Any]
    top_memories: List[Dict[str, Any]]
    creative: Dict[str, Any]
    cards: List[WrappedCard]
    generated_at: str

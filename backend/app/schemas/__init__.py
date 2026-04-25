"""
PetPal - Schema模块初始化
"""
from app.schemas.auth import SendCodeRequest, LoginRequest, LoginResponse, RegisterRequest
from app.schemas.user import UserProfile, UpdateProfileRequest
from app.schemas.pet import CreatePetRequest, UpdatePetRequest, PetResponse
from app.schemas.content import CreatePostRequest, UpdatePostRequest, CreateCommentRequest, PostResponse
from app.schemas.health import (
    HealthAnalysisRequest, HealthAnalysisResponse,
    ConsultationRequest, ConsultationMessageRequest,
    CreateHealthRecordRequest
)

__all__ = [
    "SendCodeRequest", "LoginRequest", "LoginResponse", "RegisterRequest",
    "UserProfile", "UpdateProfileRequest",
    "CreatePetRequest", "UpdatePetRequest", "PetResponse",
    "CreatePostRequest", "UpdatePostRequest", "CreateCommentRequest", "PostResponse",
    "HealthAnalysisRequest", "HealthAnalysisResponse",
    "ConsultationRequest", "ConsultationMessageRequest", "CreateHealthRecordRequest"
]

"""
PetPal - 数据模型初始化
"""
from app.models.user import User
from app.models.pet import Pet, PetBreed, PetPhoto, VaccinationRecord, WeightRecord
from app.models.content import Post, Comment, Like, Topic, TopicFollow, Collection, CollectionFolder, Share
from app.models.health import HealthRecord, HealthConsultation, ConsultationMessage
from app.models.diagnosis import HealthDiagnosis, DiagnosisConversation
from app.models.shop import (
    Product, ProductCategory, Order, OrderItem,
    Coupon, UserCoupon, ProductReview, ProductFavorite, RefundRequest
)
from app.models.social import Follow, Message, Activity, ActivityParticipant, Notification, Conversation
from app.models.points import PointsRecord, PointsProduct, PointsRechargeOrder
from app.models.membership import MembershipOrder
from app.models.login_log import LoginLog
from app.models.audit_log import AuditLog, AuditAction, AuditResource
from app.models.user_settings import UserSettings, UserBlacklist, UserAddress, UserFeedback, UserReport
from app.models.avatar import PetAvatar, PetAvatarChat, PetAvatarMessage, PetSticker, PersonalityProfile

__all__ = [
    "User",
    "Pet", "PetBreed", "PetPhoto", "VaccinationRecord", "WeightRecord",
    "Post", "Comment", "Like", "Topic", "TopicFollow", "Collection", "CollectionFolder", "Share",
    "HealthRecord", "HealthConsultation", "ConsultationMessage",
    "HealthDiagnosis", "DiagnosisConversation",
    "Product", "ProductCategory", "Order", "OrderItem",
    "Coupon", "UserCoupon", "ProductReview", "ProductFavorite", "RefundRequest",
    "Follow", "Message", "Activity", "ActivityParticipant", "Notification", "Conversation",
    "PointsRecord", "PointsProduct", "PointsRechargeOrder", "MembershipOrder",
    "LoginLog",
    "AuditLog", "AuditAction", "AuditResource",
    "UserSettings", "UserBlacklist", "UserAddress", "UserFeedback", "UserReport",
    "PetAvatar", "PetAvatarChat", "PetAvatarMessage", "PetSticker", "PersonalityProfile",
]

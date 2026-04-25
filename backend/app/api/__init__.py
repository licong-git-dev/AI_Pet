"""
PetPal - API路由初始化
"""
from fastapi import APIRouter
from app.api import auth, users, pets, posts, health, shop, points, diagnosis, upload, messages, activities, payments, search, pet_avatar, membership
from app.api.admin import admin_router

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(pets.router, prefix="/pets", tags=["宠物"])
api_router.include_router(posts.router, prefix="/posts", tags=["内容"])
api_router.include_router(health.router, prefix="/health", tags=["健康"])
api_router.include_router(diagnosis.router, prefix="/diagnosis", tags=["AI诊断"])
api_router.include_router(shop.router, prefix="/shop", tags=["商城"])
api_router.include_router(points.router, prefix="/points", tags=["积分"])
api_router.include_router(membership.router, prefix="/membership", tags=["会员"])
api_router.include_router(upload.router, prefix="/upload", tags=["文件上传"])
api_router.include_router(messages.router, prefix="/messages", tags=["消息通知"])
api_router.include_router(activities.router, prefix="/activities", tags=["线下活动"])
api_router.include_router(payments.router, prefix="/payments", tags=["支付"])
api_router.include_router(search.router, prefix="/search", tags=["搜索"])
api_router.include_router(pet_avatar.router, prefix="/pet-avatar", tags=["宠物数字分身"])

# 注册管理后台路由
api_router.include_router(admin_router, prefix="/admin", tags=["管理后台"])

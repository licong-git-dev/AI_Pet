"""
PetPal - 管理后台API

提供管理员功能：
- 用户管理
- 内容审核
- 数据统计
- 系统配置
"""
from fastapi import APIRouter
from app.api.admin import users, content, statistics

admin_router = APIRouter()

# 注册管理后台路由
admin_router.include_router(users.router, prefix="/users", tags=["管理-用户"])
admin_router.include_router(content.router, prefix="/content", tags=["管理-内容"])
admin_router.include_router(statistics.router, prefix="/statistics", tags=["管理-统计"])

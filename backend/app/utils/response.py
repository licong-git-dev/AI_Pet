"""
PetPal - 通用响应模型
"""
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PageInfo(BaseModel):
    """分页信息"""
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class PageResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[list] = None
    page_info: Optional[PageInfo] = None


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return {
        "code": 0,
        "message": message,
        "data": data
    }


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    """错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data
    }


def page_response(data: list, page: int, page_size: int, total: int) -> dict:
    """分页响应"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }

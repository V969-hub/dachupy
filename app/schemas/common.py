from typing import TypeVar, Generic, Optional, List, Any
from pydantic import BaseModel

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """
    Standardized API response format.
    All API responses should use this format for consistency.
    """
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": {}
            }
        }


class PageInfo(BaseModel):
    """Pagination information."""
    page: int
    page_size: int
    total: int
    total_pages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "page": 1,
                "page_size": 10,
                "total": 100,
                "total_pages": 10
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standardized paginated API response format.
    Used for list endpoints that support pagination.
    """
    code: int = 200
    message: str = "success"
    data: Optional[List[T]] = None
    page_info: Optional[PageInfo] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": [],
                "page_info": {
                    "page": 1,
                    "page_size": 10,
                    "total": 100,
                    "total_pages": 10
                }
            }
        }


def success_response(data: Any = None, message: str = "success") -> dict:
    """Helper function to create a success response."""
    return {
        "code": 200,
        "message": message,
        "data": data
    }


def error_response(code: int, message: str, data: Any = None) -> dict:
    """Helper function to create an error response."""
    return {
        "code": code,
        "message": message,
        "data": data
    }


def paginated_response(
    data: List[Any],
    page: int,
    page_size: int,
    total: int,
    message: str = "success"
) -> dict:
    """Helper function to create a paginated response."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "code": 200,
        "message": message,
        "data": data,
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }

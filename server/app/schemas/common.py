"""Generic response wrappers shared by all API endpoints."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API success response envelope."""

    code: int = 0
    message: str = "success"
    data: T


class PaginatedData(BaseModel, Generic[T]):
    """Paginated list payload."""

    items: list[T]
    total: int
    page: int
    page_size: int


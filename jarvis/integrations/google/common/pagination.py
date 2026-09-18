"""Pagination models and bounding utilities for Google list requests."""
from __future__ import annotations

from typing import Generic, List, Optional, Tuple, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


class PaginationParams(BaseModel):
    """Standardized pagination parameters for Google list operations."""
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    page_token: Optional[str] = None


class PaginatedResult(BaseModel, Generic[T]):
    """Standardized envelope for paginated Google API responses."""
    model_config = ConfigDict(extra="forbid")

    items: Tuple[T, ...] = Field(default_factory=tuple)
    next_page_token: Optional[str] = None
    total_estimate: Optional[int] = None

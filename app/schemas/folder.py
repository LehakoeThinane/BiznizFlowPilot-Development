"""Folder request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_folder_id: Optional[UUID] = None


class FolderRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    parent_folder_id: Optional[UUID] = None
    name: str
    created_by: Optional[UUID] = None
    created_at: datetime


class FolderListResponse(BaseModel):
    items: list[FolderResponse]

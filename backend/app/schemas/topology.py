"""Pydantic v2 schemas for TopologyNode, TopologyLink, and graph responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NodeBase(BaseModel):
    node_id: str = Field(..., max_length=255)
    device_id: Optional[uuid.UUID] = None
    role: Optional[str] = Field(None, max_length=50)
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    meta: Optional[dict] = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    role: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    meta: Optional[dict] = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class NodeRead(NodeBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LinkBase(BaseModel):
    source_node_id: str = Field(..., max_length=255)
    target_node_id: str = Field(..., max_length=255)
    source_interface: Optional[str] = Field(None, max_length=100)
    target_interface: Optional[str] = Field(None, max_length=100)
    discovery_method: Optional[str] = Field(None, max_length=20)


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    discovery_method: Optional[str] = None


class LinkRead(LinkBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class GraphResponse(BaseModel):
    nodes: List[NodeRead]
    links: List[LinkRead]

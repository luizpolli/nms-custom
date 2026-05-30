"""Pydantic v2 schemas for TopologyNode, TopologyLink, and graph responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NodeBase(BaseModel):
    node_id: str = Field(..., max_length=255)
    device_id: uuid.UUID | None = None
    role: str | None = Field(None, max_length=50)
    position_x: float | None = None
    position_y: float | None = None
    meta: dict | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    role: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    meta: dict | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class NodeRead(NodeBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LinkBase(BaseModel):
    source_node_id: str = Field(..., max_length=255)
    target_node_id: str = Field(..., max_length=255)
    source_interface: str | None = Field(None, max_length=100)
    target_interface: str | None = Field(None, max_length=100)
    discovery_method: str | None = Field(None, max_length=20)


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    source_interface: str | None = None
    target_interface: str | None = None
    discovery_method: str | None = None


class LinkRead(LinkBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class GraphResponse(BaseModel):
    nodes: list[NodeRead]
    links: list[LinkRead]

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


Route = Literal["POLICY_ONLY", "EXTERNAL_REQUIRED", "MIXED"]


class RouteDecision(BaseModel):
    route: Route
    reason: str = Field(description="Short routing reason; no coverage conclusion.")

class AskRequest(BaseModel):
    question: str


class SourceCitation(BaseModel):
    source_id: str
    source: str
    page: int
    section: str
    clause: str


class WebSource(BaseModel):
    title: str = ""
    url: str


class AskResponse(BaseModel):
    route: Route
    answer: str
    policy_sources: list[SourceCitation]
    web_sources: list[WebSource] = []
    needs_more_information: bool = False


class WorkflowState(TypedDict, total=False):
    question: str
    route: Route
    route_reason: str
    policy_context: list[dict]
    answer: str
    policy_sources: list[dict]
    web_sources: list[dict]
    needs_more_information: bool

from enum import Enum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowAction(Enum):
    gmail_search = "gmail.search"
    gmail_get_message = "gmail.getMessage"
    gmail_create_draft = "gmail.createDraft"
    gmail_send = "gmail.send"
    gmail_add_label = "gmail.addLabel"
    gmail_archive = "gmail.archive"
    llm_classify = "llm.classify"
    llm_extract = "llm.extract"
    llm_summarize = "llm.summarize"
    llm_compose = "llm.compose"
    platform_approval = "platform.approval"


class WorkflowGenerateRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=4000)


class WorkflowNode(BaseModel):
    id: str = Field(min_length=1)
    action: WorkflowAction
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)
    condition: str | None = None


_MAX_NODES = 30


def _ensure_acyclic(nodes: list[WorkflowNode], edges: list[WorkflowEdge]) -> None:
    adjacency: dict[str, list[str]] = {node.id: [] for node in nodes}
    for edge in edges:
        adjacency[edge.from_].append(edge.to)

    visited: set[str] = set()
    in_progress: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in in_progress:
            raise ValueError("workflow graph contains a cycle")
        if node_id in visited:
            return

        in_progress.add(node_id)
        for next_node_id in adjacency[node_id]:
            visit(next_node_id)
        in_progress.remove(node_id)
        visited.add(node_id)

    for node in nodes:
        visit(node.id)


class Workflow(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        if not self.nodes:
            raise ValueError("workflow has no nodes")
        if len(self.nodes) > _MAX_NODES:
            raise ValueError(f"workflow exceeds {_MAX_NODES} nodes")

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("workflow contains duplicate node ids")

        known_node_ids = set(node_ids)
        for edge in self.edges:
            if edge.from_ not in known_node_ids:
                raise ValueError(f"edge source does not exist: {edge.from_}")
            if edge.to not in known_node_ids:
                raise ValueError(f"edge target does not exist: {edge.to}")

        _ensure_acyclic(self.nodes, self.edges)
        return self


class WorkflowGenerationResult(BaseModel):
    message: str = Field(min_length=1)
    workflow: Workflow


class WorkflowMessageDeltaEvent(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    delta: str


class WorkflowToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class WorkflowToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    output: Any


class WorkflowResultEvent(BaseModel):
    type: Literal["result"] = "result"
    result: WorkflowGenerationResult


class WorkflowErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: Literal["generation_error", "provider_error"]
    message: str


type WorkflowStreamEvent = Annotated[
    WorkflowMessageDeltaEvent
    | WorkflowToolCallEvent
    | WorkflowToolResultEvent
    | WorkflowResultEvent
    | WorkflowErrorEvent,
    Field(discriminator="type"),
]

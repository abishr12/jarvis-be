import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.workflows import get_generator
from app.main import create_app
from app.models.workflow import (
    WorkflowGenerationResult,
    WorkflowMessageDeltaEvent,
    WorkflowResultEvent,
    WorkflowStreamEvent,
    WorkflowToolCallEvent,
    WorkflowToolResultEvent,
)
from app.services.workflow_generator import (
    WorkflowGenerationError,
    WorkflowProviderError,
)


class StubGenerator:
    def __init__(
        self,
        events: list[WorkflowStreamEvent] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.events = events or []
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def stream(
        self,
        prompt: str,
        thread_id: str,
    ) -> AsyncIterator[WorkflowStreamEvent]:
        self.calls.append((prompt, thread_id))

        if self.error is not None:
            raise self.error

        for event in self.events:
            yield event


def _result() -> WorkflowGenerationResult:
    return WorkflowGenerationResult.model_validate(
        {
            "message": "I will summarize your unread job emails.",
            "workflow": {
                "id": "summarize-job-emails",
                "name": "Summarize Job Emails",
                "nodes": [
                    {
                        "id": "search-emails",
                        "action": "gmail.search",
                        "config": {"query": "is:unread label:jobs"},
                    },
                    {
                        "id": "summarize-emails",
                        "action": "llm.summarize",
                        "config": {},
                    },
                ],
                "edges": [{"from": "search-emails", "to": "summarize-emails"}],
            },
        }
    )


def _client_with(generator: StubGenerator) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_generator] = lambda: generator
    return TestClient(app)


def test_stream_workflow_returns_ndjson_events() -> None:
    generator = StubGenerator(
        events=[
            WorkflowMessageDeltaEvent(delta="I will summarize your emails."),
            WorkflowToolCallEvent(
                tool_call_id="call-1",
                name="gmail.search",
                arguments={"query": "is:unread label:jobs"},
            ),
            WorkflowToolResultEvent(
                tool_call_id="call-1",
                name="gmail.search",
                output={"messageIds": ["message-1"]},
            ),
            WorkflowResultEvent(result=_result()),
        ]
    )
    client = _client_with(generator)

    response = client.post(
        "/workflows/generate/stream",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my unread job emails.",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"

    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == [
        "message_delta",
        "tool_call",
        "tool_result",
        "result",
    ]
    assert events[0]["delta"] == "I will summarize your emails."
    assert events[1]["arguments"] == {"query": "is:unread label:jobs"}
    assert events[2]["output"] == {"messageIds": ["message-1"]}
    assert events[3]["result"]["workflow"]["edges"] == [
        {
            "from": "search-emails",
            "to": "summarize-emails",
            "condition": None,
        }
    ]
    assert generator.calls == [
        ("Summarize my unread job emails.", "test-thread"),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"prompt": "Summarize my emails."},
        {"thread_id": "test-thread", "prompt": ""},
    ],
)
def test_stream_workflow_rejects_invalid_requests(body: dict[str, str]) -> None:
    client = _client_with(StubGenerator())

    response = client.post("/workflows/generate/stream", json=body)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            WorkflowGenerationError("invalid output"),
            "generation_error",
            "Could not generate a valid workflow.",
        ),
        (
            WorkflowProviderError("rate limited"),
            "provider_error",
            "Workflow generation provider failed.",
        ),
    ],
)
def test_stream_workflow_returns_agent_errors_as_events(
    error: Exception,
    code: str,
    message: str,
) -> None:
    client = _client_with(StubGenerator(error=error))

    response = client.post(
        "/workflows/generate/stream",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my emails.",
        },
    )

    assert response.status_code == 200
    assert [json.loads(line) for line in response.text.splitlines()] == [
        {
            "type": "error",
            "code": code,
            "message": message,
        }
    ]


def test_stream_workflow_returns_service_unavailable_when_unconfigured() -> None:
    app = create_app()
    app.state.workflow_generator = None
    client = TestClient(app)

    response = client.post(
        "/workflows/generate/stream",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my emails.",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Workflow generation is not configured."}

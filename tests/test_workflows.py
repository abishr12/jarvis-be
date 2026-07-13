import pytest
from fastapi.testclient import TestClient

from app.api.workflows import get_generator
from app.main import create_app
from app.models.workflow import WorkflowGenerationResult
from app.services.workflow_generator import (
    WorkflowGenerationError,
    WorkflowProviderError,
)


class StubGenerator:
    def __init__(
        self,
        result: WorkflowGenerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def generate(self, prompt: str, thread_id: str) -> WorkflowGenerationResult:
        self.calls.append((prompt, thread_id))

        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


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


def test_generate_workflow_returns_result() -> None:
    generator = StubGenerator(result=_result())
    client = _client_with(generator)

    response = client.post(
        "/workflows/generate",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my unread job emails.",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "I will summarize your unread job emails."
    assert response.json()["workflow"]["edges"] == [
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
def test_generate_workflow_rejects_invalid_requests(body: dict[str, str]) -> None:
    client = _client_with(StubGenerator(result=_result()))

    response = client.post("/workflows/generate", json=body)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (
            WorkflowGenerationError("invalid output"),
            "Could not generate a valid workflow.",
        ),
        (
            WorkflowProviderError("rate limited"),
            "Workflow generation provider failed.",
        ),
    ],
)
def test_generate_workflow_maps_agent_errors_to_bad_gateway(
    error: Exception,
    detail: str,
) -> None:
    client = _client_with(StubGenerator(error=error))

    response = client.post(
        "/workflows/generate",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my emails.",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": detail}


def test_generate_workflow_returns_service_unavailable_when_unconfigured() -> None:
    app = create_app()
    app.state.workflow_generator = None
    client = TestClient(app)

    response = client.post(
        "/workflows/generate",
        json={
            "thread_id": "test-thread",
            "prompt": "Summarize my emails.",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Workflow generation is not configured."}

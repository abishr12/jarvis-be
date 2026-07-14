from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.models.workflow import (
    WorkflowErrorEvent,
    WorkflowGenerateRequest,
)
from app.services.workflow_generator import (
    WorkflowGenerationError,
    WorkflowGenerator,
    WorkflowProviderError,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_generator(request: Request) -> WorkflowGenerator:
    generator: WorkflowGenerator | None = getattr(
        request.app.state,
        "workflow_generator",
        None,
    )
    if generator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow generation is not configured.",
        )
    return generator


@router.post("/generate/stream", response_class=StreamingResponse)
async def stream_workflow(
    body: WorkflowGenerateRequest,
    generator: Annotated[WorkflowGenerator, Depends(get_generator)],
) -> StreamingResponse:
    async def content() -> AsyncIterator[str]:
        try:
            async for event in generator.stream(body.prompt, body.thread_id):
                yield event.model_dump_json(by_alias=True) + "\n"
        except WorkflowGenerationError:
            error = WorkflowErrorEvent(
                code="generation_error",
                message="Could not generate a valid workflow.",
            )
            yield error.model_dump_json() + "\n"
        except WorkflowProviderError:
            error = WorkflowErrorEvent(
                code="provider_error",
                message="Workflow generation provider failed.",
            )
            yield error.model_dump_json() + "\n"

    return StreamingResponse(
        content(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

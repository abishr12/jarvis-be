from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.models.workflow import WorkflowGenerateRequest, WorkflowGenerationResult
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


@router.post("/generate", response_model=WorkflowGenerationResult)
async def generate_workflow(
    body: WorkflowGenerateRequest,
    generator: Annotated[WorkflowGenerator, Depends(get_generator)],
) -> WorkflowGenerationResult:
    try:
        return await generator.generate(body.prompt, body.thread_id)
    except WorkflowGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate a valid workflow.",
        ) from exc
    except WorkflowProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Workflow generation provider failed.",
        ) from exc

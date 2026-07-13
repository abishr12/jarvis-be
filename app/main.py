from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic

from app.api.health import router as health_router
from app.api.workflows import router as workflows_router
from app.config import settings
from app.services.workflow_generator import WorkflowGenerator


def _configure_workflow_generator(app: FastAPI) -> None:
    if settings.anthropic_api_key is None:
        app.state.workflow_generator = None
        return

    model = ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout,
        stop=None,
    )
    app.state.workflow_generator = WorkflowGenerator(model)


def create_app() -> FastAPI:
    app = FastAPI(title="Jarvis API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _configure_workflow_generator(app)
    app.include_router(health_router)
    app.include_router(workflows_router)

    return app

import logging
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader
from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputError, ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from app.models.workflow import WorkflowAction, WorkflowGenerationResult

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

ACTION_CATALOG: dict[WorkflowAction, str] = {
    WorkflowAction.gmail_search: "Search Gmail. config: {query: string} using Gmail search syntax.",
    WorkflowAction.gmail_get_message: "Fetch one email. config: {messageId: string}.",
    WorkflowAction.gmail_create_draft: "Create a draft. config: {to, subject, body}.",
    WorkflowAction.gmail_send: "Send an email. config: {to, subject, body}.",
    WorkflowAction.gmail_add_label: "Add a Gmail label. config: {label: string}.",
    WorkflowAction.gmail_archive: "Archive an email. config: {}.",
    WorkflowAction.llm_classify: "Classify text. config: {categories: string[]}.",
    WorkflowAction.llm_extract: "Extract structured info. config: {instructions: string}.",
    WorkflowAction.llm_summarize: "Summarize text. config: {}.",
    WorkflowAction.llm_compose: "Draft text. config: {instructions: string}.",
    WorkflowAction.platform_approval: "Pause for human approval. config: {}.",
}

SYSTEM_PROMPT = _env.get_template("workflow_system.jinja").render(
    actions=[{"name": action.value, "description": desc} for action, desc in ACTION_CATALOG.items()]
)


class WorkflowProviderError(Exception):
    """The upstream model request failed."""


class WorkflowGenerationError(Exception):
    """The model could not produce a valid workflow."""


class WorkflowGenerator:
    def __init__(self, model: BaseChatModel) -> None:
        self._agent = create_agent(
            model=model,
            tools=[],
            system_prompt=SYSTEM_PROMPT,
            response_format=ToolStrategy(WorkflowGenerationResult),
            checkpointer=InMemorySaver(),
        )

    async def generate(self, prompt: str, thread_id: str) -> WorkflowGenerationResult:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        try:
            result = await self._agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
            )
        except StructuredOutputError as exc:
            logger.warning("structured output failed: %s", exc)
            raise WorkflowGenerationError(str(exc)) from exc
        except Exception as exc:
            logger.warning("agent invocation failed: %s", exc)
            raise WorkflowProviderError(str(exc)) from exc
        return cast(WorkflowGenerationResult, result["structured_response"])

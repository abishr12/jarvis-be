import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader
from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputError, ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.models.workflow import (
    WorkflowAction,
    WorkflowGenerationResult,
    WorkflowMessageDeltaEvent,
    WorkflowResultEvent,
    WorkflowStreamEvent,
    WorkflowToolCallEvent,
    WorkflowToolResultEvent,
)

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

_CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("app.models.workflow", "WorkflowAction"),
        ("app.models.workflow", "WorkflowGenerationResult"),
    ]
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
            checkpointer=InMemorySaver(serde=_CHECKPOINT_SERDE),
        )

    async def stream(self, prompt: str, thread_id: str) -> AsyncIterator[WorkflowStreamEvent]:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        tool_names: dict[str, str] = {}
        result_emitted = False

        try:
            async for chunk in self._agent.astream(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if chunk["type"] == "messages":
                    message, _metadata = chunk["data"]

                    if isinstance(message, AIMessageChunk) and message.text:
                        yield WorkflowMessageDeltaEvent(delta=message.text)

                elif chunk["type"] == "updates":
                    for update in chunk["data"].values():
                        if not isinstance(update, dict):
                            continue

                        structured_response = update.get("structured_response")

                        if structured_response is not None and not result_emitted:
                            result = cast(WorkflowGenerationResult, structured_response)
                            yield WorkflowResultEvent(result=result)
                            result_emitted = True

                        messages = update.get("messages")
                        if not messages:
                            continue

                        message = messages[-1]

                        if isinstance(message, AIMessage):
                            for tool_call in message.tool_calls:
                                name = tool_call["name"]

                                # ToolStrategy uses this internal call to return
                                # the final structured workflow.
                                if name == WorkflowGenerationResult.__name__:
                                    continue

                                tool_call_id = tool_call.get("id")
                                if not tool_call_id:
                                    continue

                                tool_names[tool_call_id] = name
                                yield WorkflowToolCallEvent(
                                    tool_call_id=tool_call_id,
                                    name=name,
                                    arguments=tool_call["args"],
                                )

                        elif isinstance(message, ToolMessage):
                            tool_name = message.name or tool_names.get(message.tool_call_id)

                            if tool_name is None or tool_name == WorkflowGenerationResult.__name__:
                                continue

                            yield WorkflowToolResultEvent(
                                tool_call_id=message.tool_call_id,
                                name=tool_name,
                                output=message.content,
                            )

            if not result_emitted:
                raise WorkflowGenerationError(
                    "Agent stream completed without a structured response."
                )
        except WorkflowGenerationError:
            raise
        except StructuredOutputError as exc:
            logger.warning("structured output stream failed: %s", exc)
            raise WorkflowGenerationError(str(exc)) from exc
        except Exception as exc:
            logger.warning("agent stream failed: %s", exc)
            raise WorkflowProviderError(str(exc)) from exc

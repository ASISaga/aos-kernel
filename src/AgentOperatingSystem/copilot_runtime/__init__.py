"""Copilot Runtime — CopilotKit/SDK-JS bridge to AOS Foundry orchestration.

The :class:`CopilotRuntime` connects CopilotKit frontend clients (using
``@copilotkit/sdk-js``) to the AOS Foundry orchestration engine.  It
accepts standard chat messages, routes them through the kernel's
:class:`~AgentOperatingSystem.orchestration.FoundryOrchestrationEngine`,
and streams responses back in the Vercel AI SDK data-stream format that
CopilotKit clients expect.

Typical usage with FastAPI::

    from AgentOperatingSystem import AgentOperatingSystem
    from AgentOperatingSystem.copilot_runtime import CopilotRuntime
    from fastapi import FastAPI

    app = FastAPI()
    kernel = AgentOperatingSystem()
    runtime = CopilotRuntime(kernel=kernel)
    app.include_router(runtime.fastapi_router())

The default endpoint path is ``/copilotkit`` but can be changed via the
*path* parameter of :meth:`CopilotRuntime.fastapi_router`.

SSE stream format
-----------------
Responses are emitted as Server-Sent Events using the Vercel AI SDK data
stream protocol, which is the wire format that ``@copilotkit/sdk-js``
clients parse:

* ``data: 0:"<chunk>"\\n\\n`` — UTF-8 text chunk
* ``data: 2:[...]\\n\\n`` — arbitrary JSON data / annotations
* ``data: d:{...}\\n\\n`` — stream finish signal
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import APIRouter
    from AgentOperatingSystem.agent_operating_system import AgentOperatingSystem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CopilotMessage(BaseModel):
    """A single chat message in CopilotKit / OpenAI format.

    :param role: Message role — ``"user"``, ``"assistant"``, or ``"system"``.
    :param content: Text content of the message.
    :param id: Optional message identifier.
    """

    role: str
    content: str
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class CopilotRuntimeRequest(BaseModel):
    """Request body sent by a ``@copilotkit/sdk-js`` frontend client.

    :param messages: Full conversation history including the latest user turn.
    :param thread_id: Stable identifier for the conversation thread.  A new
        thread is created when omitted or ``None``.
    :param agent_id: Local AOS agent to use for this turn.  Falls back to the
        :attr:`CopilotRuntime.default_agent_id` when omitted.
    :param actions: Optional list of action definitions exposed to the client.
    :param agent_states: Optional per-agent state snapshots.
    """

    messages: List[CopilotMessage]
    thread_id: Optional[str] = None
    agent_id: Optional[str] = None
    actions: Optional[List[Dict[str, Any]]] = None
    agent_states: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# SSE helpers (Vercel AI SDK data-stream protocol)
# ---------------------------------------------------------------------------


def _sse_text_chunk(text: str) -> str:
    """Return a text-chunk SSE event (type ``0``)."""
    return f"data: 0:{json.dumps(text)}\n\n"


def _sse_data(data: Any) -> str:
    """Return a data-annotation SSE event (type ``2``)."""
    return f"data: 2:{json.dumps(data)}\n\n"


def _sse_finish(finish_reason: str = "stop") -> str:
    """Return a stream-finish SSE event (type ``d``)."""
    return f"data: d:{json.dumps({'finishReason': finish_reason})}\n\n"


# ---------------------------------------------------------------------------
# CopilotRuntime
# ---------------------------------------------------------------------------


class CopilotRuntime:
    """CopilotKit Runtime — bridges ``@copilotkit/sdk-js`` clients to AOS Foundry.

    The runtime maintains a mapping of CopilotKit *thread IDs* to AOS
    orchestration IDs so that multi-turn conversations are automatically
    routed to the correct Foundry thread.

    :param kernel: Initialised :class:`~AgentOperatingSystem.AgentOperatingSystem`
        instance.  Must be initialised (``await kernel.initialize()``) before
        the first request is processed.
    :param default_agent_id: Agent used when the request does not specify one.
        If empty *and* no agent is registered, the runtime still creates an
        orchestration and routes the message without a Foundry agent ID.
    :param default_purpose: Purpose text used when creating new orchestrations.
    """

    def __init__(
        self,
        kernel: AgentOperatingSystem,
        default_agent_id: str = "",
        default_purpose: str = "Assist the user",
    ) -> None:
        self.kernel = kernel
        self.default_agent_id = default_agent_id
        self.default_purpose = default_purpose
        # copilotkit thread_id → AOS orchestration_id
        self._thread_orchestrations: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Core request processing
    # ------------------------------------------------------------------

    async def process_request(
        self,
        request: CopilotRuntimeRequest,
    ) -> AsyncIterator[str]:
        """Process a CopilotKit request and yield Vercel AI SDK SSE events.

        1. Resolve (or create) the AOS orchestration for the conversation thread.
        2. Extract the latest user message.
        3. Run an agent turn via :meth:`AgentOperatingSystem.run_agent_turn`.
        4. Stream the response back as SSE data events.

        :param request: Incoming CopilotKit request.
        :yields: SSE event strings (text/event-stream lines).
        """
        thread_id = request.thread_id or str(uuid.uuid4())
        agent_id = request.agent_id or self.default_agent_id

        # Validate: at least one user message must be present
        user_messages = [m for m in request.messages if m.role == "user"]
        if not user_messages:
            yield _sse_text_chunk("No user message provided.")
            yield _sse_finish("stop")
            return

        last_user_message = user_messages[-1].content

        try:
            orchestration_id = await self._get_or_create_orchestration(
                thread_id=thread_id,
                agent_id=agent_id,
            )

            effective_agent_id = agent_id or self._resolve_default_agent()
            turn_result = await self.kernel.run_agent_turn(
                orchestration_id=orchestration_id,
                agent_id=effective_agent_id,
                message=last_user_message,
            )

            # Attempt to extract a text response from the turn result
            response_text = turn_result.get("response", "")
            if not response_text:
                # Fall back to the latest assistant message on the thread
                response_text = await self._get_latest_assistant_response(
                    orchestration_id
                )

            if response_text:
                yield _sse_text_chunk(response_text)
            else:
                # Emit metadata so the client knows the turn completed
                yield _sse_data(
                    {
                        "orchestration_id": orchestration_id,
                        "run_id": turn_result.get("run_id"),
                        "status": turn_result.get("status", "completed"),
                    }
                )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("CopilotRuntime.process_request failed: %s", exc)
            yield _sse_text_chunk("An error occurred while processing the request.")

        yield _sse_finish("stop")

    # ------------------------------------------------------------------
    # Orchestration helpers
    # ------------------------------------------------------------------

    async def _get_or_create_orchestration(
        self,
        thread_id: str,
        agent_id: str,
    ) -> str:
        """Return the AOS orchestration ID for *thread_id*, creating it if needed.

        :param thread_id: CopilotKit conversation thread identifier.
        :param agent_id: Requested agent for the new orchestration.
        :returns: AOS orchestration ID.
        """
        if thread_id in self._thread_orchestrations:
            return self._thread_orchestrations[thread_id]

        # Gather agent IDs for the new orchestration
        agent_ids: List[str] = [agent_id] if agent_id else []
        if not agent_ids:
            registered = self.kernel.agent_manager.list_registered_agents()
            agent_ids = [r["agent_id"] for r in registered]
        if not agent_ids:
            agent_ids = ["default"]

        orch = await self.kernel.create_orchestration(
            agent_ids=agent_ids,
            purpose=self.default_purpose,
        )
        orchestration_id: str = orch["orchestration_id"]
        self._thread_orchestrations[thread_id] = orchestration_id

        logger.info(
            "CopilotRuntime: created orchestration %s for thread %s",
            orchestration_id,
            thread_id,
        )
        return orchestration_id

    def _resolve_default_agent(self) -> str:
        """Return the first registered agent ID or a stub fallback."""
        registered = self.kernel.agent_manager.list_registered_agents()
        if registered:
            return registered[0]["agent_id"]
        return "default"

    async def _get_latest_assistant_response(
        self, orchestration_id: str
    ) -> str:
        """Return the content of the most recent assistant message on the thread.

        :param orchestration_id: Target orchestration.
        :returns: Message content string, or empty string if none found.
        """
        try:
            messages = await self.kernel.get_thread_messages(orchestration_id)
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    return str(msg.get("content", ""))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug("Failed to retrieve assistant response: %s", exc)
        return ""

    # ------------------------------------------------------------------
    # Thread / orchestration introspection
    # ------------------------------------------------------------------

    def get_orchestration_id(self, thread_id: str) -> Optional[str]:
        """Return the AOS orchestration ID for *thread_id*, or ``None``.

        :param thread_id: CopilotKit conversation thread identifier.
        :returns: Orchestration ID string, or ``None`` if not yet created.
        """
        return self._thread_orchestrations.get(thread_id)

    def list_threads(self) -> List[str]:
        """Return all CopilotKit thread IDs currently managed by this runtime.

        :returns: List of thread ID strings.
        """
        return list(self._thread_orchestrations.keys())

    @property
    def thread_count(self) -> int:
        """Number of active CopilotKit conversation threads."""
        return len(self._thread_orchestrations)

    # ------------------------------------------------------------------
    # FastAPI integration
    # ------------------------------------------------------------------

    def fastapi_router(self, path: str = "/copilotkit") -> APIRouter:
        """Return a FastAPI :class:`~fastapi.APIRouter` with the CopilotKit endpoint.

        Mount the returned router on a FastAPI application::

            app.include_router(runtime.fastapi_router())

        The endpoint accepts ``POST <path>`` requests with a
        :class:`CopilotRuntimeRequest` JSON body and responds with an SSE
        stream (``text/event-stream``).

        :param path: URL path for the endpoint.  Defaults to ``/copilotkit``.
        :returns: Configured :class:`~fastapi.APIRouter` instance.
        """
        from fastapi import APIRouter  # pylint: disable=import-outside-toplevel
        from fastapi.responses import StreamingResponse  # pylint: disable=import-outside-toplevel

        router = APIRouter()
        _runtime = self

        @router.post(path)
        async def copilotkit_endpoint(
            request: CopilotRuntimeRequest,
        ) -> StreamingResponse:
            """CopilotKit runtime endpoint — streams SSE responses."""

            async def _stream() -> AsyncIterator[str]:
                async for chunk in _runtime.process_request(request):
                    yield chunk

            return StreamingResponse(
                _stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        return router


__all__ = [
    "CopilotRuntime",
    "CopilotMessage",
    "CopilotRuntimeRequest",
]

"""Orchestration engine — Foundry Agent Service native orchestration.

:class:`FoundryOrchestrationEngine` manages multi-agent orchestrations
entirely through the Foundry Agent Service.  All orchestration lifecycle
(create, run turns, stop) is backed by Foundry threads, messages, and runs.

Foundry primitives used:

* **Thread** — shared conversation context for an orchestration.
* **Message** — individual messages posted to a thread.
* **Run** — an agent execution turn on a thread.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FoundryOrchestrationEngine:
    """Manages multi-agent orchestrations via the Foundry Agent Service.

    :param project_client: An ``AIProjectClient`` instance whose ``.agents``
        property provides the ``AgentsClient``.
    :param agent_manager: The kernel's :class:`FoundryAgentManager`.
    """

    def __init__(
        self,
        project_client: Any = None,
        agent_manager: Any = None,
    ) -> None:
        self.project_client = project_client
        self.agent_manager = agent_manager
        # orchestration_id → record
        self._orchestrations: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Orchestration lifecycle
    # ------------------------------------------------------------------

    async def create_orchestration(
        self,
        agent_ids: List[str],
        purpose: str,
        purpose_scope: str = "",
        context: Optional[Dict[str, Any]] = None,
        workflow: str = "collaborative",
        mcp_servers: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new purpose-driven orchestration backed by a Foundry thread.

        Creates a Foundry thread and posts an initial system message with the
        orchestration purpose.

        :param agent_ids: Local agent identifiers to participate.
        :param purpose: Orchestration purpose text.
        :param purpose_scope: Boundaries of the purpose.
        :param context: Contextual data for agents.
        :param workflow: Workflow pattern (``collaborative``, ``sequential``,
            ``hierarchical``).
        :param mcp_servers: Per-agent MCP server selection.
        :param metadata: Key-value metadata for the Foundry thread.
        :returns: Orchestration record with ``orchestration_id``, ``thread_id``,
            and status.
        """
        orchestration_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        thread_id = str(uuid.uuid4())

        # Create a Foundry thread when the project client is available
        if self.project_client is not None:
            try:
                thread = self.project_client.agents.create_thread(
                    metadata=metadata or {},
                )
                thread_id = thread.id

                # Post the orchestration purpose as the initial message
                self.project_client.agents.create_message(
                    thread_id=thread_id,
                    role="user",
                    content=f"[ORCHESTRATION] Purpose: {purpose}"
                    + (f" | Scope: {purpose_scope}" if purpose_scope else ""),
                )
            except Exception as exc:
                logger.warning("Foundry thread creation failed: %s — using local stub", exc)

        record: Dict[str, Any] = {
            "orchestration_id": orchestration_id,
            "thread_id": thread_id,
            "agent_ids": list(agent_ids),
            "purpose": purpose,
            "purpose_scope": purpose_scope,
            "context": context or {},
            "workflow": workflow,
            "mcp_servers": mcp_servers or {},
            "metadata": metadata or {},
            "status": "active",
            "turns": [],
            "created_at": now,
            "updated_at": now,
            "managed_by": "foundry_agent_service",
        }
        self._orchestrations[orchestration_id] = record
        logger.info(
            "Created orchestration %s (thread=%s) — agents=%s workflow=%s purpose=%s",
            orchestration_id,
            thread_id,
            agent_ids,
            workflow,
            purpose[:60],
        )
        return dict(record)

    async def run_agent_turn(
        self,
        orchestration_id: str,
        agent_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Execute a single agent turn within an orchestration.

        Posts a message to the Foundry thread then creates a run for the
        specified agent.

        :param orchestration_id: Target orchestration.
        :param agent_id: Agent to execute this turn.
        :param message: Input message for the agent.
        :returns: Turn result with ``run_id`` and ``status``.
        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")

        run_id = str(uuid.uuid4())
        turn_result: Dict[str, Any] = {
            "run_id": run_id,
            "agent_id": agent_id,
            "message": message,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Post message and create a run in Foundry
        if self.project_client is not None:
            try:
                thread_id = record["thread_id"]

                # Post user message to the thread
                self.project_client.agents.create_message(
                    thread_id=thread_id,
                    role="user",
                    content=message,
                )

                # Resolve Foundry agent ID
                foundry_agent_id = agent_id
                if self.agent_manager is not None:
                    try:
                        foundry_agent_id = self.agent_manager.get_foundry_agent_id(agent_id)
                    except KeyError:
                        pass

                # Create and poll a run
                run = self.project_client.agents.create_and_process_run(
                    thread_id=thread_id,
                    assistant_id=foundry_agent_id,
                )
                run_id = run.id
                turn_result["run_id"] = run_id
                turn_result["status"] = run.status
            except Exception as exc:
                logger.warning("Foundry run_agent_turn failed: %s — using local result", exc)

        record["turns"].append(turn_result)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return turn_result

    async def get_thread_messages(
        self,
        orchestration_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve all messages from the orchestration's Foundry thread.

        :param orchestration_id: Target orchestration.
        :returns: List of message dicts.
        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")

        if self.project_client is not None:
            try:
                messages = self.project_client.agents.list_messages(
                    thread_id=record["thread_id"],
                )
                result = []
                for m in messages.data:
                    # Handle structured content (list of content blocks)
                    content = m.content
                    if isinstance(content, list) and content:
                        text_block = content[0]
                        content = getattr(getattr(text_block, "text", None), "value", str(text_block))
                    result.append({"role": m.role, "content": content, "id": m.id})
                return result
            except Exception as exc:
                logger.warning("Failed to list thread messages: %s", exc)

        # Local fallback: return turns as messages
        return [
            {"role": "user", "content": t["message"], "agent_id": t["agent_id"]}
            for t in record["turns"]
        ]

    async def get_status(self, orchestration_id: str) -> Dict[str, Any]:
        """Get the current status of an orchestration.

        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")
        return dict(record)

    async def stop_orchestration(self, orchestration_id: str) -> None:
        """Stop an active orchestration.

        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")

        # Cancel any in-progress runs on the thread
        if self.project_client is not None:
            try:
                runs = self.project_client.agents.list_runs(
                    thread_id=record["thread_id"],
                )
                for run in getattr(runs, "data", []):
                    if run.status in ("queued", "in_progress"):
                        self.project_client.agents.cancel_run(
                            thread_id=record["thread_id"],
                            run_id=run.id,
                        )
            except Exception as exc:
                logger.warning("Foundry stop_orchestration failed: %s", exc)

        record["status"] = "stopped"
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Stopped orchestration %s", orchestration_id)

    async def cancel_orchestration(self, orchestration_id: str) -> None:
        """Cancel an orchestration.

        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")

        record["status"] = "cancelled"
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Cancelled orchestration %s", orchestration_id)

    async def delete_thread(self, orchestration_id: str) -> None:
        """Delete the Foundry thread for an orchestration.

        :raises KeyError: If the orchestration is not found.
        """
        record = self._orchestrations.get(orchestration_id)
        if record is None:
            raise KeyError(f"Orchestration {orchestration_id!r} not found")

        if self.project_client is not None:
            try:
                self.project_client.agents.delete_thread(record["thread_id"])
            except Exception as exc:
                logger.warning("Failed to delete Foundry thread: %s", exc)

        self._orchestrations.pop(orchestration_id, None)
        logger.info("Deleted thread for orchestration %s", orchestration_id)

    def list_orchestrations(self) -> List[Dict[str, Any]]:
        """Return all orchestration records."""
        return list(self._orchestrations.values())

    @property
    def orchestration_count(self) -> int:
        """Number of active orchestrations."""
        return len(self._orchestrations)

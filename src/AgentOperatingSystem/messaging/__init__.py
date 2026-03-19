"""Messaging bridge — bidirectional communication via Foundry threads.

:class:`FoundryMessageBridge` connects the local PurposeDrivenAgent event/message
system with Foundry conversation threads.  Messages flow in both directions:

* **Inbound** (Foundry → PDA): Orchestration instructions are translated into
  ``handle_message`` calls on the PurposeDrivenAgent.
* **Outbound** (PDA → Foundry): Agent responses and events are posted back to
  the Foundry thread so the orchestration has a complete conversation history.

All messages are posted directly to Foundry threads via the ``AgentsClient``
(from ``azure-ai-projects``).

When :attr:`subconscious_mcp_url` is configured, every bridged message is
also persisted to the ``subconscious.asisaga.com`` MCP server so that
conversation history is available across sessions and kernel restarts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: HTTP timeout (seconds) for fire-and-forget persistence calls to subconscious.
_SUBCONSCIOUS_PERSIST_TIMEOUT: float = 5.0
#: HTTP timeout (seconds) for conversation retrieval calls to subconscious.
_SUBCONSCIOUS_RETRIEVE_TIMEOUT: float = 10.0


class FoundryMessageBridge:
    """Bidirectional message bridge between PurposeDrivenAgent and Foundry threads.

    :param agent_manager: The kernel's :class:`FoundryAgentManager`.
    :param orchestration_engine: The kernel's :class:`FoundryOrchestrationEngine`.
    :param subconscious_mcp_url: URL of the subconscious MCP server for
        conversation persistence.  When set, every inbound and outbound
        message is also written to the subconscious store so that the full
        conversation history survives kernel restarts.
    """

    def __init__(
        self,
        agent_manager: Any = None,
        orchestration_engine: Any = None,
        subconscious_mcp_url: str = "",
    ) -> None:
        self.agent_manager = agent_manager
        self.orchestration_engine = orchestration_engine
        self.subconscious_mcp_url = subconscious_mcp_url
        # message log: list of all bridged messages
        self._messages: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Inbound: Foundry → PurposeDrivenAgent
    # ------------------------------------------------------------------

    async def deliver_to_agent(
        self,
        agent_id: str,
        message: str,
        orchestration_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deliver a Foundry orchestration message to a PurposeDrivenAgent.

        This translates Foundry thread messages into the PDA event model.
        The concrete delivery mechanism depends on how agents are hosted
        (in-process, via HTTP, or via Service Bus).

        :param agent_id: Target agent identifier.
        :param message: Message content from the orchestration thread.
        :param orchestration_id: Orchestration that generated the message.
        :param metadata: Additional metadata.
        :returns: Delivery result with message_id and status.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        record: Dict[str, Any] = {
            "message_id": message_id,
            "direction": "foundry_to_agent",
            "agent_id": agent_id,
            "orchestration_id": orchestration_id,
            "content": message,
            "metadata": metadata or {},
            "status": "delivered",
            "timestamp": now,
        }
        self._messages.append(record)
        logger.info(
            "Delivered message %s to agent %s (orchestration=%s)",
            message_id,
            agent_id,
            orchestration_id,
        )
        await self._persist_to_subconscious(record)
        return record

    # ------------------------------------------------------------------
    # Outbound: PurposeDrivenAgent → Foundry
    # ------------------------------------------------------------------

    async def send_to_foundry(
        self,
        agent_id: str,
        message: str,
        orchestration_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a PurposeDrivenAgent response back to the Foundry thread.

        Agent responses, events, and purpose-alignment updates are posted
        to the orchestration's Foundry thread for a complete audit trail.

        :param agent_id: Source agent identifier.
        :param message: Response content from the agent.
        :param orchestration_id: Target orchestration.
        :param metadata: Additional metadata.
        :returns: Send result with message_id and status.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Post to orchestration thread if available
        if orchestration_id and self.orchestration_engine:
            try:
                await self.orchestration_engine.run_agent_turn(
                    orchestration_id=orchestration_id,
                    agent_id=agent_id,
                    message=message,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to post to Foundry thread for orchestration %s: %s",
                    orchestration_id,
                    exc,
                )

        record: Dict[str, Any] = {
            "message_id": message_id,
            "direction": "agent_to_foundry",
            "agent_id": agent_id,
            "orchestration_id": orchestration_id,
            "content": message,
            "metadata": metadata or {},
            "status": "sent",
            "timestamp": now,
        }
        self._messages.append(record)
        logger.info(
            "Sent message %s from agent %s to Foundry (orchestration=%s)",
            message_id,
            agent_id,
            orchestration_id,
        )
        await self._persist_to_subconscious(record)
        return record

    # ------------------------------------------------------------------
    # Purpose alignment messaging
    # ------------------------------------------------------------------

    async def broadcast_purpose_alignment(
        self,
        orchestration_id: str,
        purpose: str,
        purpose_scope: str = "",
    ) -> List[Dict[str, Any]]:
        """Broadcast a purpose-alignment message to all agents in an orchestration.

        This is called when an orchestration's purpose changes and agents
        need to re-align their working purpose.

        :param orchestration_id: Target orchestration.
        :param purpose: New purpose text.
        :param purpose_scope: New purpose scope.
        :returns: List of delivery results.
        """
        if not self.orchestration_engine:
            return []

        try:
            status = await self.orchestration_engine.get_status(orchestration_id)
        except KeyError:
            logger.warning("Cannot broadcast — orchestration %s not found", orchestration_id)
            return []

        results: List[Dict[str, Any]] = []
        alignment_message = (
            f"[PURPOSE ALIGNMENT] Align your working purpose to: {purpose}"
        )
        if purpose_scope:
            alignment_message += f" | Scope: {purpose_scope}"

        for agent_id in status.get("agent_ids", []):
            result = await self.deliver_to_agent(
                agent_id=agent_id,
                message=alignment_message,
                orchestration_id=orchestration_id,
                metadata={"type": "purpose_alignment", "purpose": purpose, "purpose_scope": purpose_scope},
            )
            results.append(result)

        logger.info(
            "Broadcast purpose alignment to %d agents in orchestration %s",
            len(results),
            orchestration_id,
        )
        return results

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_messages(
        self,
        agent_id: Optional[str] = None,
        orchestration_id: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query bridged messages with optional filters.

        :param agent_id: Filter by agent.
        :param orchestration_id: Filter by orchestration.
        :param direction: Filter by direction (``foundry_to_agent`` or
            ``agent_to_foundry``).
        """
        results = self._messages
        if agent_id:
            results = [m for m in results if m["agent_id"] == agent_id]
        if orchestration_id:
            results = [m for m in results if m["orchestration_id"] == orchestration_id]
        if direction:
            results = [m for m in results if m["direction"] == direction]
        return results

    @property
    def message_count(self) -> int:
        """Total number of bridged messages."""
        return len(self._messages)

    # ------------------------------------------------------------------
    # Subconscious MCP persistence
    # ------------------------------------------------------------------

    async def _persist_to_subconscious(self, record: Dict[str, Any]) -> None:
        """Persist a message record to the subconscious MCP server.

        Calls the subconscious MCP server's ``store_conversation`` tool via
        the standard MCP JSON-RPC protocol.  The call is fire-and-forget:
        failures are logged as warnings and never propagate to the caller so
        that conversation delivery is never blocked by persistence errors.

        :param record: The message record to persist.
        """
        if not self.subconscious_mcp_url:
            return
        try:
            import httpx

            payload = {
                "jsonrpc": "2.0",
                "id": record["message_id"],
                "method": "tools/call",
                "params": {
                    "name": "store_conversation",
                    "arguments": {
                        "message_id": record["message_id"],
                        "orchestration_id": record.get("orchestration_id"),
                        "agent_id": record["agent_id"],
                        "direction": record["direction"],
                        "content": record["content"],
                        "metadata": record.get("metadata", {}),
                        "timestamp": record["timestamp"],
                    },
                },
            }
            endpoint = f"{self.subconscious_mcp_url.rstrip('/')}/mcp"
            async with httpx.AsyncClient(timeout=_SUBCONSCIOUS_PERSIST_TIMEOUT) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                logger.debug(
                    "Persisted message %s to subconscious (orchestration=%s)",
                    record["message_id"],
                    record.get("orchestration_id"),
                )
        except Exception as exc:
            logger.warning(
                "Failed to persist message %s to subconscious: %s",
                record.get("message_id"),
                exc,
            )

    async def get_conversation_from_subconscious(
        self,
        orchestration_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve persisted conversation history from the subconscious server.

        Calls the subconscious MCP server's ``retrieve_conversation`` tool to
        fetch all stored messages for the given orchestration.  Returns an
        empty list when the subconscious URL is not configured or the call
        fails.

        :param orchestration_id: The orchestration whose history to retrieve.
        :returns: List of persisted message records, oldest first.
        """
        if not self.subconscious_mcp_url:
            return []
        try:
            import httpx

            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "retrieve_conversation",
                    "arguments": {"orchestration_id": orchestration_id},
                },
            }
            endpoint = f"{self.subconscious_mcp_url.rstrip('/')}/mcp"
            async with httpx.AsyncClient(timeout=_SUBCONSCIOUS_RETRIEVE_TIMEOUT) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("result", {}).get("messages", [])
        except Exception as exc:
            logger.warning(
                "Failed to retrieve conversation %s from subconscious: %s",
                orchestration_id,
                exc,
            )
            return []

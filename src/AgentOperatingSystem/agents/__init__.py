"""Agent management — Foundry Agent Service native registration.

:class:`FoundryAgentManager` manages the full lifecycle of agents within the
Azure AI Foundry Agent Service.  It handles:

* Creating / deleting agents via the ``AgentsClient`` (from ``azure-ai-agents``).
* Attaching Foundry-native tools: ``code_interpreter``, ``file_search``,
  ``bing_grounding``, ``azure_ai_search``, ``openapi``, and ``function``.
* Maintaining a bidirectional mapping between local agent IDs and Foundry
  agent IDs.
* Purpose alignment when orchestration context changes.

Also exports:

* :class:`PurposeDrivenAgent` — the fundamental agent building block
* :class:`GenericPurposeDrivenAgent` — alias for PurposeDrivenAgent
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Re-export from purpose_driven module
from .purpose_driven import PurposeDrivenAgent, GenericPurposeDrivenAgent

logger = logging.getLogger(__name__)

#: Foundry-native tool types supported by the Agent Service.
FOUNDRY_TOOL_TYPES = frozenset({
    "code_interpreter",
    "file_search",
    "bing_grounding",
    "azure_ai_search",
    "openapi",
    "function",
})


class FoundryAgentManager:
    """Manages agent lifecycle via the Foundry Agent Service.

    :param project_client: An ``AIProjectClient`` connected to the target
        Foundry project.  The ``project_client.agents`` property provides
        the ``AgentsClient`` used for all operations.
    :param default_model: Default model deployment name for new agents.
    """

    def __init__(
        self,
        project_client: Any = None,
        default_model: str = "gpt-4o",
    ) -> None:
        self.project_client = project_client
        self.default_model = default_model
        # local_agent_id → foundry registration record
        self._registered: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_agent(
        self,
        agent_id: str,
        purpose: str,
        name: str = "",
        adapter_name: str = "",
        capabilities: Optional[List[str]] = None,
        model: Optional[str] = None,
        tools: Optional[List[dict]] = None,
        tool_resources: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        response_format: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Register an agent with the Foundry Agent Service.

        If the agent is already registered the existing record is returned.

        :param agent_id: Local agent identifier.
        :param purpose: Agent's perpetual purpose (used as ``instructions``).
        :param name: Human-readable name (defaults to *agent_id*).
        :param adapter_name: LoRA adapter name for domain specialisation.
        :param capabilities: Declared capabilities list.
        :param model: Model deployment name (overrides default).
        :param tools: Foundry tool definitions (``code_interpreter``,
            ``file_search``, ``bing_grounding``, ``azure_ai_search``,
            ``openapi``, ``function``).
        :param tool_resources: Foundry tool resources (e.g. vector store IDs
            for ``file_search``).
        :param temperature: Sampling temperature for the model.
        :param top_p: Nucleus-sampling probability mass.
        :param response_format: Response format (``text`` or ``json_object``).
        :param metadata: Key-value metadata attached to the Foundry agent.
        :returns: Registration record dictionary.
        """
        if agent_id in self._registered:
            logger.debug("Agent %s already registered — returning existing record", agent_id)
            return self._registered[agent_id]

        foundry_agent_id = str(uuid.uuid4())
        model_name = model or self.default_model
        instructions = purpose
        if adapter_name:
            instructions = f"[Adapter: {adapter_name}] {purpose}"

        # Create agent in Foundry Agent Service if project client is available
        if self.project_client is not None:
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "name": name or agent_id,
                    "instructions": instructions,
                }
                if tools:
                    kwargs["tools"] = tools
                if tool_resources:
                    kwargs["tool_resources"] = tool_resources
                if temperature is not None:
                    kwargs["temperature"] = temperature
                if top_p is not None:
                    kwargs["top_p"] = top_p
                if response_format:
                    kwargs["response_format"] = response_format
                if metadata:
                    kwargs["metadata"] = metadata

                foundry_agent = self.project_client.agents.create_agent(**kwargs)
                foundry_agent_id = foundry_agent.id
            except Exception as exc:
                logger.warning(
                    "Failed to create Foundry agent for %s: %s — using local stub",
                    agent_id,
                    exc,
                )

        record: Dict[str, Any] = {
            "agent_id": agent_id,
            "foundry_agent_id": foundry_agent_id,
            "name": name or agent_id,
            "purpose": purpose,
            "adapter_name": adapter_name,
            "capabilities": capabilities or [],
            "model": model_name,
            "tools": tools or [],
            "tool_resources": tool_resources or {},
            "temperature": temperature,
            "top_p": top_p,
            "response_format": response_format,
            "metadata": metadata or {},
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "managed_by": "foundry_agent_service",
        }
        self._registered[agent_id] = record
        logger.info(
            "Registered agent %s → Foundry agent %s (model=%s)",
            agent_id,
            foundry_agent_id,
            model_name,
        )
        return record

    async def update_agent(
        self,
        agent_id: str,
        purpose: Optional[str] = None,
        name: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[dict]] = None,
        tool_resources: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Update an existing Foundry agent's configuration.

        :param agent_id: Local agent identifier.
        :returns: Updated registration record.
        :raises KeyError: If the agent is not registered.
        """
        record = self._registered.get(agent_id)
        if record is None:
            raise KeyError(f"Agent {agent_id!r} is not registered")

        if self.project_client is not None:
            try:
                kwargs: Dict[str, Any] = {"assistant_id": record["foundry_agent_id"]}
                if purpose is not None:
                    kwargs["instructions"] = purpose
                if name is not None:
                    kwargs["name"] = name
                if model is not None:
                    kwargs["model"] = model
                if tools is not None:
                    kwargs["tools"] = tools
                if tool_resources is not None:
                    kwargs["tool_resources"] = tool_resources
                if temperature is not None:
                    kwargs["temperature"] = temperature
                if top_p is not None:
                    kwargs["top_p"] = top_p
                if metadata is not None:
                    kwargs["metadata"] = metadata
                self.project_client.agents.update_agent(**kwargs)
            except Exception as exc:
                logger.warning("Failed to update Foundry agent %s: %s", agent_id, exc)

        # Update local record
        if purpose is not None:
            record["purpose"] = purpose
        if name is not None:
            record["name"] = name
        if model is not None:
            record["model"] = model
        if tools is not None:
            record["tools"] = tools
        if tool_resources is not None:
            record["tool_resources"] = tool_resources
        if temperature is not None:
            record["temperature"] = temperature
        if top_p is not None:
            record["top_p"] = top_p
        if metadata is not None:
            record["metadata"] = metadata

        logger.info("Updated agent %s", agent_id)
        return dict(record)

    async def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent registration and delete it from Foundry.

        :param agent_id: Local agent identifier.
        :raises KeyError: If the agent is not registered.
        """
        record = self._registered.pop(agent_id, None)
        if record is None:
            raise KeyError(f"Agent {agent_id!r} is not registered")

        if self.project_client is not None:
            try:
                self.project_client.agents.delete_agent(record["foundry_agent_id"])
            except Exception as exc:
                logger.warning("Failed to delete Foundry agent %s: %s", record["foundry_agent_id"], exc)
        logger.info("Unregistered agent %s", agent_id)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_registration(self, agent_id: str) -> Dict[str, Any]:
        """Return the registration record for *agent_id*.

        :raises KeyError: If the agent is not registered.
        """
        if agent_id not in self._registered:
            raise KeyError(f"Agent {agent_id!r} is not registered")
        return dict(self._registered[agent_id])

    def get_foundry_agent_id(self, agent_id: str) -> str:
        """Return the Foundry agent ID for *agent_id*.

        :raises KeyError: If the agent is not registered.
        """
        return self.get_registration(agent_id)["foundry_agent_id"]

    def list_registered_agents(self) -> List[Dict[str, Any]]:
        """Return registration records for all registered agents."""
        return list(self._registered.values())

    @property
    def agent_count(self) -> int:
        """Number of currently registered agents."""
        return len(self._registered)

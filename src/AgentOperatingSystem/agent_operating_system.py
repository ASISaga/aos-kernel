"""AgentOperatingSystem — the kernel entry point.

The :class:`AgentOperatingSystem` class is the top-level façade that wires
together all kernel subsystems:

* **FoundryAgentManager** — agent lifecycle management via Foundry Agent Service.
* **FoundryOrchestrationEngine** — orchestration via Foundry threads/runs.
* **FoundryMessageBridge** — bidirectional message passing.
* **KernelConfig** — configuration from environment / Bicep parameters.

All orchestration is managed natively through the Foundry Agent Service
(``azure-ai-projects`` / ``azure-ai-agents`` SDK).

Typical usage in an Azure Function::

    from AgentOperatingSystem import AgentOperatingSystem

    kernel = AgentOperatingSystem()
    await kernel.initialize()

    # Register an agent with Foundry-native tools
    await kernel.register_agent(
        agent_id="ceo",
        purpose="Strategic leadership and executive decision-making",
        adapter_name="leadership",
        tools=[{"type": "code_interpreter"}, {"type": "file_search"}],
    )

    # Create an orchestration backed by a Foundry thread
    orch = await kernel.create_orchestration(
        agent_ids=["ceo", "cfo"],
        purpose="Quarterly strategic review",
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from AgentOperatingSystem.config import KernelConfig
from AgentOperatingSystem.agents import FoundryAgentManager
from AgentOperatingSystem.orchestration import FoundryOrchestrationEngine
from AgentOperatingSystem.messaging import FoundryMessageBridge
from AgentOperatingSystem.observability import AOSObservabilityProvider
from aos_intelligence.ml import LoRAAdapterRegistry, LoRAInferenceClient, LoRAOrchestrationRouter

logger = logging.getLogger(__name__)


class AgentOperatingSystem:
    """The AOS Kernel — manages agents natively through the Foundry Agent Service.

    :param config: Kernel configuration.  When ``None``, configuration is
        loaded from environment variables.
    :param project_client: An optional ``AIProjectClient`` instance.  When
        ``None``, the kernel operates in local/stub mode suitable for
        testing and development.
    """

    def __init__(
        self,
        config: Optional[KernelConfig] = None,
        project_client: Any = None,
        lora_registry: Optional[LoRAAdapterRegistry] = None,
        inference_client: Any = None,
        observability: Optional[AOSObservabilityProvider] = None,
    ) -> None:
        self.config = config or KernelConfig.from_env()
        self._project_client = project_client
        self._initialized = False

        # Subsystems
        self.agent_manager = FoundryAgentManager(
            project_client=project_client,
            default_model=self.config.default_model,
            subconscious_mcp_url=self.config.subconscious_mcp_url,
        )
        self.orchestration_engine = FoundryOrchestrationEngine(
            project_client=project_client,
            agent_manager=self.agent_manager,
            subconscious_mcp_url=self.config.subconscious_mcp_url,
        )
        self.message_bridge = FoundryMessageBridge(
            agent_manager=self.agent_manager,
            orchestration_engine=self.orchestration_engine,
            subconscious_mcp_url=self.config.subconscious_mcp_url,
        )

        # Multi-LoRA subsystems
        self.lora_registry: LoRAAdapterRegistry = lora_registry or LoRAAdapterRegistry()
        self.lora_inference: LoRAInferenceClient = LoRAInferenceClient(
            registry=self.lora_registry,
            inference_client=inference_client,
        )
        self.lora_router: LoRAOrchestrationRouter = LoRAOrchestrationRouter(registry=self.lora_registry)

        # Observability subsystem
        self.observability: AOSObservabilityProvider = observability or AOSObservabilityProvider(
            service_name=self.config.otel_service_name,
            service_version="6.0.0",
            environment=self.config.environment,
            otlp_endpoint=self.config.otlp_endpoint,
            application_insights_connection_string=self.config.applicationinsights_connection_string,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the kernel and establish Foundry connections.

        When a project client is not provided and a
        ``FOUNDRY_PROJECT_ENDPOINT`` is configured, the kernel attempts
        to create an ``AIProjectClient`` automatically.
        """
        if self._initialized:
            return

        # Auto-create project client from config if not provided
        if self._project_client is None and self.config.foundry_project_endpoint:
            try:
                from AgentOperatingSystem._foundry_internal import _create_project_client

                self._project_client = _create_project_client(
                    endpoint=self.config.foundry_project_endpoint,
                )
                # Wire project client into subsystems
                self.agent_manager.project_client = self._project_client
                self.orchestration_engine.project_client = self._project_client
            except Exception as exc:
                logger.warning("Failed to create AIProjectClient: %s", exc)

        self._initialized = True
        self.observability.setup()
        logger.info(
            "AOS Kernel initialized (environment=%s, foundry=%s)",
            self.config.environment,
            "connected" if self._project_client else "local",
        )

    async def shutdown(self) -> None:
        """Gracefully shut down the kernel."""
        self.observability.shutdown()
        self._initialized = False
        logger.info("AOS Kernel shut down")

    # ------------------------------------------------------------------
    # Agent management (delegates to FoundryAgentManager)
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

        See :meth:`FoundryAgentManager.register_agent` for details.
        """
        return await self.agent_manager.register_agent(
            agent_id=agent_id,
            purpose=purpose,
            name=name,
            adapter_name=adapter_name,
            capabilities=capabilities,
            model=model,
            tools=tools,
            tool_resources=tool_resources,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            metadata=metadata,
        )

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

        See :meth:`FoundryAgentManager.update_agent` for details.
        """
        return await self.agent_manager.update_agent(
            agent_id=agent_id,
            purpose=purpose,
            name=name,
            model=model,
            tools=tools,
            tool_resources=tool_resources,
            temperature=temperature,
            top_p=top_p,
            metadata=metadata,
        )

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        await self.agent_manager.unregister_agent(agent_id)

    # ------------------------------------------------------------------
    # Orchestration (delegates to FoundryOrchestrationEngine)
    # ------------------------------------------------------------------

    async def create_orchestration(
        self,
        agent_ids: List[str],
        purpose: str,
        purpose_scope: str = "",
        context: Optional[Dict[str, Any]] = None,
        workflow: str = "collaborative",
        mcp_servers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a purpose-driven orchestration backed by a Foundry thread.

        See :meth:`FoundryOrchestrationEngine.create_orchestration` for details.
        """
        return await self.orchestration_engine.create_orchestration(
            agent_ids=agent_ids,
            purpose=purpose,
            purpose_scope=purpose_scope,
            context=context,
            workflow=workflow,
            mcp_servers=mcp_servers,
        )

    async def run_agent_turn(
        self,
        orchestration_id: str,
        agent_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Execute a single agent turn via a Foundry run."""
        return await self.orchestration_engine.run_agent_turn(
            orchestration_id=orchestration_id,
            agent_id=agent_id,
            message=message,
        )

    async def get_orchestration_status(self, orchestration_id: str) -> Dict[str, Any]:
        """Get orchestration status."""
        return await self.orchestration_engine.get_status(orchestration_id)

    async def get_thread_messages(self, orchestration_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages from the orchestration's Foundry thread."""
        return await self.orchestration_engine.get_thread_messages(orchestration_id)

    async def get_conversation_from_subconscious(
        self, orchestration_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve persisted conversation history from the subconscious MCP server.

        Returns an empty list when the subconscious URL is not configured or
        the call fails.

        :param orchestration_id: Target orchestration.
        :returns: List of persisted message records, oldest first.
        """
        return await self.message_bridge.get_conversation_from_subconscious(orchestration_id)

    async def stop_orchestration(self, orchestration_id: str) -> None:
        """Stop an orchestration."""
        await self.orchestration_engine.stop_orchestration(orchestration_id)

    async def cancel_orchestration(self, orchestration_id: str) -> None:
        """Cancel an orchestration."""
        await self.orchestration_engine.cancel_orchestration(orchestration_id)

    async def delete_thread(self, orchestration_id: str) -> None:
        """Delete the Foundry thread for an orchestration."""
        await self.orchestration_engine.delete_thread(orchestration_id)

    # ------------------------------------------------------------------
    # Multi-LoRA (delegates to LoRAOrchestrationRouter / LoRAInferenceClient)
    # ------------------------------------------------------------------

    def resolve_lora_adapters(
        self,
        orchestration_type: str,
        step_name: str,
        agent_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the LoRA adapter records for the given orchestration step.

        Used by the Foundry Agent Service to determine which adapters to
        activate before executing a step.  Delegates to
        :class:`~aos_intelligence.ml.LoRAOrchestrationRouter`.

        :param orchestration_type: Orchestration category.
        :param step_name: Step within the orchestration.
        :param agent_ids: Participating agent IDs for persona-based fallback.
        :returns: List of adapter record dicts (empty if no adapters apply).
        """
        return self.lora_router.resolve_adapters(
            orchestration_type=orchestration_type,
            step_name=step_name,
            agent_ids=agent_ids,
        )

    # ------------------------------------------------------------------
    # A2A Agent Tool Enrollment
    # ------------------------------------------------------------------

    def enroll_agent_tools(
        self,
        coordinator_id: str,
        specialist_ids: List[str],
        thread_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Enroll specialist agents as A2A tools for a coordinator agent.

        Iterates through the registered specialist agents and generates
        A2A tool definitions that can be attached to the coordinator's
        Foundry agent, enabling the LLM to dynamically discover, consult,
        and delegate to specialists.

        :param coordinator_id: Agent ID of the coordinator (e.g. ``"ceo"``).
        :param specialist_ids: Agent IDs of specialists to enroll as tools.
        :param thread_id: Optional thread ID for orchestration context injection.
        :returns: List of A2A tool definition dicts suitable for Foundry
            ``create_agent(tools=[...])``.
        :raises KeyError: If the coordinator or a specialist is not registered.
        """
        # Verify coordinator is registered
        self.agent_manager.get_registration(coordinator_id)

        tool_definitions: List[Dict[str, Any]] = []
        for spec_id in specialist_ids:
            record = self.agent_manager.get_registration(spec_id)
            tool_def: Dict[str, Any] = {
                "type": "agent",
                "agent": {
                    "name": record.get("name", spec_id),
                    "description": record["purpose"],
                    "connection_id": f"a2a-connection-{spec_id}",
                    "agent_id": spec_id,
                    "foundry_agent_id": record["foundry_agent_id"],
                },
            }
            if thread_id:
                tool_def["agent"]["thread_id"] = thread_id
            tool_definitions.append(tool_def)

        logger.info(
            "Enrolled %d specialist(s) as A2A tools for coordinator '%s'",
            len(tool_definitions),
            coordinator_id,
        )
        return tool_definitions

    def get_a2a_tool_definitions(
        self,
        agent_ids: List[str],
        thread_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate Foundry-compatible A2A tool definitions for agents.

        :param agent_ids: Agent IDs to generate tool definitions for.
        :param thread_id: Optional thread ID for context injection.
        :returns: List of tool definition dicts.
        """
        definitions: List[Dict[str, Any]] = []
        for agent_id in agent_ids:
            try:
                record = self.agent_manager.get_registration(agent_id)
                definition: Dict[str, Any] = {
                    "type": "agent",
                    "agent": {
                        "name": record.get("name", agent_id),
                        "description": record["purpose"],
                        "connection_id": f"a2a-connection-{agent_id}",
                        "agent_id": agent_id,
                        "foundry_agent_id": record["foundry_agent_id"],
                    },
                }
                if thread_id:
                    definition["agent"]["thread_id"] = thread_id
                definitions.append(definition)
            except KeyError:
                logger.warning(
                    "Agent '%s' not registered — skipping A2A tool generation",
                    agent_id,
                )
        return definitions

    # ------------------------------------------------------------------
    # Messaging (delegates to FoundryMessageBridge)
    # ------------------------------------------------------------------

    async def send_message_to_agent(
        self,
        agent_id: str,
        message: str,
        orchestration_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to a PurposeDrivenAgent via the bridge."""
        return await self.message_bridge.deliver_to_agent(
            agent_id=agent_id,
            message=message,
            orchestration_id=orchestration_id,
        )

    async def send_message_to_foundry(
        self,
        agent_id: str,
        message: str,
        orchestration_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a PurposeDrivenAgent response to Foundry."""
        return await self.message_bridge.send_to_foundry(
            agent_id=agent_id,
            message=message,
            orchestration_id=orchestration_id,
        )

    async def broadcast_purpose_alignment(
        self,
        orchestration_id: str,
        purpose: str,
        purpose_scope: str = "",
    ) -> List[Dict[str, Any]]:
        """Broadcast purpose alignment to all agents in an orchestration."""
        return await self.message_bridge.broadcast_purpose_alignment(
            orchestration_id=orchestration_id,
            purpose=purpose,
            purpose_scope=purpose_scope,
        )

    # ------------------------------------------------------------------
    # Health / Status
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Return kernel health status."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "environment": self.config.environment,
            "foundry_connected": self._project_client is not None,
            "agents_registered": self.agent_manager.agent_count,
            "active_orchestrations": self.orchestration_engine.orchestration_count,
            "messages_bridged": self.message_bridge.message_count,
            "lora_adapters_registered": self.lora_registry.adapter_count,
            "subconscious_connected": bool(self.config.subconscious_mcp_url),
            "observability": self.observability.get_status(),
        }

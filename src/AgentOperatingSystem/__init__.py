"""AOS Kernel — Agent Operating System Kernel.

All orchestration is managed natively through the Foundry Agent Service
(``azure-ai-projects`` / ``azure-ai-agents`` SDK).

Core components:

- :class:`AgentOperatingSystem` — the kernel entry point
- :class:`KernelConfig` — configuration from environment / Bicep
- :class:`FoundryAgentManager` — agent lifecycle management via Foundry
- :class:`FoundryOrchestrationEngine` — orchestration via Foundry threads/runs
- :class:`FoundryMessageBridge` — bidirectional PDA ↔ Foundry messaging

Observability:

- :class:`AOSObservabilityProvider` — OTel-based traces, metrics, logs

Multi-LoRA components (from ``aos-intelligence``):

- :class:`~aos_intelligence.ml.LoRAAdapterRegistry`
- :class:`~aos_intelligence.ml.LoRAInferenceClient`
- :class:`~aos_intelligence.ml.LoRAOrchestrationRouter`
"""

__version__ = "6.0.0"

from AgentOperatingSystem.agent_operating_system import AgentOperatingSystem
from AgentOperatingSystem.config import KernelConfig
from AgentOperatingSystem.agents import FoundryAgentManager
from AgentOperatingSystem.orchestration import FoundryOrchestrationEngine
from AgentOperatingSystem.messaging import FoundryMessageBridge
from AgentOperatingSystem.observability import AOSObservabilityProvider
from aos_intelligence.ml import LoRAAdapterRegistry, LoRAInferenceClient, LoRAOrchestrationRouter

__all__ = [
    "AgentOperatingSystem",
    "KernelConfig",
    "FoundryAgentManager",
    "FoundryOrchestrationEngine",
    "FoundryMessageBridge",
    "AOSObservabilityProvider",
    "LoRAAdapterRegistry",
    "LoRAInferenceClient",
    "LoRAOrchestrationRouter",
]

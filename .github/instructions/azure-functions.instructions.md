---
applyTo: "src/**/*.py,tests/**/*.py"
description: "AOS kernel patterns: Foundry Agent Service, orchestration, messaging, and A2A tool enrollment"
---

# AOS Kernel Patterns

## Kernel Initialization

The kernel façade (`AgentOperatingSystem`) wires together all subsystems. Always initialize before use:

```python
from AgentOperatingSystem import AgentOperatingSystem

kernel = AgentOperatingSystem()
await kernel.initialize()
```

When `FOUNDRY_PROJECT_ENDPOINT` is set, the kernel connects to the Azure AI Foundry Agent Service automatically.

## Agent Registration

```python
await kernel.register_agent(
    agent_id="ceo",
    purpose="Strategic leadership and executive decision-making",
    name="CEO Agent",
    adapter_name="leadership",
    capabilities=["orchestration", "decision-making"],
    model="gpt-4o",
)
```

Delegates to `FoundryAgentManager.register_agent`.

## Orchestration Lifecycle

```python
# Create a collaborative (default) orchestration
orch = await kernel.create_orchestration(
    agent_ids=["ceo", "cfo"],
    purpose="Quarterly strategic review",
    purpose_scope="C-suite strategic alignment",
    workflow="collaborative",   # "sequential" | "hierarchical" | "collaborative"
    context={"fiscal_year": 2026},
)

# Run one agent turn
result = await kernel.run_agent_turn(
    orchestration_id=orch["orchestration_id"],
    agent_id="ceo",
    message="Begin the strategic review",
)

# Stop / cancel
await kernel.stop_orchestration(orch["orchestration_id"])
await kernel.cancel_orchestration(orch["orchestration_id"])
```

## A2A Tool Enrollment

Enroll specialists as Foundry-compatible A2A tool definitions for a coordinator:

```python
tool_defs = kernel.enroll_agent_tools(
    coordinator_id="ceo",
    specialist_ids=["cfo", "cto", "cso"],
    thread_id="thread-001",   # optional — injects orchestration context
)
# Pass tool_defs to Foundry create_agent(tools=tool_defs)
```

## Message Bridge

```python
# Deliver to a PurposeDrivenAgent
await kernel.send_message_to_agent(
    agent_id="cfo",
    message="Provide Q1 budget summary",
    orchestration_id=orch_id,
)

# Send agent response back to Foundry
await kernel.send_message_to_foundry(
    agent_id="cfo",
    message="Q1 budget: $4.2M operating, $1.1M capex",
    orchestration_id=orch_id,
)

# Broadcast purpose alignment to all agents in an orchestration
await kernel.broadcast_purpose_alignment(
    orchestration_id=orch_id,
    purpose="Drive strategic review",
    purpose_scope="C-suite alignment",
)
```

## Multi-LoRA Adapter Resolution

```python
adapters = kernel.resolve_lora_adapters(
    orchestration_type="strategic",
    step_name="analysis",
    agent_ids=["ceo", "cfo"],
)
# Returns list of adapter record dicts for Foundry to activate
```

## Health Check

```python
health = await kernel.health_check()
# {
#   "status": "healthy",
#   "environment": "production",
#   "foundry_connected": True,
#   "agents_registered": 5,
#   "active_orchestrations": 2,
#   "messages_bridged": 42,
#   "lora_adapters_registered": 3,
# }
```

## Subsystem Access

Access subsystems directly for advanced use:

```python
kernel.agent_manager          # FoundryAgentManager
kernel.orchestration_engine   # FoundryOrchestrationEngine
kernel.message_bridge         # FoundryMessageBridge
kernel.lora_registry          # LoRAAdapterRegistry
kernel.lora_inference         # LoRAInferenceClient
kernel.lora_router            # LoRAOrchestrationRouter
```

## Validation

```bash
pytest tests/ -v --asyncio-mode=auto    # Run all tests
pytest tests/test_kernel.py -v          # Kernel façade tests
pylint src/AgentOperatingSystem          # Lint
```

## Related Documentation

→ **Repository spec**: `.github/specs/repository.md`  
→ **Python standards**: `.github/instructions/python.instructions.md`  
→ **Architecture**: `.github/instructions/architecture.instructions.md`

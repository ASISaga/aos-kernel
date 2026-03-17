# aos-kernel

The Agent Operating System Kernel — Foundry Agent Service native orchestration, messaging, agent management, and all supporting system services.

## Overview

`aos-kernel` is the OS kernel for the Agent Operating System (AOS). It provides the core infrastructure that perpetual agents run on, natively integrated with the Azure AI Foundry Agent Service:

- **Foundry Agent Service** — Agent CRUD, thread/run lifecycle via `azure-ai-projects` / `azure-ai-agents` SDK
- **Foundry-native tools** — code_interpreter, file_search, bing_grounding, azure_ai_search, openapi, function
- **A2A Tool Enrollment** — Enroll specialist agents as A2A tools for coordinator agents
- **Orchestration Engine** — Purpose-driven orchestration via Foundry threads and runs
- **Messaging** — Bidirectional message bridge (PurposeDrivenAgent ↔ Foundry threads)
- **Multi-LoRA** — LoRA adapter registry, inference client, orchestration router
- **Reliability** — Circuit breakers, retry policies, fault tolerance patterns
- **Observability** — Logging, metrics, distributed tracing (OpenTelemetry)
- **Governance** — Audit, compliance, risk management

## Installation

```bash
pip install aos-kernel

# With Azure service backends
pip install aos-kernel[azure]

# With all optional dependencies
pip install aos-kernel[full]
```

## Quick Start

```python
from AgentOperatingSystem import AgentOperatingSystem

kernel = AgentOperatingSystem()
await kernel.initialize()

# Register agents with Foundry-native tools
await kernel.register_agent(
    "ceo", "Strategic leadership",
    adapter_name="leadership",
    tools=[{"type": "code_interpreter"}, {"type": "file_search"}],
    tool_resources={"file_search": {"vector_store_ids": ["vs-001"]}},
    temperature=0.7,
)
await kernel.register_agent("cfo", "Financial oversight", adapter_name="finance")

# Create an orchestration backed by a Foundry thread
orch = await kernel.create_orchestration(
    agent_ids=["ceo", "cfo"],
    purpose="Quarterly strategic review",
)

# Run agent turns (posts messages to Foundry thread, creates runs)
turn = await kernel.run_agent_turn(
    orch["orchestration_id"], "ceo", "Set the agenda",
)

# Retrieve thread messages from Foundry
messages = await kernel.get_thread_messages(orch["orchestration_id"])

# Enroll specialists as A2A tools for a coordinator
tools = kernel.enroll_agent_tools(
    coordinator_id="ceo",
    specialist_ids=["cfo"],
    thread_id="thread-001",
)

# Update agent configuration
await kernel.update_agent("ceo", temperature=0.5, tools=[{"type": "code_interpreter"}])
```

## Architecture

The kernel provides system services that perpetual agents depend on. All orchestration flows through the Foundry Agent Service natively via `azure-ai-projects` and `azure-ai-agents` SDK:

```
┌──────────────────────────────────────────────────┐
│              Agent Operating System               │
│          (azure-ai-projects SDK native)           │
├────────────────┬────────────────┬────────────────┤
│  FoundryAgent  │  A2A Tool     │   Multi-LoRA   │
│  Manager       │  Enrollment   │   Inference    │
├────────────────┼────────────────┼────────────────┤
│  Orchestration │  Message      │  Observability │
│  Engine        │  Bridge       │  (OTel)        │
│  (Threads/Runs)│  (Thread Msgs)│                │
└────────────────┴────────────────┴────────────────┘
```

### Core Dependencies

| Package | Purpose |
|---|---|
| `azure-ai-projects>=2.0.0b4` | Primary SDK — AIProjectClient for Foundry Agent Service |
| `azure-ai-agents>=1.1.0` | AgentsClient — agent CRUD, threads, messages, runs |
| `azure-identity>=1.25.0` | Managed Identity authentication for Function App ↔ Foundry |
| `purpose-driven-agent>=1.0.0` | Foundational agent base class |
| `leadership-agent>=1.0.0` | Leadership agent with orchestration capabilities |
| `aos-intelligence>=2.0.0` | ML layer — LoRA adapters, inference, training |

### Foundry Agent Service Capabilities

| Capability | Kernel Integration |
|---|---|
| Agent CRUD | `FoundryAgentManager.register_agent()` / `update_agent()` / `unregister_agent()` |
| Thread management | `FoundryOrchestrationEngine.create_orchestration()` / `delete_thread()` |
| Message posting | `FoundryOrchestrationEngine.run_agent_turn()` / `get_thread_messages()` |
| Run lifecycle | `create_and_process_run` (automatic polling) |
| code_interpreter | Pass `tools=[{"type": "code_interpreter"}]` to `register_agent()` |
| file_search | Pass `tools=[{"type": "file_search"}]` with `tool_resources` |
| bing_grounding | Pass `tools=[{"type": "bing_grounding", ...}]` |
| azure_ai_search | Pass `tools=[{"type": "azure_ai_search", ...}]` |
| A2A tools | `enroll_agent_tools()` — specialists as callable tools for coordinators |
| Temperature/top_p | Pass `temperature`/`top_p` to `register_agent()` |
| Response format | Pass `response_format="json_object"` to `register_agent()` |
| Agent metadata | Pass `metadata={"key": "value"}` to `register_agent()` |

## Repository Structure

```
src/AgentOperatingSystem/   # Kernel source code
tests/                      # Kernel tests (128 tests)
examples/                   # Usage examples
docs/                       # Kernel documentation
.github/                    # CI/CD, Copilot skills, prompts, instructions
```

## Related Repositories

- [purpose-driven-agent](https://github.com/ASISaga/purpose-driven-agent) — Foundational agent base class (code-only library)
- [leadership-agent](https://github.com/ASISaga/leadership-agent) — Leadership agent with orchestration (code-only library)
- [ceo-agent](https://github.com/ASISaga/ceo-agent) — CEO agent (executive + leadership)
- [cfo-agent](https://github.com/ASISaga/cfo-agent) — CFO agent (finance + leadership)
- [cto-agent](https://github.com/ASISaga/cto-agent) — CTO agent (technology + leadership)
- [cso-agent](https://github.com/ASISaga/cso-agent) — CSO agent (security + leadership)
- [cmo-agent](https://github.com/ASISaga/cmo-agent) — CMO agent (marketing + leadership)
- [aos-intelligence](https://github.com/ASISaga/aos-intelligence) — ML/AI intelligence layer
- [aos-infrastructure](https://github.com/ASISaga/aos-infrastructure) — Infrastructure deployment
- [aos-dispatcher](https://github.com/ASISaga/aos-dispatcher) — Orchestration API
- [aos-realm-of-agents](https://github.com/ASISaga/aos-realm-of-agents) — Agent catalog
- [aos-mcp-servers](https://github.com/ASISaga/aos-mcp-servers) — MCPServers function app
- [aos-client-sdk](https://github.com/ASISaga/aos-client-sdk) — Client SDK for external applications
- [business-infinity](https://github.com/ASISaga/business-infinity) — Example client application

## License

Apache License 2.0 — see [LICENSE](LICENSE)

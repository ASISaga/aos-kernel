# AOS Kernel Architecture

The AOS Kernel provides the core runtime infrastructure for the Agent Operating System, natively integrated with the Azure AI Foundry Agent Service.

## System Architecture

All orchestration flows through the Foundry Agent Service natively via `azure-ai-projects` and `azure-ai-agents` SDK. The kernel does not use any legacy custom orchestration framework.

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentOperatingSystem                       │
│                     (Kernel Façade)                           │
├───────────────┬───────────────┬───────────────┬─────────────┤
│ FoundryAgent  │ Orchestration │   Message     │  Multi-LoRA │
│ Manager       │ Engine        │   Bridge      │  (aos-intel)│
├───────────────┴───────────────┴───────────────┴─────────────┤
│              azure-ai-projects / azure-ai-agents              │
│         (AIProjectClient → AgentsClient)                      │
├─────────────────────────────────────────────────────────────┤
│          Azure AI Foundry Agent Service                       │
│   Agents · Threads · Messages · Runs · Tools · Files         │
└─────────────────────────────────────────────────────────────┘
```

## Kernel Modules

| Module | Description |
|--------|-------------|
| `agent_operating_system.py` | Top-level kernel façade |
| `_foundry_internal.py` | AIProjectClient / AgentsClient creation helpers |
| `agents/` | `FoundryAgentManager` — agent CRUD via Foundry |
| `orchestration/` | `FoundryOrchestrationEngine` — thread/run lifecycle |
| `messaging/` | `FoundryMessageBridge` — bidirectional message passing |
| `config/` | `KernelConfig` — Pydantic config from environment |
| `auth/` | Authentication & authorization |
| `mcp/` | Model Context Protocol integration |
| `reliability/` | Circuit breakers, retry policies |
| `observability/` | Logging, metrics, distributed tracing (OpenTelemetry) |
| `governance/` | Audit, compliance, risk management |
| `storage/` | Azure Storage services |

## Foundry Agent Service Integration

The kernel uses the Foundry Agent Service SDK directly:

| Foundry Operation | Kernel Method |
|-------------------|---------------|
| `agents.create_agent()` | `FoundryAgentManager.register_agent()` |
| `agents.update_agent()` | `FoundryAgentManager.update_agent()` |
| `agents.delete_agent()` | `FoundryAgentManager.unregister_agent()` |
| `agents.create_thread()` | `FoundryOrchestrationEngine.create_orchestration()` |
| `agents.create_message()` | `FoundryOrchestrationEngine.run_agent_turn()` |
| `agents.create_and_process_run()` | `FoundryOrchestrationEngine.run_agent_turn()` |
| `agents.list_messages()` | `FoundryOrchestrationEngine.get_thread_messages()` |
| `agents.list_runs()` / `cancel_run()` | `FoundryOrchestrationEngine.stop_orchestration()` |
| `agents.delete_thread()` | `FoundryOrchestrationEngine.delete_thread()` |

## Key Design Principles

1. **Foundry-native** — All agent/orchestration operations use `azure-ai-projects` SDK directly; no wrapper layers
2. **Perpetual agents** — Agents register once and run indefinitely, awakening on events
3. **Purpose-driven** — Every orchestration has a stated purpose and optional scope
4. **Thin façade** — `AgentOperatingSystem` delegates to subsystem managers
5. **Async throughout** — All I/O operations are async

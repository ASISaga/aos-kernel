# aos-kernel Repository Specification

**Version**: 1.0.0  
**Status**: Active  
**Last Updated**: 2026-03-07

## Overview

`aos-kernel` is the OS kernel for the Agent Operating System (AOS). It provides the core infrastructure that perpetual agents run on: Foundry Agent Service integration, A2A tool enrollment, orchestration engine, message bridge, Multi-LoRA inference, reliability patterns, observability, and governance.

## Scope

- Repository role in the AOS ecosystem
- Technology stack and coding patterns
- Testing and validation workflows
- Key design principles for kernel contributors

## Repository Role

| Concern | Owner |
|---------|-------|
| Agent registration, thread/run lifecycle via Azure AI Foundry | **aos-kernel** (`FoundryAgentManager`) |
| Orchestration lifecycle (create, run, stop, cancel) | **aos-kernel** (`FoundryOrchestrationEngine`) |
| Bidirectional message passing (PurposeDrivenAgent ↔ Foundry) | **aos-kernel** (`FoundryMessageBridge`) |
| A2A tool enrollment — specialists as tools for coordinators | **aos-kernel** (`AgentOperatingSystem.enroll_agent_tools`) |
| Multi-LoRA adapter registry, inference, routing | **aos-kernel** (via `aos-intelligence`) |
| Reliability, observability, governance | **aos-kernel** (subsystem modules) |
| Agent catalog (C-suite agents) | `aos-realm-of-agents` |
| Client-facing orchestration API | `aos-dispatcher` |
| Client SDK for external applications | `aos-client-sdk` |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.10+ |
| Primary SDK | `azure-ai-projects>=2.0.0b4` — Foundry Agent Service |
| Agent SDK | `azure-ai-agents>=1.1.0` — `AgentsClient` within AI Project |
| Auth | `azure-identity>=1.25.0` — Managed Identity / DefaultAzureCredential |
| Agent base | `purpose-driven-agent>=1.0.0` — `PurposeDrivenAgent` base class |
| Orchestration | `leadership-agent>=1.0.0` — leadership + orchestration capabilities |
| ML/LoRA | `aos-intelligence>=2.0.0` — LoRA adapters, inference, training |
| Async | Python `asyncio` |
| Tests | `pytest` + `pytest-asyncio` |
| Linter | `pylint` (min score 5.0/10, configured in `pyproject.toml`) |
| Build / deploy | `azure.yaml` (Azure Developer CLI) |

## Directory Structure

```
aos-kernel/
├── src/AgentOperatingSystem/
│   ├── agent_operating_system.py  # Top-level kernel façade
│   ├── _foundry_internal.py       # Internal Foundry service wiring
│   ├── agents/                    # FoundryAgentManager — agent registration
│   ├── orchestration/             # FoundryOrchestrationEngine — lifecycle
│   ├── messaging/                 # FoundryMessageBridge — message passing
│   ├── config/                    # KernelConfig — environment configuration
│   ├── auth/                      # Authentication & authorization
│   ├── mcp/                       # Model Context Protocol integration
│   ├── reliability/               # Circuit breakers, retry policies
│   ├── observability/             # Logging, metrics, distributed tracing (OpenTelemetry)
│   ├── governance/                # Audit, compliance, risk management
│   └── storage/                   # Azure Storage services
├── tests/                         # Kernel tests (pytest + pytest-asyncio)
├── examples/                      # Usage examples
├── docs/                          # Kernel documentation
├── pyproject.toml                 # Build config, dependencies, pytest/pylint settings
└── azure.yaml                     # Azure Developer CLI deployment config
```

## Core Patterns

### Kernel Initialization

```python
from AgentOperatingSystem import AgentOperatingSystem

kernel = AgentOperatingSystem()
await kernel.initialize()
```

When `FOUNDRY_PROJECT_ENDPOINT` is set in the environment, the kernel automatically creates an `AIProjectClient` and connects to the Foundry Agent Service.

### Agent Registration

```python
await kernel.register_agent(
    agent_id="ceo",
    purpose="Strategic leadership and executive decision-making",
    name="CEO Agent",
    adapter_name="leadership",
)
```

### Orchestration Lifecycle

```python
# Create a purpose-driven orchestration
orch = await kernel.create_orchestration(
    agent_ids=["ceo", "cfo"],
    purpose="Quarterly strategic review",
    purpose_scope="C-suite strategic alignment",
    workflow="collaborative",  # or "sequential", "hierarchical"
)

# Run a single agent turn
result = await kernel.run_agent_turn(
    orchestration_id=orch["orchestration_id"],
    agent_id="ceo",
    message="Initiate strategic review",
)

# Stop or cancel
await kernel.stop_orchestration(orch["orchestration_id"])
```

### A2A Tool Enrollment

```python
# Enroll specialist agents as A2A tools for the CEO coordinator
tools = kernel.enroll_agent_tools(
    coordinator_id="ceo",
    specialist_ids=["cfo", "cto", "cso"],
    thread_id="thread-001",
)
# `tools` is a list of Foundry-compatible tool definition dicts
```

### Multi-LoRA Adapter Resolution

```python
adapters = kernel.resolve_lora_adapters(
    orchestration_type="strategic",
    step_name="analysis",
    agent_ids=["ceo", "cfo"],
)
```

### Health Check

```python
status = await kernel.health_check()
# Returns: initialized, environment, foundry_connected, agents_registered,
#          active_orchestrations, messages_bridged, lora_adapters_registered
```

## Testing Workflow

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v --asyncio-mode=auto

# Run with coverage
pytest tests/ -v --asyncio-mode=auto --cov=AgentOperatingSystem --cov-report=term-missing

# Run a specific test module
pytest tests/test_kernel.py -v

# Lint
pylint src/AgentOperatingSystem --fail-under=5.0

# Type-check (optional)
mypy src/AgentOperatingSystem
```

**CI**: GitHub Actions (`ci.yml`) runs `pytest` across Python 3.10, 3.11, and 3.12 on every push/PR to `main` and `develop`, plus a `pylint` lint step.

→ **CI workflow**: `.github/workflows/ci.yml`

## Related Repositories

| Repository | Role |
|-----------|------|
| [purpose-driven-agent](https://github.com/ASISaga/purpose-driven-agent) | Foundational `PurposeDrivenAgent` base class |
| [leadership-agent](https://github.com/ASISaga/leadership-agent) | Leadership agent with orchestration capabilities |
| [ceo-agent](https://github.com/ASISaga/ceo-agent) | CEO agent (executive + leadership) |
| [cfo-agent](https://github.com/ASISaga/cfo-agent) | CFO agent (finance + leadership) |
| [cto-agent](https://github.com/ASISaga/cto-agent) | CTO agent (technology + leadership) |
| [aos-intelligence](https://github.com/ASISaga/aos-intelligence) | ML/AI intelligence layer — LoRA adapters, inference |
| [aos-dispatcher](https://github.com/ASISaga/aos-dispatcher) | Orchestration API (delegates to kernel) |
| [aos-realm-of-agents](https://github.com/ASISaga/aos-realm-of-agents) | Agent catalog |
| [aos-client-sdk](https://github.com/ASISaga/aos-client-sdk) | Client SDK for external applications |
| [aos-infrastructure](https://github.com/ASISaga/aos-infrastructure) | Infrastructure deployment (Bicep) |

## Key Design Principles

1. **Foundry-first** — All orchestration is managed exclusively by the Azure AI Foundry Agent Service; no legacy custom orchestration path
2. **Perpetual agents** — Agents register once and run indefinitely, awakening on events
3. **Purpose-driven** — Every orchestration has a stated `purpose` and optional `purpose_scope`; agents work toward it continuously
4. **Thin façade** — `AgentOperatingSystem` delegates to subsystem managers; keep the façade thin and subsystems focused
5. **Async throughout** — All I/O operations are async; use `await` for all service calls

## References

→ **Agent framework spec**: `.github/specs/agent-intelligence-framework.md`  
→ **Conventional tools**: `.github/docs/conventional-tools.md`  
→ **Python coding standards**: `.github/instructions/python.instructions.md`  
→ **Architecture instructions**: `.github/instructions/architecture.instructions.md`  
→ **Development workflow**: `.github/instructions/development.instructions.md`

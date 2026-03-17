---
applyTo: "src/**/*.py,tests/**/*.py"
description: "AOS kernel architecture overview and technology stack reference"
---

# Architecture and Technology Stack

## Core Concept: Perpetual vs Task-Based

**Agent Operating System (AOS)** is a production-ready operating system for AI agents, built on Microsoft Azure and the Foundry Agent Service (`azure-ai-projects` / `azure-ai-agents` SDK). The key architectural difference from traditional AI orchestration frameworks is **PERSISTENCE** - agents are perpetual entities that run indefinitely, not temporary task-based sessions.

- **Traditional frameworks**: Temporary sessions that start, execute, and terminate
- **AOS**: Perpetual agents that register once and run indefinitely, awakening on events
- **State persists** across the agent's entire lifetime via ContextMCPServer

## Repository Structure

```
aos-kernel/
├── src/AgentOperatingSystem/
│   ├── agent_operating_system.py  # Top-level kernel façade
│   ├── _foundry_internal.py       # AIProjectClient / AgentsClient creation
│   ├── agents/                    # FoundryAgentManager — agent CRUD via Foundry
│   ├── orchestration/             # FoundryOrchestrationEngine — thread/run lifecycle
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
└── pyproject.toml                 # Build config, dependencies, pytest/pylint settings
```

## Technology Stack

- **Language**: Python 3.10+
- **Platform**: Microsoft Azure (Functions, Service Bus, Storage, etc.)
- **Primary SDK**: `azure-ai-projects>=2.0.0b4` — `AIProjectClient` for Foundry Agent Service
- **Agent SDK**: `azure-ai-agents>=1.1.0` — `AgentsClient` (agent CRUD, threads, messages, runs)
- **Async**: Asyncio for concurrent operations
- **Testing**: pytest with pytest-asyncio
- **Dependencies**: See pyproject.toml

## Foundry Agent Service Integration

The kernel uses the Foundry Agent Service SDK directly for all agent/orchestration operations:

- **Agent CRUD**: `project_client.agents.create_agent()` / `update_agent()` / `delete_agent()`
- **Thread management**: `create_thread()` / `delete_thread()`
- **Message posting**: `create_message(thread_id, role, content)`
- **Run lifecycle**: `create_and_process_run(thread_id, assistant_id)`
- **Foundry tools**: `code_interpreter`, `file_search`, `bing_grounding`, `azure_ai_search`, `openapi`, `function`

## Azure Integration

AOS heavily uses Azure services:

- **Azure AI Foundry** for agent service (primary)
- **Azure Functions** for deployment
- **Azure Service Bus** for messaging
- **Azure Storage** (Blob, Table, Queue) for persistence
- **Azure Key Vault** for secrets

## MCP (Model Context Protocol)

AOS implements MCP for tool and resource access:

- `src/AgentOperatingSystem/mcp/` - MCP implementation
- **ContextMCPServer** for state preservation
- Domain-specific tools and access to contemporary software systems

## Important Files to Know

### Core Entry Points

- `src/AgentOperatingSystem/agent_operating_system.py` - Main AOS kernel façade
- `src/AgentOperatingSystem/__init__.py` - Package exports
- `src/AgentOperatingSystem/_foundry_internal.py` - AIProjectClient creation

### Key Documentation

- `README.md` - Main project README with overview
- `docs/architecture.md` - Architecture documentation
- `docs/api-reference.md` - API reference
- `.github/specs/repository.md` - Repository specification

### Configuration

- `pyproject.toml` - Python project configuration and dependencies
- `azure.yaml` - Azure Developer CLI deployment config

## Key Resources

- **Repository**: https://github.com/ASISaga/aos-kernel
- **Issues**: https://github.com/ASISaga/aos-kernel/issues
- **Azure AI Foundry**: https://learn.microsoft.com/azure/ai-studio/
- **azure-ai-projects SDK**: https://pypi.org/project/azure-ai-projects/
- **azure-ai-agents SDK**: https://pypi.org/project/azure-ai-agents/
- **MCP Protocol**: https://modelcontextprotocol.io/

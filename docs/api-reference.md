# AOS Kernel API Reference

## Core Classes

### AgentOperatingSystem
Main kernel façade. Entry point for the OS. Delegates to subsystems.

**Lifecycle:**
- `initialize()` — Initialize kernel, auto-create `AIProjectClient` from config
- `shutdown()` — Graceful shutdown

**Agent Management:**
- `register_agent(agent_id, purpose, ...)` — Register agent with Foundry Agent Service
- `update_agent(agent_id, ...)` — Update agent configuration in Foundry
- `unregister_agent(agent_id)` — Delete agent from Foundry

**Orchestration:**
- `create_orchestration(agent_ids, purpose, ...)` — Create orchestration backed by Foundry thread
- `run_agent_turn(orchestration_id, agent_id, message)` — Execute agent turn via Foundry run
- `get_orchestration_status(orchestration_id)` — Get orchestration status
- `get_thread_messages(orchestration_id)` — Retrieve messages from Foundry thread
- `stop_orchestration(orchestration_id)` — Stop orchestration, cancel in-progress runs
- `cancel_orchestration(orchestration_id)` — Cancel orchestration
- `delete_thread(orchestration_id)` — Delete Foundry thread

**A2A Tool Enrollment:**
- `enroll_agent_tools(coordinator_id, specialist_ids, ...)` — Enroll specialists as A2A tools
- `get_a2a_tool_definitions(agent_ids, ...)` — Generate tool definitions

**Messaging:**
- `send_message_to_agent(agent_id, message, ...)` — Deliver to PurposeDrivenAgent
- `send_message_to_foundry(agent_id, message, ...)` — Send to Foundry thread
- `broadcast_purpose_alignment(orchestration_id, purpose, ...)` — Broadcast alignment

**Multi-LoRA:**
- `resolve_lora_adapters(orchestration_type, step_name, ...)` — Resolve LoRA adapters

**Health:**
- `health_check()` — Kernel health status

### FoundryAgentManager
Agent lifecycle management via Foundry Agent Service (`project_client.agents`).

### FoundryOrchestrationEngine
Orchestration lifecycle via Foundry threads and runs.

### FoundryMessageBridge
Bidirectional message bridge (PurposeDrivenAgent ↔ Foundry threads).

### KernelConfig
Pydantic configuration model. Loads from environment variables.

## Foundry-Native Tool Types

| Tool Type | Description |
|-----------|-------------|
| `code_interpreter` | Execute Python code in a sandboxed environment |
| `file_search` | Search uploaded files using vector stores |
| `bing_grounding` | Web search via Bing |
| `azure_ai_search` | RAG via Azure AI Search |
| `openapi` | Call external APIs via OpenAPI specs |
| `function` | Custom function calling |

## Multi-LoRA (from aos-intelligence)

- `LoRAAdapterRegistry` — Register and look up LoRA adapters
- `LoRAInferenceClient` — Run inference with LoRA adapters
- `LoRAOrchestrationRouter` — Route adapters for orchestration steps

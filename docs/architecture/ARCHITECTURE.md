# Agent Operating System (AOS) - Architecture

**Version:** 2025.1.2  
**Status:** Production  
**Last Updated:** December 25, 2025

---

## 📖 Table of Contents

- [Executive Summary](#executive-summary)
- [System Overview](#system-overview)
- [Architectural Layers](#architectural-layers)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Deployment Architecture](#deployment-architecture)
- [Technology Stack](#technology-stack)
- [Design Principles](#design-principles)
- [Architectural Patterns](#architectural-patterns)
- [Scalability Architecture](#scalability-architecture)
- [Security Architecture](#security-architecture)
- [Observability Architecture](#observability-architecture)
- [Decision Records](#decision-records)

---

## 🎯 Executive Summary

The **Agent Operating System (AOS)** is a complete, production-grade operating system for AI agents built on Microsoft Azure and the Azure AI Foundry Agent Service. Just as traditional operating systems provide foundational infrastructure for applications, AOS provides the **kernel, system services, runtime environment, and application framework** for autonomous AI agents.

### The Core Architectural Difference: Perpetual vs Task-Based

**The fundamental architectural principle of AOS is PERSISTENCE.**

Traditional AI frameworks use a **task-based session model**:
- Agents are created for specific tasks
- Agents execute and then terminate
- State is lost between sessions
- Manual lifecycle management required

AOS uses an **perpetual persistent model**:
- Agents are registered once and run indefinitely
- Agents sleep when idle, awaken on events
- State persists across the agent's entire lifetime
- Event-driven, automatic lifecycle management

This architectural choice makes AOS a true "operating system" - agents are like daemon processes that continuously run, respond to events, and maintain state, rather than short-lived scripts that execute and exit.

### Key Architectural Characteristics

- **Perpetual Architecture** - Agents run indefinitely as persistent entities
- **Event-Driven** - Agents awaken automatically in response to events
- **Persistent State** - Agent context preserved across all interactions
- **Layered Architecture** - Clear separation between kernel, services, and applications
- **Cloud-Native** - Designed for Azure, distributed and scalable
- **Modular** - Loosely coupled components with well-defined interfaces
- **Observable** - Built-in instrumentation at every layer
- **Secure** - Security by design with defense in depth
- **Reliable** - Fault tolerance and resilience patterns throughout

---

## 🏗️ System Overview

### Conceptual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
│              Business Applications & Custom Agents              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │   CEO      │  │    CFO     │  │    CTO     │  + Custom     │
│  │   Agent    │  │   Agent    │  │   Agent    │    Agents     │
│  │ [PERPETUAL]│  │ [PERPETUAL]│  │ [PERPETUAL]│  [PERPETUAL]  │
│  └────────────┘  └────────────┘  └────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                    ↕ System Calls (Python API)
┌─────────────────────────────────────────────────────────────────┐
│                   SYSTEM SERVICE LAYER                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Core Services                                           │  │
│  │  • Auth & Authorization  • Storage Management           │  │
│  │  • Message Bus           • Environment & Config         │  │
│  │  • Event Distribution    • State Persistence            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Advanced Services                                       │  │
│  │  • ML Pipeline           • MCP Integration              │  │
│  │  • Knowledge & Learning  • Governance & Audit           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Cross-Cutting Services                                  │  │
│  │  • Reliability           • Observability                │  │
│  │  • Extensibility         • Platform Services            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    ↕ Service APIs
┌─────────────────────────────────────────────────────────────────┐
│                        KERNEL LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Orchestration Engine  │  Agent Lifecycle Manager        │  │
│  │  [Event Router]        │  [Perpetual Manager]            │  │
│  ├────────────────────────┼────────────────────────────────┤  │
│  │  Resource Scheduler    │  State Machine Manager         │  │
│  ├────────────────────────┼────────────────────────────────┤  │
│  │  Event Bus             │  Policy Enforcement Engine     │  │
│  │  [Pub/Sub]             │  [Event-Driven]                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    ↕ Azure SDK & APIs
┌─────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                          │
│              Microsoft Azure Cloud Platform                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Service Bus  │  Storage  │  ML  │  Monitor  │  AD      │  │
│  │  [Events]     │ [State]   │      │           │          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 Architectural Layers

### Layer 1: Infrastructure Layer

**Purpose:** Cloud infrastructure and Azure services

**Components:**
- Azure Service Bus (messaging backbone)
- Azure Storage (Blob, Table, Queue)
- Azure Cosmos DB (document storage)
- Azure Machine Learning (ML workloads)
- Azure Monitor & Application Insights (observability)
- Azure AD & Key Vault (identity & secrets)
- Azure Functions (serverless compute)

**Responsibilities:**
- Provide scalable cloud resources
- Handle infrastructure-level reliability
- Manage geographic distribution
- Provide compliance and security

### Layer 2: Kernel Layer

**Purpose:** Core operating system services

**Components:**
- **Orchestration Engine** (`orchestration/`) - Workflow and agent coordination
- **Agent Lifecycle Manager** (`agents/`) - Always-on agent management
- **Resource Scheduler** - Resource allocation and scheduling
- **State Machine Manager** (`reliability/state_machine.py`) - Workflow state management
- **Event Bus** (`messaging/`) - Event distribution and agent awakening
- **Policy Enforcement Engine** (`governance/`) - Runtime policy checks

**Responsibilities:**
- Agent lifecycle management (register, run indefinitely, monitor, deregister)
- **Always-on agent operations** - persistent agent lifecycle
- **Event-driven awakening** - automatically wake agents for relevant events
- Workflow orchestration and coordination
- Resource scheduling and allocation
- **Persistent state management** - maintain agent context across events
- Event routing and distribution
- Policy enforcement

**Perpetual Architecture:**

The kernel implements the core perpetual model:

1. **Agent Registration:** Agents register once and enter an indefinite run loop
2. **Sleep Mode:** Idle agents sleep to conserve resources
3. **Event Awakening:** Agents automatically awaken when subscribed events occur
4. **State Persistence:** Agent state is preserved across all awakenings
5. **Continuous Operation:** Agents run until explicitly deregistered

```
Agent Lifecycle in AOS:

Register → [Initialize] → [Start Perpetual Loop]
                              ↓
                         [Sleep Mode] ←─────────────┐
                              ↓                      │
                     [Event Received]                │
                              ↓                      │
                    [Awaken & Process]               │
                              ↓                      │
                      [Save State]                   │
                              ↓                      │
                    [Return to Sleep] ───────────────┘
                              ↓
                    [Runs indefinitely until deregistered]
```

**Key Characteristics:**
- Minimal and stable
- High performance (< 10ms overhead per operation)
- Highly reliable (99.99% uptime)
- Fully asynchronous
- **Event-driven** - agents respond to events, not polling
- **Persistent** - agents maintain state indefinitely

### Layer 3: System Service Layer

**Purpose:** Reusable infrastructure services

**Core Services:**
- **Auth Service** (`auth/`) - Authentication and authorization
- **Storage Service** (`storage/`) - Unified storage abstraction
- **Messaging Service** (`messaging/`) - Agent communication
- **Environment Service** (`environment/`) - Configuration management

**Advanced Services:**
- **ML Pipeline** (`ml/`) - Model training and inference
- **MCP Integration** (`mcp/`) - External tool integration
- **Knowledge Service** (`knowledge/`) - Knowledge management
- **Learning Service** (`learning/`) - Continuous improvement
- **Governance Service** (`governance/`) - Audit and compliance

**Cross-Cutting Services:**
- **Reliability** (`reliability/`) - Circuit breakers, retries
- **Observability** (`observability/`) - Metrics, logs, traces
- **Extensibility** (`extensibility/`) - Plugin framework
- **Platform Services** (`platform/`) - Common utilities

**Responsibilities:**
- Provide high-level APIs for applications
- Abstract Azure services
- Implement business-agnostic logic
- Ensure cross-service consistency

### Layer 4: Application Layer

**Purpose:** Business applications and custom agents

**Components:**
- Business applications (BusinessInfinity, custom apps)
- Leadership agents (CEO, CFO, CTO, etc.)
- Domain-specific agents
- Custom workflows and orchestrations

**Responsibilities:**
- Implement business logic
- Define domain workflows
- Create specialized agents
- Build user interfaces
- Integrate with external systems

---

## 🔧 Core Components

### Orchestration Engine

**Location:** `src/AgentOperatingSystem/orchestration/`

**Purpose:** Core workflow orchestration and multi-agent coordination

**Architecture:**
```
┌─────────────────────────────────────────┐
│      Orchestration Engine               │
├─────────────────────────────────────────┤
│  ┌────────────────┐  ┌───────────────┐ │
│  │  Workflow      │  │  Multi-Agent  │ │
│  │  Executor      │  │  Coordinator  │ │
│  └────────────────┘  └───────────────┘ │
│  ┌────────────────┐  ┌───────────────┐ │
│  │  Agent         │  │  Dependency   │ │
│  │  Registry      │  │  Resolver     │ │
│  └────────────────┘  └───────────────┘ │
└─────────────────────────────────────────┘
```

**Key Features:**
- Declarative workflow definitions
- Parallel and sequential execution
- Dependency resolution
- Error handling and compensation
- State persistence

### Storage System

**Location:** `src/AgentOperatingSystem/storage/`

**Purpose:** Unified storage abstraction

**Architecture:**
```
┌────────────────────────────────────────┐
│     UnifiedStorageManager              │
├────────────────────────────────────────┤
│  ┌──────────────────────────────────┐ │
│  │    Abstract Storage Interface    │ │
│  └──────────────────────────────────┘ │
│         ↓           ↓           ↓      │
│  ┌──────────┐ ┌─────────┐ ┌────────┐ │
│  │   Blob   │ │  Table  │ │ Queue  │ │
│  │  Backend │ │ Backend │ │Backend │ │
│  └──────────┘ └─────────┘ └────────┘ │
└────────────────────────────────────────┘
```

**Backends:**
- Blob Storage - Unstructured data
- Table Storage - Structured data
- Queue Storage - Message queues
- Cosmos DB - Document database
- File Storage - Local development

### Messaging System

**Location:** `src/AgentOperatingSystem/messaging/`

**Purpose:** Agent-to-agent communication

**Architecture:**
```
┌──────────────────────────────────────────┐
│         Message Bus                      │
├──────────────────────────────────────────┤
│  ┌─────────────┐      ┌──────────────┐  │
│  │  Publisher  │ ───> │  Subscriber  │  │
│  └─────────────┘      └──────────────┘  │
│         ↓                     ↑           │
│  ┌──────────────────────────────────┐   │
│  │   Azure Service Bus Topics       │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

**Patterns:**
- Publish/Subscribe
- Request/Response
- Event Sourcing
- Message Queuing

### ML Pipeline

**Location:** `src/AgentOperatingSystem/ml/`

**Purpose:** Machine learning training and inference

**Architecture:**
```
┌──────────────────────────────────────────┐
│       MLPipelineManager                  │
├──────────────────────────────────────────┤
│  ┌─────────────┐      ┌──────────────┐  │
│  │   Training  │      │  Inference   │  │
│  │   Pipeline  │      │   Engine     │  │
│  └─────────────┘      └──────────────┘  │
│         ↓                     ↓           │
│  ┌────────────────────────────────────┐ │
│  │    Azure Machine Learning          │ │
│  │    (Llama-3.1-8B + LoRA)          │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

**Features:**
- LoRA adapter management
- Multi-agent model sharing
- Inference caching
- Cost optimization

---

## 🔄 Data Flow

### Agent Message Flow

```
Agent A                Message Bus              Agent B
   │                       │                       │
   │ 1. publish("topic",msg)                      │
   ├──────────────────────>│                      │
   │                       │ 2. route(msg)        │
   │                       ├─────────────────────>│
   │                       │                      │
   │                       │ 3. process(msg)      │
   │                       │<─────────────────────┤
   │                       │ 4. ack               │
   │<──────────────────────┤                      │
   │ 5. confirm            │                      │
```

### ML Inference Flow

```
Agent              ML Pipeline           Azure ML          Cache
  │                    │                    │               │
  │ 1. infer(prompt)   │                    │               │
  ├───────────────────>│                    │               │
  │                    │ 2. check cache     │               │
  │                    ├───────────────────────────────────>│
  │                    │<───────────────────────────────────┤
  │                    │ 3. cache miss      │               │
  │                    │                    │               │
  │                    │ 4. invoke model    │               │
  │                    ├───────────────────>│               │
  │                    │<───────────────────┤               │
  │                    │ 5. response        │               │
  │                    │                    │               │
  │                    │ 6. cache result    │               │
  │                    ├───────────────────────────────────>│
  │<───────────────────┤                    │               │
  │ 7. return result   │                    │               │
```

### Audit Logging Flow

```
Operation          Governance          Storage          Monitor
    │                  │                  │               │
    │ 1. execute()     │                  │               │
    ├─────────────────>│                  │               │
    │                  │ 2. log(audit)    │               │
    │                  ├─────────────────>│               │
    │                  │                  │               │
    │                  │ 3. emit metric   │               │
    │                  ├─────────────────────────────────>│
    │<─────────────────┤                  │               │
    │ 4. complete      │                  │               │
```

---

## 🚀 Deployment Architecture

### Development Environment

```
┌────────────────────────────────┐
│  Developer Workstation         │
│  ┌──────────────────────────┐ │
│  │   AOS Local Instance     │ │
│  │   • File storage backend │ │
│  │   • In-memory messaging  │ │
│  │   • Mock ML inference    │ │
│  └──────────────────────────┘ │
└────────────────────────────────┘
```

### Production Environment

```
┌─────────────────────────────────────────────────────────┐
│                    Azure Cloud                          │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Load Balancer / API Gateway         │  │
│  └──────────────────────────────────────────────────┘  │
│                         ↓                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│  │ AOS       │  │ AOS       │  │ AOS       │         │
│  │ Instance  │  │ Instance  │  │ Instance  │  ...    │
│  │ #1        │  │ #2        │  │ #3        │         │
│  └───────────┘  └───────────┘  └───────────┘         │
│        ↓              ↓              ↓                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Shared Azure Services                  │  │
│  │  • Service Bus  • Storage  • ML  • Monitor      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Multi-Region Deployment

```
┌────────────── Region 1: West US 2 ──────────────┐
│  ┌─────────────────────────────────────────┐   │
│  │  AOS Cluster (Primary)                  │   │
│  │  • Active-Active agents                 │   │
│  │  • Read-Write storage                   │   │
│  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
           ↕ Async replication
┌────────────── Region 2: East US ────────────────┐
│  ┌─────────────────────────────────────────┐   │
│  │  AOS Cluster (Secondary)                │   │
│  │  • Standby agents                       │   │
│  │  • Read-Only storage replica            │   │
│  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## 💻 Technology Stack

### Programming Languages

- **Python 3.8+** - Primary implementation language
- **YAML** - Configuration and infrastructure as code
- **JSON** - Data interchange and configuration

### Core Frameworks & Libraries

| Category | Technology | Purpose |
|----------|-----------|---------|
| Foundry Agent Service | Azure AI Foundry Agent Service | Core agent capabilities |
| Async Runtime | asyncio, aiohttp | Asynchronous operations |
| Data Validation | Pydantic | Data models and validation |
| API Framework | FastAPI | REST API endpoints |
| ML Framework | Transformers, PyTorch | ML model operations |
| Testing | pytest, pytest-asyncio | Test framework |

### Azure Services

| Service | Usage | Criticality |
|---------|-------|-------------|
| Service Bus | Messaging backbone | Critical |
| Blob Storage | Object storage | Critical |
| Table Storage | Structured data | High |
| Cosmos DB | Document storage | Medium |
| Machine Learning | Model hosting | High |
| Key Vault | Secrets management | Critical |
| Monitor | Observability | High |
| AD B2C | Authentication | Critical |
| Functions | Serverless compute | Medium |

### Development Tools

- **Git** - Version control
- **GitHub Actions** - CI/CD
- **Docker** - Containerization
- **pytest** - Testing
- **Black** - Code formatting
- **Ruff** - Linting
- **mypy** - Type checking

---

## 🎯 Design Principles

### 1. Infrastructure First

AOS provides **only** pure infrastructure. No business logic in the OS layer.

**Rationale:** Maintain clear separation of concerns and reusability

### 2. Separation of Concerns

Clear boundaries between:
- Kernel (orchestration, lifecycle)
- Services (auth, storage, messaging, ML)
- Applications (business logic, agents)

**Rationale:** Modularity, testability, maintainability

### 3. Async by Default

All I/O operations use async/await patterns.

**Rationale:** Better resource utilization, higher throughput, lower latency

### 4. Event-Driven

Components communicate via events, not direct calls.

**Rationale:** Loose coupling, scalability, audit trail

### 5. Observable

Built-in instrumentation at every layer.

**Rationale:** Production readiness, debuggability, performance monitoring

### 6. Secure by Design

Security is not an add-on, it's foundational.

**Rationale:** Defense in depth, compliance, trust

### 7. Cloud-Native

Designed for distributed, cloud environments.

**Rationale:** Scalability, reliability, geographic distribution

### 8. Extensible

Plugin architecture for custom capabilities.

**Rationale:** Flexibility, future-proofing, ecosystem growth

---

## 🔨 Architectural Patterns

### System Patterns

1. **Layered Architecture** - Clear separation of concerns
2. **Microkernel** - Minimal kernel with pluggable services
3. **Event Sourcing** - Audit trail and state reconstruction
4. **CQRS** - Separate read and write models where beneficial

### Reliability Patterns

1. **Circuit Breaker** - Prevent cascading failures
2. **Retry with Backoff** - Graceful retry logic
3. **Bulkhead** - Isolate resource pools
4. **Timeout** - Prevent hanging operations
5. **Saga** - Distributed transaction management

### Observability Patterns

1. **Distributed Tracing** - End-to-end request tracking
2. **Structured Logging** - Machine-parseable logs
3. **Health Checks** - Readiness and liveness probes
4. **Metrics Collection** - RED (Rate, Errors, Duration) metrics

### Security Patterns

1. **Defense in Depth** - Multiple security layers
2. **Least Privilege** - Minimal required permissions
3. **Secure by Default** - Security-first configuration
4. **Zero Trust** - Never trust, always verify

---

## 📈 Scalability Architecture

### Horizontal Scaling

**Agent Scaling:**
```
Load Balancer
     ↓
┌─────┴─────┬─────┬─────┬─────┐
│ Agent 1   │ A2  │ A3  │ A4  │ ... Add agents as needed
└───────────┴─────┴─────┴─────┘
```

**Service Scaling:**
```
Service Bus (Partitioned)
     ↓
┌─────┴─────┬─────┬─────┬─────┐
│Worker 1   │ W2  │ W3  │ W4  │ ... Scale workers
└───────────┴─────┴─────┴─────┘
```

### Vertical Scaling

| Resource | Impact |
|----------|---------|
| CPU | Concurrent workflow execution |
| Memory | ML model caching, state management |
| Disk I/O | Storage throughput |
| Network | Message throughput |

### Scaling Limits

| Component | Max Instances | Constraint |
|-----------|---------------|------------|
| Agents | Unlimited | Cost only |
| Message Partitions | 32 per topic | Service Bus limit |
| Storage | 5 PB | Blob Storage limit |
| ML Endpoints | 100+ | Cost and quota |

---

## 🔐 Security Architecture

### Security Layers

```
Layer 7: Application   → Input validation, output encoding
Layer 6: Authentication → Identity verification
Layer 5: Authorization → Permission checks
Layer 4: Network       → VNets, NSGs, firewalls
Layer 3: Data          → Encryption at rest/transit
Layer 2: Audit         → Tamper-evident logs
Layer 1: Infrastructure → Azure security baseline
```

### Authentication Flow

```
1. User/Agent Request
   ↓
2. API Gateway (TLS termination)
   ↓
3. Auth Service (Token validation)
   ↓
4. RBAC Check (Permission verification)
   ↓
5. Service Layer (Business logic)
   ↓
6. Data Layer (Encrypted storage)
   ↓
7. Audit Log (Tamper-evident)
```

### Data Protection

- **At Rest:** AES-256 encryption
- **In Transit:** TLS 1.2+
- **Keys:** Azure Key Vault with rotation
- **Secrets:** Never logged or cached

---

## 👁️ Observability Architecture

### Three Pillars

```
┌────────────────────────────────────────┐
│          Application Code              │
├────────────────────────────────────────┤
│  Instrumentation Layer                 │
│  • Metrics  • Logs  • Traces          │
├────────────────────────────────────────┤
│     OpenTelemetry SDK                  │
├────────────────────────────────────────┤
│     Azure Monitor / App Insights       │
└────────────────────────────────────────┘
```

### Metrics Hierarchy

```
System Metrics
  ├── Agent Metrics
  │   ├── agent.decisions.count
  │   ├── agent.decisions.latency
  │   └── agent.errors.count
  ├── Storage Metrics
  │   ├── storage.operations.count
  │   ├── storage.operations.latency
  │   └── storage.errors.count
  └── Messaging Metrics
      ├── messages.published.count
      ├── messages.consumed.count
      └── messages.latency
```

---

## 📋 Decision Records

### ADR-001: Layered Architecture

**Status:** Accepted  
**Date:** 2025-01-01

**Decision:** Implement layered architecture with clear boundaries

**Context:** Need structure for complex system with multiple concerns

**Consequences:**
- ✅ Clear separation of concerns
- ✅ Testability and maintainability
- ❌ Potential performance overhead (mitigated with async)

### ADR-002: Azure as Primary Cloud

**Status:** Accepted  
**Date:** 2025-01-01

**Decision:** Azure-first with abstraction for multi-cloud

**Context:** Integration with Azure AI Foundry Agent Service

**Consequences:**
- ✅ Deep Azure integration
- ✅ Enterprise features
- ❌ Vendor lock-in (mitigated with abstraction)

### ADR-003: Async-First API Design

**Status:** Accepted  
**Date:** 2025-01-01

**Decision:** All I/O operations use async/await

**Context:** Need high throughput and responsiveness

**Consequences:**
- ✅ Better resource utilization
- ✅ Higher scalability
- ❌ Increased complexity (mitigated with patterns)

---

## 📚 Related Documentation

- **[README](README.md)** - Project overview
- **[Specifications](docs/specifications/README.md)** - Detailed component specs
- **[Quickstart](docs/quickstart.md)** - Getting started guide
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines

---

<div align="center">

*This is a living document. Last updated: December 25, 2025*

**[View on GitHub](https://github.com/ASISaga/AgentOperatingSystem)** • **[Report Issue](https://github.com/ASISaga/AgentOperatingSystem/issues)**

</div>

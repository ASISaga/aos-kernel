"""Observability subsystem for the Agent Operating System.

Provides OpenTelemetry-based traces, metrics, and logs following the
OTel GenAI semantic conventions, with integration points for Azure Monitor,
Application Insights, and Microsoft Foundry agent tracing.

Core entry-point:

- :class:`AOSObservabilityProvider` — configures OTel providers and
  exposes helpers for tracing agent operations, recording GenAI metrics,
  and governance evaluations.
"""

from AgentOperatingSystem.observability.otel import AOSObservabilityProvider

__all__ = ["AOSObservabilityProvider"]

"""OpenTelemetry-based observability for the Agent Operating System.

Provides a unified observability provider that configures the three OTel
signals — **traces**, **metrics**, and **logs** — following the
`OpenTelemetry GenAI Semantic Conventions`_ and integrating with:

* **Microsoft Foundry agent tracing** (via ``azure-ai-projects`` SDK)
* **Azure Monitor / Application Insights** (via OTLP export)
* **Foundry Control Plane** guardrails and evaluation hooks

The :class:`AOSObservabilityProvider` is the single entry-point that the
kernel initialises at startup.  It exposes helpers for creating spans
around agent operations, recording GenAI metrics, and emitting
structured log records that include trace-context propagation.

Usage::

    from AgentOperatingSystem.observability.otel import AOSObservabilityProvider

    provider = AOSObservabilityProvider(
        service_name="aos-kernel",
        otlp_endpoint="http://localhost:4317",
    )
    provider.setup()

    # Create a span for an agent operation
    with provider.trace_agent_operation("ceo", "register") as span:
        span.set_attribute("gen_ai.agent.id", "ceo")
        ...

    # Record GenAI metrics
    provider.record_agent_invocation("ceo", model="gpt-4o", duration_s=1.2,
                                      input_tokens=150, output_tokens=80)

    # Shutdown
    provider.shutdown()

.. _OpenTelemetry GenAI Semantic Conventions:
    https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence

from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic-convention attribute keys
# ---------------------------------------------------------------------------
# We intentionally hard-code the stable string values here rather than
# importing from ``opentelemetry.semconv._incubating`` so that this
# module works with any semconv release ≥ 0.45b0.

_ATTR_SERVICE_NAME = "service.name"
_ATTR_SERVICE_VERSION = "service.version"
_ATTR_DEPLOYMENT_ENVIRONMENT = "deployment.environment"

# GenAI semantic conventions (stable strings per OTel GenAI spec)
ATTR_GEN_AI_SYSTEM = "gen_ai.system"
ATTR_GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
ATTR_GEN_AI_AGENT_ID = "gen_ai.agent.id"
ATTR_GEN_AI_AGENT_NAME = "gen_ai.agent.name"
ATTR_GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
ATTR_GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
ATTR_GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
ATTR_GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
ATTR_GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
ATTR_GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
ATTR_GEN_AI_EVALUATION_NAME = "gen_ai.evaluation.name"
ATTR_GEN_AI_EVALUATION_SCORE_VALUE = "gen_ai.evaluation.score.value"
ATTR_GEN_AI_EVALUATION_SCORE_LABEL = "gen_ai.evaluation.score.label"
ATTR_GEN_AI_TOKEN_TYPE = "gen_ai.token.type"

# GenAI metric names (per OTel GenAI spec)
METRIC_CLIENT_OPERATION_DURATION = "gen_ai.client.operation.duration"
METRIC_CLIENT_TOKEN_USAGE = "gen_ai.client.token.usage"

# AOS-specific metric names (custom, namespaced under ``aos.``)
METRIC_AOS_AGENT_REGISTRATIONS = "aos.agent.registrations"
METRIC_AOS_ORCHESTRATION_CREATED = "aos.orchestration.created"
METRIC_AOS_ORCHESTRATION_DURATION = "aos.orchestration.duration"
METRIC_AOS_MESSAGES_BRIDGED = "aos.messages.bridged"
METRIC_AOS_GOVERNANCE_EVALUATIONS = "aos.governance.evaluations"

# Foundry system identifier
SYSTEM_AZURE_AI_FOUNDRY = "az.ai.foundry"


def _build_resource(
    service_name: str,
    service_version: str,
    environment: str,
    extra_attributes: Optional[Dict[str, str]] = None,
) -> Resource:
    """Build an OTel ``Resource`` with AOS identity attributes."""
    attrs: Dict[str, str] = {
        _ATTR_SERVICE_NAME: service_name,
        _ATTR_SERVICE_VERSION: service_version,
        _ATTR_DEPLOYMENT_ENVIRONMENT: environment,
        ATTR_GEN_AI_SYSTEM: SYSTEM_AZURE_AI_FOUNDRY,
    }
    if extra_attributes:
        attrs.update(extra_attributes)
    return Resource.create(attrs)


class AOSObservabilityProvider:
    """Unified OpenTelemetry observability provider for the AOS kernel.

    Configures ``TracerProvider``, ``MeterProvider``, and optionally
    ``LoggerProvider`` to emit telemetry following the OTel GenAI
    semantic conventions and Azure Monitor best practices.

    :param service_name: Logical service name (default ``"aos-kernel"``).
    :param service_version: Service version (default ``"6.0.0"``).
    :param environment: Deployment environment (``dev``, ``staging``, ``prod``).
    :param otlp_endpoint: OTLP collector endpoint.  When set, an OTLP
        gRPC exporter is configured for traces and metrics.
    :param application_insights_connection_string: Azure Monitor
        connection string.  When set, the Azure Monitor exporter is
        configured (requires ``azure-monitor-opentelemetry-exporter``).
    :param span_exporters: Additional span exporters.
    :param metric_readers: Additional metric readers.
    :param extra_resource_attributes: Extra key/value pairs to add to the
        OTel ``Resource``.
    """

    def __init__(
        self,
        service_name: str = "aos-kernel",
        service_version: str = "6.0.0",
        environment: str = "dev",
        otlp_endpoint: str = "",
        application_insights_connection_string: str = "",
        span_exporters: Optional[Sequence[SpanExporter]] = None,
        metric_readers: Optional[Sequence[MetricReader]] = None,
        extra_resource_attributes: Optional[Dict[str, str]] = None,
    ) -> None:
        self._service_name = service_name
        self._service_version = service_version
        self._environment = environment
        self._otlp_endpoint = otlp_endpoint
        self._appinsights_cs = application_insights_connection_string
        self._extra_span_exporters = list(span_exporters or [])
        self._extra_metric_readers = list(metric_readers or [])
        self._extra_resource_attrs = extra_resource_attributes

        self._resource: Optional[Resource] = None
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._in_memory_metric_reader: Optional[InMemoryMetricReader] = None
        self._tracer: Optional[otel_trace.Tracer] = None
        self._meter: Optional[otel_metrics.Meter] = None

        # Instruments (created lazily in ``setup``)
        self._operation_duration_histogram: Any = None
        self._token_usage_counter: Any = None
        self._agent_registrations_counter: Any = None
        self._orchestration_created_counter: Any = None
        self._orchestration_duration_histogram: Any = None
        self._messages_bridged_counter: Any = None
        self._governance_evaluations_counter: Any = None

        self._is_setup = False

    # ------------------------------------------------------------------
    # Setup / Teardown
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Initialise OTel providers and register instruments.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._is_setup:
            return

        self._resource = _build_resource(
            service_name=self._service_name,
            service_version=self._service_version,
            environment=self._environment,
            extra_attributes=self._extra_resource_attrs,
        )

        self._setup_tracing()
        self._setup_metrics()
        self._is_setup = True
        logger.info(
            "AOS observability initialised (service=%s, env=%s, otlp=%s, appinsights=%s)",
            self._service_name,
            self._environment,
            bool(self._otlp_endpoint),
            bool(self._appinsights_cs),
        )

    def shutdown(self) -> None:
        """Flush and shut down all providers."""
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
        self._is_setup = False
        logger.info("AOS observability shut down")

    # ------------------------------------------------------------------
    # Tracing helpers
    # ------------------------------------------------------------------

    @property
    def tracer(self) -> otel_trace.Tracer:
        """Return the configured ``Tracer`` instance."""
        if self._tracer is None:
            raise RuntimeError("Call setup() before using the tracer.")
        return self._tracer

    @contextmanager
    def trace_agent_operation(
        self,
        agent_id: str,
        operation: str,
        *,
        model: str = "",
        conversation_id: str = "",
        attributes: Optional[Dict[str, str]] = None,
    ) -> Iterator[otel_trace.Span]:
        """Context manager that creates a span for an agent operation.

        Automatically sets GenAI semantic-convention attributes on the
        span and records the duration.

        :param agent_id: Agent identifier (``gen_ai.agent.id``).
        :param operation: Operation name (e.g. ``"invoke"``, ``"register"``).
        :param model: Model used (``gen_ai.request.model``).
        :param conversation_id: Optional conversation / thread ID.
        :param attributes: Extra span attributes.
        :yields: The active ``Span``.
        """
        span_name = f"{operation} {agent_id}"
        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute(ATTR_GEN_AI_SYSTEM, SYSTEM_AZURE_AI_FOUNDRY)
            span.set_attribute(ATTR_GEN_AI_OPERATION_NAME, operation)
            span.set_attribute(ATTR_GEN_AI_AGENT_ID, agent_id)
            if model:
                span.set_attribute(ATTR_GEN_AI_REQUEST_MODEL, model)
            if conversation_id:
                span.set_attribute(ATTR_GEN_AI_CONVERSATION_ID, conversation_id)
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            try:
                yield span
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise

    @contextmanager
    def trace_orchestration(
        self,
        orchestration_id: str,
        purpose: str,
        workflow: str = "collaborative",
        *,
        attributes: Optional[Dict[str, str]] = None,
    ) -> Iterator[otel_trace.Span]:
        """Context manager that creates a span for an orchestration lifecycle.

        :param orchestration_id: Unique orchestration identifier.
        :param purpose: Orchestration purpose text.
        :param workflow: Workflow type.
        :param attributes: Extra span attributes.
        :yields: The active ``Span``.
        """
        span_name = f"orchestration {orchestration_id}"
        with self.tracer.start_as_current_span(span_name) as span:
            span.set_attribute(ATTR_GEN_AI_SYSTEM, SYSTEM_AZURE_AI_FOUNDRY)
            span.set_attribute(ATTR_GEN_AI_OPERATION_NAME, "orchestration")
            span.set_attribute("aos.orchestration.id", orchestration_id)
            span.set_attribute("aos.orchestration.purpose", purpose)
            span.set_attribute("aos.orchestration.workflow", workflow)
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            start = time.monotonic()
            try:
                yield span
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            finally:
                duration_s = time.monotonic() - start
                if self._orchestration_duration_histogram:
                    self._orchestration_duration_histogram.record(
                        duration_s,
                        {
                            "aos.orchestration.workflow": workflow,
                            ATTR_GEN_AI_SYSTEM: SYSTEM_AZURE_AI_FOUNDRY,
                        },
                    )

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    @property
    def meter(self) -> otel_metrics.Meter:
        """Return the configured ``Meter`` instance."""
        if self._meter is None:
            raise RuntimeError("Call setup() before using the meter.")
        return self._meter

    def record_agent_invocation(
        self,
        agent_id: str,
        *,
        model: str = "",
        duration_s: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        operation: str = "invoke",
    ) -> None:
        """Record metrics for a single agent invocation.

        Emits the standard GenAI metrics (``gen_ai.client.operation.duration``
        and ``gen_ai.client.token.usage``) together with AOS-custom counters.

        :param agent_id: Agent identifier.
        :param model: Model deployment name.
        :param duration_s: Operation duration in seconds.
        :param input_tokens: Prompt / input token count.
        :param output_tokens: Completion / output token count.
        :param operation: Operation name.
        """
        common_attrs: Dict[str, str] = {
            ATTR_GEN_AI_SYSTEM: SYSTEM_AZURE_AI_FOUNDRY,
            ATTR_GEN_AI_OPERATION_NAME: operation,
            ATTR_GEN_AI_AGENT_ID: agent_id,
        }
        if model:
            common_attrs[ATTR_GEN_AI_REQUEST_MODEL] = model

        if self._operation_duration_histogram and duration_s > 0:
            self._operation_duration_histogram.record(duration_s, common_attrs)

        if self._token_usage_counter:
            if input_tokens > 0:
                self._token_usage_counter.add(
                    input_tokens,
                    {**common_attrs, ATTR_GEN_AI_TOKEN_TYPE: "input"},
                )
            if output_tokens > 0:
                self._token_usage_counter.add(
                    output_tokens,
                    {**common_attrs, ATTR_GEN_AI_TOKEN_TYPE: "output"},
                )

    def record_agent_registration(self, agent_id: str, model: str = "") -> None:
        """Increment the agent-registration counter."""
        if self._agent_registrations_counter:
            attrs = {ATTR_GEN_AI_AGENT_ID: agent_id}
            if model:
                attrs[ATTR_GEN_AI_REQUEST_MODEL] = model
            self._agent_registrations_counter.add(1, attrs)

    def record_orchestration_created(
        self, orchestration_id: str, workflow: str = "collaborative"
    ) -> None:
        """Increment the orchestration-created counter."""
        if self._orchestration_created_counter:
            self._orchestration_created_counter.add(
                1,
                {
                    "aos.orchestration.id": orchestration_id,
                    "aos.orchestration.workflow": workflow,
                },
            )

    def record_message_bridged(
        self, direction: str, agent_id: str = ""
    ) -> None:
        """Increment the messages-bridged counter."""
        if self._messages_bridged_counter:
            attrs: Dict[str, str] = {"aos.message.direction": direction}
            if agent_id:
                attrs[ATTR_GEN_AI_AGENT_ID] = agent_id
            self._messages_bridged_counter.add(1, attrs)

    # ------------------------------------------------------------------
    # Governance / Evaluation helpers
    # ------------------------------------------------------------------

    def record_governance_evaluation(
        self,
        evaluation_name: str,
        score_value: float,
        *,
        score_label: str = "",
        agent_id: str = "",
    ) -> None:
        """Record a governance evaluation result.

        Emits a counter for governance evaluations and, when tracing is
        active, adds evaluation attributes to the current span following
        the GenAI evaluation semantic conventions.

        :param evaluation_name: Name of the evaluation (e.g. ``"content_safety"``).
        :param score_value: Numeric evaluation score.
        :param score_label: Optional human-readable label (e.g. ``"pass"``).
        :param agent_id: Optional agent identifier.
        """
        if self._governance_evaluations_counter:
            attrs: Dict[str, str] = {
                ATTR_GEN_AI_EVALUATION_NAME: evaluation_name,
            }
            if score_label:
                attrs[ATTR_GEN_AI_EVALUATION_SCORE_LABEL] = score_label
            if agent_id:
                attrs[ATTR_GEN_AI_AGENT_ID] = agent_id
            self._governance_evaluations_counter.add(1, attrs)

        # Annotate the active span if one exists
        current_span = otel_trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(ATTR_GEN_AI_EVALUATION_NAME, evaluation_name)
            current_span.set_attribute(ATTR_GEN_AI_EVALUATION_SCORE_VALUE, score_value)
            if score_label:
                current_span.set_attribute(ATTR_GEN_AI_EVALUATION_SCORE_LABEL, score_label)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a status dict suitable for ``health_check``."""
        return {
            "observability_enabled": self._is_setup,
            "otlp_endpoint": self._otlp_endpoint or None,
            "application_insights": bool(self._appinsights_cs),
            "service_name": self._service_name,
            "environment": self._environment,
        }

    def collect_metrics_snapshot(self) -> Dict[str, Any]:
        """Collect a point-in-time metrics snapshot (for tests / debugging).

        Requires the in-memory metric reader to be configured (which is
        the default when no external readers are provided).
        """
        if self._in_memory_metric_reader is None:
            return {}

        data = self._in_memory_metric_reader.get_metrics_data()
        snapshot: Dict[str, Any] = {}
        for resource_metric in data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    points = []
                    for dp in metric.data.data_points:
                        point: Dict[str, Any] = {}
                        if hasattr(dp, "sum"):
                            point["value"] = dp.sum
                        elif hasattr(dp, "value"):
                            point["value"] = dp.value
                        if hasattr(dp, "attributes") and dp.attributes:
                            point["attributes"] = dict(dp.attributes)
                        points.append(point)
                    snapshot[metric.name] = {
                        "description": metric.description,
                        "unit": metric.unit,
                        "data_points": points,
                    }
        return snapshot

    # ------------------------------------------------------------------
    # Private setup helpers
    # ------------------------------------------------------------------

    def _setup_tracing(self) -> None:
        """Configure ``TracerProvider`` with exporters."""
        self._tracer_provider = TracerProvider(resource=self._resource)

        # OTLP gRPC exporter
        if self._otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(endpoint=self._otlp_endpoint)
                self._tracer_provider.add_span_processor(
                    SimpleSpanProcessor(otlp_exporter)
                )
                logger.info("OTLP trace exporter configured: %s", self._otlp_endpoint)
            except ImportError:
                logger.warning(
                    "opentelemetry-exporter-otlp-proto-grpc not installed — "
                    "OTLP trace export disabled"
                )

        # Azure Monitor exporter
        if self._appinsights_cs:
            try:
                from azure.monitor.opentelemetry.exporter import (
                    AzureMonitorTraceExporter,
                )

                az_exporter = AzureMonitorTraceExporter(
                    connection_string=self._appinsights_cs
                )
                self._tracer_provider.add_span_processor(
                    SimpleSpanProcessor(az_exporter)
                )
                logger.info("Azure Monitor trace exporter configured")
            except ImportError:
                logger.warning(
                    "azure-monitor-opentelemetry-exporter not installed — "
                    "Application Insights trace export disabled"
                )

        # Additional exporters (e.g. test in-memory exporters)
        for exporter in self._extra_span_exporters:
            self._tracer_provider.add_span_processor(
                SimpleSpanProcessor(exporter)
            )

        otel_trace.set_tracer_provider(self._tracer_provider)
        self._tracer = self._tracer_provider.get_tracer(
            self._service_name,
            self._service_version,
        )

    def _setup_metrics(self) -> None:
        """Configure ``MeterProvider`` with readers and create instruments."""
        readers: List[MetricReader] = []

        # Always add an in-memory reader for diagnostics / tests
        self._in_memory_metric_reader = InMemoryMetricReader()
        readers.append(self._in_memory_metric_reader)

        # OTLP metric exporter
        if self._otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                    OTLPMetricExporter,
                )
                from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

                otlp_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=self._otlp_endpoint),
                    export_interval_millis=60_000,
                )
                readers.append(otlp_reader)
                logger.info("OTLP metric exporter configured: %s", self._otlp_endpoint)
            except ImportError:
                logger.warning(
                    "opentelemetry-exporter-otlp-proto-grpc not installed — "
                    "OTLP metric export disabled"
                )

        # Azure Monitor metric exporter
        if self._appinsights_cs:
            try:
                from azure.monitor.opentelemetry.exporter import (
                    AzureMonitorMetricExporter,
                )
                from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

                az_reader = PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(
                        connection_string=self._appinsights_cs
                    ),
                    export_interval_millis=60_000,
                )
                readers.append(az_reader)
                logger.info("Azure Monitor metric exporter configured")
            except ImportError:
                logger.warning(
                    "azure-monitor-opentelemetry-exporter not installed — "
                    "Application Insights metric export disabled"
                )

        # Additional user-supplied readers
        readers.extend(self._extra_metric_readers)

        self._meter_provider = MeterProvider(
            resource=self._resource,
            metric_readers=readers,
        )
        otel_metrics.set_meter_provider(self._meter_provider)
        self._meter = self._meter_provider.get_meter(
            self._service_name,
            self._service_version,
        )

        # ------ Create instruments following GenAI semantic conventions ------

        # gen_ai.client.operation.duration (histogram, seconds)
        self._operation_duration_histogram = self._meter.create_histogram(
            name=METRIC_CLIENT_OPERATION_DURATION,
            description="Duration of GenAI client operations",
            unit="s",
        )

        # gen_ai.client.token.usage (counter)
        self._token_usage_counter = self._meter.create_counter(
            name=METRIC_CLIENT_TOKEN_USAGE,
            description="Number of tokens used in GenAI operations",
            unit="{token}",
        )

        # AOS-specific instruments
        self._agent_registrations_counter = self._meter.create_counter(
            name=METRIC_AOS_AGENT_REGISTRATIONS,
            description="Number of agent registrations",
            unit="{registration}",
        )
        self._orchestration_created_counter = self._meter.create_counter(
            name=METRIC_AOS_ORCHESTRATION_CREATED,
            description="Number of orchestrations created",
            unit="{orchestration}",
        )
        self._orchestration_duration_histogram = self._meter.create_histogram(
            name=METRIC_AOS_ORCHESTRATION_DURATION,
            description="Duration of orchestrations",
            unit="s",
        )
        self._messages_bridged_counter = self._meter.create_counter(
            name=METRIC_AOS_MESSAGES_BRIDGED,
            description="Number of messages bridged between Foundry and agents",
            unit="{message}",
        )
        self._governance_evaluations_counter = self._meter.create_counter(
            name=METRIC_AOS_GOVERNANCE_EVALUATIONS,
            description="Number of governance evaluations performed",
            unit="{evaluation}",
        )

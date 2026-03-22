"""Tests for the AOS observability module (OTel-based).

Validates:
- AOSObservabilityProvider setup/shutdown lifecycle
- Tracing with GenAI semantic convention attributes
- Metrics recording (GenAI + AOS-custom)
- Governance evaluation hooks
- Kernel integration (health_check includes observability status)
"""

import pytest

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from AgentOperatingSystem import AgentOperatingSystem
from AgentOperatingSystem.observability.otel import (
    AOSObservabilityProvider,
    ATTR_GEN_AI_AGENT_ID,
    ATTR_GEN_AI_EVALUATION_NAME,
    ATTR_GEN_AI_EVALUATION_SCORE_VALUE,
    ATTR_GEN_AI_OPERATION_NAME,
    ATTR_GEN_AI_REQUEST_MODEL,
    ATTR_GEN_AI_SYSTEM,
    METRIC_AOS_AGENT_REGISTRATIONS,
    METRIC_AOS_GOVERNANCE_EVALUATIONS,
    METRIC_AOS_MESSAGES_BRIDGED,
    METRIC_AOS_ORCHESTRATION_CREATED,
    METRIC_CLIENT_OPERATION_DURATION,
    METRIC_CLIENT_TOKEN_USAGE,
    SYSTEM_AZURE_AI_FOUNDRY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(*, exporter: InMemorySpanExporter | None = None) -> AOSObservabilityProvider:
    """Create a provider with an in-memory span exporter for testing."""
    exporters = [exporter] if exporter else []
    return AOSObservabilityProvider(
        service_name="aos-test",
        service_version="0.0.1",
        environment="test",
        span_exporters=exporters,
    )


# ---------------------------------------------------------------------------
# Provider lifecycle
# ---------------------------------------------------------------------------

class TestProviderLifecycle:
    """Tests for AOSObservabilityProvider setup and shutdown."""

    def test_setup_is_idempotent(self):
        provider = _make_provider()
        provider.setup()
        provider.setup()  # second call should be a no-op
        assert provider._is_setup is True
        provider.shutdown()

    def test_shutdown_resets_state(self):
        provider = _make_provider()
        provider.setup()
        provider.shutdown()
        assert provider._is_setup is False

    def test_tracer_requires_setup(self):
        provider = _make_provider()
        with pytest.raises(RuntimeError, match="setup"):
            _ = provider.tracer

    def test_meter_requires_setup(self):
        provider = _make_provider()
        with pytest.raises(RuntimeError, match="setup"):
            _ = provider.meter

    def test_get_status_before_setup(self):
        provider = _make_provider()
        status = provider.get_status()
        assert status["observability_enabled"] is False
        assert status["service_name"] == "aos-test"

    def test_get_status_after_setup(self):
        provider = _make_provider()
        provider.setup()
        status = provider.get_status()
        assert status["observability_enabled"] is True
        assert status["environment"] == "test"
        provider.shutdown()


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------

class TestTracing:
    """Tests for span creation and GenAI semantic attributes."""

    def test_trace_agent_operation_creates_span(self):
        exporter = InMemorySpanExporter()
        provider = _make_provider(exporter=exporter)
        provider.setup()

        with provider.trace_agent_operation("ceo", "register", model="gpt-4o"):
            pass  # simulate work

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "register ceo"
        attrs = dict(span.attributes)
        assert attrs[ATTR_GEN_AI_SYSTEM] == SYSTEM_AZURE_AI_FOUNDRY
        assert attrs[ATTR_GEN_AI_OPERATION_NAME] == "register"
        assert attrs[ATTR_GEN_AI_AGENT_ID] == "ceo"
        assert attrs[ATTR_GEN_AI_REQUEST_MODEL] == "gpt-4o"
        provider.shutdown()

    def test_trace_agent_operation_records_exception(self):
        exporter = InMemorySpanExporter()
        provider = _make_provider(exporter=exporter)
        provider.setup()

        with pytest.raises(ValueError, match="test error"):
            with provider.trace_agent_operation("cfo", "invoke"):
                raise ValueError("test error")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR
        provider.shutdown()

    def test_trace_agent_operation_with_extra_attributes(self):
        exporter = InMemorySpanExporter()
        provider = _make_provider(exporter=exporter)
        provider.setup()

        with provider.trace_agent_operation(
            "cto", "invoke",
            conversation_id="thread-42",
            attributes={"custom.key": "custom_value"},
        ):
            pass

        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["gen_ai.conversation.id"] == "thread-42"
        assert attrs["custom.key"] == "custom_value"
        provider.shutdown()

    def test_trace_orchestration_creates_span(self):
        exporter = InMemorySpanExporter()
        provider = _make_provider(exporter=exporter)
        provider.setup()

        with provider.trace_orchestration("orch-1", "Strategic review", "collaborative"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs["aos.orchestration.id"] == "orch-1"
        assert attrs["aos.orchestration.purpose"] == "Strategic review"
        assert attrs["aos.orchestration.workflow"] == "collaborative"
        provider.shutdown()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    """Tests for GenAI and AOS-custom metric recording."""

    def test_record_agent_invocation_duration_and_tokens(self):
        provider = _make_provider()
        provider.setup()

        provider.record_agent_invocation(
            "ceo",
            model="gpt-4o",
            duration_s=1.5,
            input_tokens=100,
            output_tokens=50,
        )

        snapshot = provider.collect_metrics_snapshot()
        assert METRIC_CLIENT_OPERATION_DURATION in snapshot
        assert METRIC_CLIENT_TOKEN_USAGE in snapshot

        # Token usage should have data points for both input and output
        token_points = snapshot[METRIC_CLIENT_TOKEN_USAGE]["data_points"]
        assert len(token_points) >= 2  # input + output
        provider.shutdown()

    def test_record_agent_registration(self):
        provider = _make_provider()
        provider.setup()

        provider.record_agent_registration("ceo", model="gpt-4o")
        provider.record_agent_registration("cfo")

        snapshot = provider.collect_metrics_snapshot()
        assert METRIC_AOS_AGENT_REGISTRATIONS in snapshot
        provider.shutdown()

    def test_record_orchestration_created(self):
        provider = _make_provider()
        provider.setup()

        provider.record_orchestration_created("orch-1", workflow="sequential")

        snapshot = provider.collect_metrics_snapshot()
        assert METRIC_AOS_ORCHESTRATION_CREATED in snapshot
        provider.shutdown()

    def test_record_message_bridged(self):
        provider = _make_provider()
        provider.setup()

        provider.record_message_bridged("foundry_to_agent", agent_id="ceo")
        provider.record_message_bridged("agent_to_foundry", agent_id="cfo")

        snapshot = provider.collect_metrics_snapshot()
        assert METRIC_AOS_MESSAGES_BRIDGED in snapshot
        provider.shutdown()

    def test_collect_metrics_snapshot_empty_when_not_setup(self):
        provider = _make_provider()
        # no setup
        snapshot = provider.collect_metrics_snapshot()
        assert snapshot == {}


# ---------------------------------------------------------------------------
# Governance / Evaluation
# ---------------------------------------------------------------------------

class TestGovernanceEvaluation:
    """Tests for governance evaluation recording."""

    def test_record_governance_evaluation_increments_counter(self):
        provider = _make_provider()
        provider.setup()

        provider.record_governance_evaluation(
            "content_safety",
            score_value=0.95,
            score_label="pass",
            agent_id="ceo",
        )

        snapshot = provider.collect_metrics_snapshot()
        assert METRIC_AOS_GOVERNANCE_EVALUATIONS in snapshot
        provider.shutdown()

    def test_record_governance_evaluation_annotates_span(self):
        exporter = InMemorySpanExporter()
        provider = _make_provider(exporter=exporter)
        provider.setup()

        with provider.trace_agent_operation("ceo", "invoke"):
            provider.record_governance_evaluation(
                "groundedness",
                score_value=0.87,
                score_label="acceptable",
            )

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[ATTR_GEN_AI_EVALUATION_NAME] == "groundedness"
        assert attrs[ATTR_GEN_AI_EVALUATION_SCORE_VALUE] == 0.87
        provider.shutdown()


# ---------------------------------------------------------------------------
# Kernel integration
# ---------------------------------------------------------------------------

class TestKernelObservabilityIntegration:
    """Tests for observability integration with the AgentOperatingSystem kernel."""

    @pytest.mark.asyncio
    async def test_health_check_includes_observability(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        health = await kernel.health_check()

        assert "observability" in health
        obs = health["observability"]
        assert obs["observability_enabled"] is True
        assert obs["service_name"] == "aos-kernel"
        await kernel.shutdown()

    @pytest.mark.asyncio
    async def test_kernel_observability_provider_accessible(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()

        assert isinstance(kernel.observability, AOSObservabilityProvider)
        assert kernel.observability._is_setup is True
        await kernel.shutdown()

    @pytest.mark.asyncio
    async def test_kernel_shutdown_disables_observability(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.shutdown()

        assert kernel.observability._is_setup is False

    @pytest.mark.asyncio
    async def test_kernel_with_custom_observability_provider(self):
        exporter = InMemorySpanExporter()
        custom_provider = AOSObservabilityProvider(
            service_name="custom-aos",
            environment="staging",
            span_exporters=[exporter],
        )
        kernel = AgentOperatingSystem(observability=custom_provider)
        await kernel.initialize()

        # Use observability through the kernel
        with kernel.observability.trace_agent_operation("ceo", "test_op"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_op ceo"

        health = await kernel.health_check()
        assert health["observability"]["service_name"] == "custom-aos"
        assert health["observability"]["environment"] == "staging"
        await kernel.shutdown()

    @pytest.mark.asyncio
    async def test_kernel_config_observability_fields(self):
        from AgentOperatingSystem.config import KernelConfig

        config = KernelConfig(
            otlp_endpoint="http://collector:4317",
            applicationinsights_connection_string="InstrumentationKey=test-key",
            otel_service_name="my-aos",
        )
        assert config.otlp_endpoint == "http://collector:4317"
        assert config.applicationinsights_connection_string == "InstrumentationKey=test-key"
        assert config.otel_service_name == "my-aos"

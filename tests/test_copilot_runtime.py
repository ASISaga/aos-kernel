"""Tests for CopilotRuntime — CopilotKit/SDK-JS bridge to AOS Foundry orchestration."""

import pytest

from AgentOperatingSystem import AgentOperatingSystem, CopilotRuntime, CopilotMessage, CopilotRuntimeRequest
from AgentOperatingSystem.copilot_runtime import _sse_text_chunk, _sse_data, _sse_finish


# ---------------------------------------------------------------------------
# SSE helper tests
# ---------------------------------------------------------------------------


class TestSSEHelpers:
    def test_sse_text_chunk(self):
        event = _sse_text_chunk("hello world")
        assert event.startswith("data: 0:")
        assert "hello world" in event
        assert event.endswith("\n\n")

    def test_sse_text_chunk_escapes_quotes(self):
        event = _sse_text_chunk('say "hi"')
        assert "data: 0:" in event
        assert event.endswith("\n\n")

    def test_sse_data(self):
        event = _sse_data({"key": "val"})
        assert "data: 2:" in event
        assert '"key"' in event
        assert event.endswith("\n\n")

    def test_sse_finish_default(self):
        event = _sse_finish()
        assert "data: d:" in event
        assert "stop" in event
        assert event.endswith("\n\n")

    def test_sse_finish_custom_reason(self):
        event = _sse_finish("length")
        assert "length" in event


# ---------------------------------------------------------------------------
# CopilotMessage / CopilotRuntimeRequest model tests
# ---------------------------------------------------------------------------


class TestCopilotModels:
    def test_message_defaults(self):
        msg = CopilotMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.id is not None  # auto-generated

    def test_message_explicit_id(self):
        msg = CopilotMessage(role="assistant", content="Hi", id="msg-001")
        assert msg.id == "msg-001"

    def test_request_defaults(self):
        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Ping")]
        )
        assert req.thread_id is None
        assert req.agent_id is None
        assert req.actions is None
        assert req.agent_states is None

    def test_request_with_thread_and_agent(self):
        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Hello")],
            thread_id="thread-abc",
            agent_id="ceo",
        )
        assert req.thread_id == "thread-abc"
        assert req.agent_id == "ceo"


# ---------------------------------------------------------------------------
# CopilotRuntime unit tests
# ---------------------------------------------------------------------------


class TestCopilotRuntime:
    @pytest.mark.asyncio
    async def test_create_via_kernel(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = kernel.create_copilot_runtime()
        assert isinstance(runtime, CopilotRuntime)
        assert runtime.kernel is kernel

    @pytest.mark.asyncio
    async def test_create_with_default_agent(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = kernel.create_copilot_runtime(default_agent_id="ceo")
        assert runtime.default_agent_id == "ceo"

    @pytest.mark.asyncio
    async def test_create_with_default_purpose(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = kernel.create_copilot_runtime(default_purpose="Custom purpose")
        assert runtime.default_purpose == "Custom purpose"

    @pytest.mark.asyncio
    async def test_thread_count_starts_zero(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        assert runtime.thread_count == 0

    @pytest.mark.asyncio
    async def test_list_threads_empty(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        assert runtime.list_threads() == []

    @pytest.mark.asyncio
    async def test_get_orchestration_id_unknown_thread(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        assert runtime.get_orchestration_id("no-such-thread") is None


class TestCopilotRuntimeProcessRequest:
    @pytest.mark.asyncio
    async def test_process_request_no_user_message(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="system", content="You are helpful")]
        )
        events = [chunk async for chunk in runtime.process_request(req)]
        # Should emit an error text chunk and a finish event
        assert any(_sse_text_chunk("No user message provided.") == e for e in events)
        assert _sse_finish("stop") in events

    @pytest.mark.asyncio
    async def test_process_request_creates_orchestration(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("ceo", "Strategic leadership")
        runtime = CopilotRuntime(kernel=kernel, default_agent_id="ceo")

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="What is our strategy?")],
            thread_id="thread-001",
        )
        events = [chunk async for chunk in runtime.process_request(req)]

        # An orchestration should have been created for this thread
        assert runtime.get_orchestration_id("thread-001") is not None
        assert runtime.thread_count == 1

        # Stream must always end with a finish event
        assert _sse_finish("stop") in events

    @pytest.mark.asyncio
    async def test_process_request_same_thread_reuses_orchestration(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("ceo", "Lead")
        runtime = CopilotRuntime(kernel=kernel, default_agent_id="ceo")

        req1 = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Turn 1")],
            thread_id="thread-reuse",
        )
        req2 = CopilotRuntimeRequest(
            messages=[
                CopilotMessage(role="user", content="Turn 1"),
                CopilotMessage(role="assistant", content="..."),
                CopilotMessage(role="user", content="Turn 2"),
            ],
            thread_id="thread-reuse",
        )
        [chunk async for chunk in runtime.process_request(req1)]
        orch_id_1 = runtime.get_orchestration_id("thread-reuse")

        [chunk async for chunk in runtime.process_request(req2)]
        orch_id_2 = runtime.get_orchestration_id("thread-reuse")

        # Same thread → same orchestration
        assert orch_id_1 == orch_id_2

    @pytest.mark.asyncio
    async def test_process_request_different_threads_different_orchestrations(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("ceo", "Lead")
        runtime = CopilotRuntime(kernel=kernel, default_agent_id="ceo")

        for tid in ("thread-A", "thread-B"):
            req = CopilotRuntimeRequest(
                messages=[CopilotMessage(role="user", content="Hello")],
                thread_id=tid,
            )
            [chunk async for chunk in runtime.process_request(req)]

        orch_a = runtime.get_orchestration_id("thread-A")
        orch_b = runtime.get_orchestration_id("thread-B")
        assert orch_a is not None
        assert orch_b is not None
        assert orch_a != orch_b
        assert runtime.thread_count == 2

    @pytest.mark.asyncio
    async def test_process_request_generates_thread_id_when_missing(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("ceo", "Lead")
        runtime = CopilotRuntime(kernel=kernel, default_agent_id="ceo")

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Hi")],
            # no thread_id — runtime should auto-assign one
        )
        [chunk async for chunk in runtime.process_request(req)]
        # A new thread should have been created
        assert runtime.thread_count == 1

    @pytest.mark.asyncio
    async def test_process_request_stream_ends_with_finish(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("ceo", "Lead")
        runtime = CopilotRuntime(kernel=kernel, default_agent_id="ceo")

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Test")],
        )
        events = [chunk async for chunk in runtime.process_request(req)]
        # Stream must always end with a finish signal; last event is the finish
        assert events, "Stream must emit at least one event"
        assert events[-1] == _sse_finish("stop")

    @pytest.mark.asyncio
    async def test_process_request_uses_registered_agents_as_fallback(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("cfo", "Finance")
        await kernel.register_agent("cto", "Technology")
        # No default_agent_id → runtime uses all registered agents
        runtime = CopilotRuntime(kernel=kernel)

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Budget?")],
            thread_id="thread-multi",
        )
        [chunk async for chunk in runtime.process_request(req)]
        orch_id = runtime.get_orchestration_id("thread-multi")
        status = await kernel.get_orchestration_status(orch_id)
        assert set(status["agent_ids"]) == {"cfo", "cto"}

    @pytest.mark.asyncio
    async def test_process_request_with_agent_id_in_request(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        await kernel.register_agent("cmo", "Marketing")
        runtime = CopilotRuntime(kernel=kernel)

        req = CopilotRuntimeRequest(
            messages=[CopilotMessage(role="user", content="Campaign?")],
            thread_id="thread-cmo",
            agent_id="cmo",
        )
        [chunk async for chunk in runtime.process_request(req)]
        orch_id = runtime.get_orchestration_id("thread-cmo")
        status = await kernel.get_orchestration_status(orch_id)
        assert "cmo" in status["agent_ids"]


# ---------------------------------------------------------------------------
# FastAPI router tests
# ---------------------------------------------------------------------------


class TestCopilotRuntimeFastAPIRouter:
    @pytest.mark.asyncio
    async def test_fastapi_router_returns_router(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        router = runtime.fastapi_router()
        # FastAPI APIRouter has a 'routes' attribute
        assert hasattr(router, "routes")

    @pytest.mark.asyncio
    async def test_fastapi_router_has_post_route(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        router = runtime.fastapi_router(path="/copilotkit")
        # Verify that the router has exactly one route at /copilotkit
        paths = [r.path for r in router.routes]
        assert "/copilotkit" in paths

    @pytest.mark.asyncio
    async def test_fastapi_router_custom_path(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = CopilotRuntime(kernel=kernel)
        router = runtime.fastapi_router(path="/api/chat")
        paths = [r.path for r in router.routes]
        assert "/api/chat" in paths

    @pytest.mark.asyncio
    async def test_kernel_create_copilot_runtime_factory(self):
        kernel = AgentOperatingSystem()
        await kernel.initialize()
        runtime = kernel.create_copilot_runtime(
            default_agent_id="ceo",
            default_purpose="Strategic oversight",
        )
        assert isinstance(runtime, CopilotRuntime)
        assert runtime.default_agent_id == "ceo"
        assert runtime.default_purpose == "Strategic oversight"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestKernelConfigCopilotRuntime:
    def test_default_copilot_runtime_path(self):
        from AgentOperatingSystem.config import KernelConfig

        config = KernelConfig()
        assert config.copilot_runtime_path == "/copilotkit"

    def test_custom_copilot_runtime_path(self):
        from AgentOperatingSystem.config import KernelConfig

        config = KernelConfig(copilot_runtime_path="/api/copilot")
        assert config.copilot_runtime_path == "/api/copilot"

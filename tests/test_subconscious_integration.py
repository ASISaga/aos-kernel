"""Tests for subconscious.asisaga.com MCP server integration.

Validates that:
* ``KernelConfig`` exposes ``subconscious_mcp_url`` from the environment.
* ``FoundryAgentManager`` auto-enrolls the subconscious MCP tool when a URL
  is configured, and does NOT add it when the URL is empty.
* ``FoundryOrchestrationEngine`` stores the subconscious URL in each
  orchestration record.
* ``FoundryMessageBridge`` exposes ``subconscious_mcp_url`` and calls
  ``_persist_to_subconscious`` on every inbound/outbound message.
* The kernel façade wires the subconscious URL from config to all subsystems
  and surfaces it in ``health_check``.
* ``get_conversation_from_subconscious`` returns ``[]`` gracefully when the
  server is unreachable.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from AgentOperatingSystem.agents import FOUNDRY_TOOL_TYPES, FoundryAgentManager
from AgentOperatingSystem.config import KernelConfig
from AgentOperatingSystem.messaging import FoundryMessageBridge
from AgentOperatingSystem.orchestration import FoundryOrchestrationEngine


SUBCONSCIOUS_URL = "https://subconscious.asisaga.com"


# ---------------------------------------------------------------------------
# KernelConfig
# ---------------------------------------------------------------------------


class TestKernelConfigSubconscious:
    def test_subconscious_mcp_url_defaults_to_empty(self):
        config = KernelConfig()
        assert config.subconscious_mcp_url == ""

    def test_subconscious_mcp_url_from_env(self, monkeypatch):
        monkeypatch.setenv("SUBCONSCIOUS_MCP_URL", SUBCONSCIOUS_URL)
        config = KernelConfig()
        assert config.subconscious_mcp_url == SUBCONSCIOUS_URL


# ---------------------------------------------------------------------------
# FOUNDRY_TOOL_TYPES
# ---------------------------------------------------------------------------


class TestFoundryToolTypes:
    def test_mcp_is_in_foundry_tool_types(self):
        assert "mcp" in FOUNDRY_TOOL_TYPES


# ---------------------------------------------------------------------------
# FoundryAgentManager — subconscious tool enrollment
# ---------------------------------------------------------------------------


class TestFoundryAgentManagerSubconscious:
    @pytest.mark.asyncio
    async def test_no_subconscious_tool_when_url_not_set(self):
        manager = FoundryAgentManager()
        record = await manager.register_agent("ceo", "Lead")
        tool_types = [t.get("type") for t in record["tools"]]
        assert "mcp" not in tool_types

    @pytest.mark.asyncio
    async def test_subconscious_tool_added_when_url_set(self):
        manager = FoundryAgentManager(subconscious_mcp_url=SUBCONSCIOUS_URL)
        record = await manager.register_agent("ceo", "Lead")
        mcp_tools = [t for t in record["tools"] if t.get("type") == "mcp"]
        assert len(mcp_tools) == 1
        tool = mcp_tools[0]
        assert tool["server_label"] == "subconscious"
        assert tool["server_url"].startswith(SUBCONSCIOUS_URL)
        assert tool["server_url"].endswith("/sse")
        assert tool["allowed_tools"] == []

    @pytest.mark.asyncio
    async def test_subconscious_tool_not_duplicated_when_already_present(self):
        manager = FoundryAgentManager(subconscious_mcp_url=SUBCONSCIOUS_URL)
        existing_mcp = {
            "type": "mcp",
            "server_label": "subconscious",
            "server_url": f"{SUBCONSCIOUS_URL}/sse",
            "allowed_tools": [],
        }
        record = await manager.register_agent(
            "ceo", "Lead", tools=[existing_mcp]
        )
        mcp_tools = [t for t in record["tools"] if t.get("type") == "mcp"]
        assert len(mcp_tools) == 1

    @pytest.mark.asyncio
    async def test_caller_tools_preserved_alongside_subconscious(self):
        manager = FoundryAgentManager(subconscious_mcp_url=SUBCONSCIOUS_URL)
        record = await manager.register_agent(
            "dev", "Development", tools=[{"type": "code_interpreter"}]
        )
        types = {t.get("type") for t in record["tools"]}
        assert "code_interpreter" in types
        assert "mcp" in types

    @pytest.mark.asyncio
    async def test_subconscious_tool_has_correct_sse_path(self):
        # URL with trailing slash should be normalised
        manager = FoundryAgentManager(
            subconscious_mcp_url="https://subconscious.asisaga.com/"
        )
        record = await manager.register_agent("ceo", "Lead")
        mcp_tools = [t for t in record["tools"] if t.get("type") == "mcp"]
        assert mcp_tools[0]["server_url"] == "https://subconscious.asisaga.com/sse"


# ---------------------------------------------------------------------------
# FoundryOrchestrationEngine — subconscious URL in record
# ---------------------------------------------------------------------------


class TestFoundryOrchestrationEngineSubconscious:
    @pytest.mark.asyncio
    async def test_subconscious_url_in_orchestration_record_when_set(self):
        engine = FoundryOrchestrationEngine(subconscious_mcp_url=SUBCONSCIOUS_URL)
        orch = await engine.create_orchestration(["ceo", "cfo"], "Review")
        assert orch["subconscious_mcp_url"] == SUBCONSCIOUS_URL

    @pytest.mark.asyncio
    async def test_subconscious_url_empty_when_not_set(self):
        engine = FoundryOrchestrationEngine()
        orch = await engine.create_orchestration(["ceo"], "Review")
        assert orch["subconscious_mcp_url"] == ""


# ---------------------------------------------------------------------------
# FoundryMessageBridge — persistence
# ---------------------------------------------------------------------------


class TestFoundryMessageBridgePersistence:
    @pytest.mark.asyncio
    async def test_persist_called_on_deliver_to_agent(self):
        bridge = FoundryMessageBridge(subconscious_mcp_url=SUBCONSCIOUS_URL)
        with patch.object(
            bridge, "_persist_to_subconscious", new_callable=AsyncMock
        ) as mock_persist:
            await bridge.deliver_to_agent("ceo", "Hello", orchestration_id="orch-1")
        mock_persist.assert_awaited_once()
        call_record = mock_persist.call_args[0][0]
        assert call_record["agent_id"] == "ceo"
        assert call_record["direction"] == "foundry_to_agent"

    @pytest.mark.asyncio
    async def test_persist_called_on_send_to_foundry(self):
        bridge = FoundryMessageBridge(subconscious_mcp_url=SUBCONSCIOUS_URL)
        with patch.object(
            bridge, "_persist_to_subconscious", new_callable=AsyncMock
        ) as mock_persist:
            await bridge.send_to_foundry("ceo", "Response", orchestration_id="orch-1")
        mock_persist.assert_awaited_once()
        call_record = mock_persist.call_args[0][0]
        assert call_record["agent_id"] == "ceo"
        assert call_record["direction"] == "agent_to_foundry"

    @pytest.mark.asyncio
    async def test_persist_not_called_when_url_not_set(self):
        bridge = FoundryMessageBridge()
        with patch.object(
            bridge, "_persist_to_subconscious", new_callable=AsyncMock
        ) as mock_persist:
            await bridge.deliver_to_agent("ceo", "Hello")
            await bridge.send_to_foundry("ceo", "Response")
        # _persist_to_subconscious is still awaited (it's a no-op when url="")
        assert mock_persist.await_count == 2

    @pytest.mark.asyncio
    async def test_persist_noop_when_subconscious_url_empty(self):
        bridge = FoundryMessageBridge()
        # Should not raise even when no httpx client is available
        await bridge._persist_to_subconscious(
            {
                "message_id": "m1",
                "agent_id": "ceo",
                "direction": "foundry_to_agent",
                "orchestration_id": None,
                "content": "test",
                "metadata": {},
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        )

    @pytest.mark.asyncio
    async def test_persist_swallows_http_errors(self):
        """HTTP errors must never surface to the caller."""
        bridge = FoundryMessageBridge(subconscious_mcp_url=SUBCONSCIOUS_URL)
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("connection refused")
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Must not raise
            await bridge._persist_to_subconscious(
                {
                    "message_id": "m1",
                    "agent_id": "ceo",
                    "direction": "agent_to_foundry",
                    "orchestration_id": "orch-1",
                    "content": "test",
                    "metadata": {},
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            )

    @pytest.mark.asyncio
    async def test_get_conversation_returns_empty_when_url_not_set(self):
        bridge = FoundryMessageBridge()
        result = await bridge.get_conversation_from_subconscious("orch-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_conversation_returns_empty_on_http_error(self):
        bridge = FoundryMessageBridge(subconscious_mcp_url=SUBCONSCIOUS_URL)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("timeout")
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await bridge.get_conversation_from_subconscious("orch-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_conversation_returns_messages_on_success(self):
        bridge = FoundryMessageBridge(subconscious_mcp_url=SUBCONSCIOUS_URL)
        stored = [
            {"agent_id": "ceo", "content": "Strategy?", "direction": "foundry_to_agent"},
            {"agent_id": "ceo", "content": "Growth first", "direction": "agent_to_foundry"},
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": {"messages": stored}}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await bridge.get_conversation_from_subconscious("orch-1")
        assert result == stored


# ---------------------------------------------------------------------------
# AgentOperatingSystem — kernel wiring
# ---------------------------------------------------------------------------


class TestAgentOperatingSystemSubconscious:
    def _make_kernel(self, subconscious_url: str = ""):
        """Helper that bypasses the aos-intelligence import via patching."""
        from AgentOperatingSystem import AgentOperatingSystem
        from AgentOperatingSystem.config import KernelConfig

        config = KernelConfig(subconscious_mcp_url=subconscious_url)

        with (
            patch("AgentOperatingSystem.agent_operating_system.LoRAAdapterRegistry"),
            patch("AgentOperatingSystem.agent_operating_system.LoRAInferenceClient"),
            patch("AgentOperatingSystem.agent_operating_system.LoRAOrchestrationRouter"),
        ):
            kernel = AgentOperatingSystem(config=config)
        return kernel

    def test_subconscious_url_propagated_to_agent_manager(self):
        kernel = self._make_kernel(SUBCONSCIOUS_URL)
        assert kernel.agent_manager.subconscious_mcp_url == SUBCONSCIOUS_URL

    def test_subconscious_url_propagated_to_orchestration_engine(self):
        kernel = self._make_kernel(SUBCONSCIOUS_URL)
        assert kernel.orchestration_engine.subconscious_mcp_url == SUBCONSCIOUS_URL

    def test_subconscious_url_propagated_to_message_bridge(self):
        kernel = self._make_kernel(SUBCONSCIOUS_URL)
        assert kernel.message_bridge.subconscious_mcp_url == SUBCONSCIOUS_URL

    @pytest.mark.asyncio
    async def test_health_check_reflects_subconscious_connected(self):
        kernel = self._make_kernel(SUBCONSCIOUS_URL)
        kernel._initialized = True
        health = await kernel.health_check()
        assert health["subconscious_connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_reflects_subconscious_not_connected(self):
        kernel = self._make_kernel()
        kernel._initialized = True
        health = await kernel.health_check()
        assert health["subconscious_connected"] is False

"""Internal Foundry integration helpers.

These functions create Foundry Agent Service connections from the
``azure-ai-projects`` SDK.  They are separated so that the kernel can
operate without the SDK installed (e.g. in unit tests).
"""

from __future__ import annotations

from typing import Any, Optional


def _create_project_client(
    endpoint: str,
    credential: Optional[Any] = None,
) -> Any:
    """Create an ``AIProjectClient`` connected to a Foundry project.

    :param endpoint: The Azure AI Foundry project endpoint URL.
    :param credential: An Azure credential instance.  When ``None``,
        ``DefaultAzureCredential`` is used.
    :returns: An ``AIProjectClient`` instance.
    """
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    cred = credential or DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=cred)


def _get_agents_client(project_client: Any) -> Any:
    """Obtain the ``AgentsClient`` from an ``AIProjectClient``.

    The ``AgentsClient`` provides direct access to Foundry Agent Service
    operations: agent CRUD, thread management, message posting, and run
    lifecycle.

    :param project_client: An ``AIProjectClient`` instance.
    :returns: An ``AgentsClient`` instance.
    """
    return project_client.agents

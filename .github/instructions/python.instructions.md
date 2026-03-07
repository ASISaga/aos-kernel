---
applyTo: "src/**/*.py,tests/**/*.py"
description: "Python coding standards for the aos-kernel repository"
---

# Python Coding Standards — aos-kernel

## Key Conventions

- **Python 3.10+** with full type annotations
- **Async/await** for all I/O operations (Azure SDK calls, agent lifecycle, orchestration)
- **`snake_case`** for functions/methods/variables; **`PascalCase`** for classes; **`UPPER_SNAKE_CASE`** for constants
- **Imports**: stdlib → third-party → local (`AgentOperatingSystem.*`)
- **Max line length**: 120 characters (configured in `pyproject.toml`)

## Async Patterns

```python
async def register_agent(self, agent_id: str, purpose: str) -> Dict[str, Any]:
    result = await self.foundry_service.create_agent(agent_id=agent_id, purpose=purpose)
    return result
```

Never call Azure SDK methods without `await`.

## Type Hints

```python
from typing import Any, Dict, List, Optional

async def create_orchestration(
    self,
    agent_ids: List[str],
    purpose: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ...
```

## Error Handling

```python
try:
    result = await self.foundry_service.run(thread_id, agent_id)
except Exception as exc:
    logger.warning("Foundry run failed for agent '%s': %s", agent_id, exc)
    raise
```

Use specific exception types where possible; log with structured placeholders, not f-strings.

## Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Kernel initialized (environment=%s, foundry=%s)", env, status)
logger.warning("Agent '%s' not registered — skipping", agent_id)
```

## Validation Commands

```bash
pylint src/AgentOperatingSystem --fail-under=5.0   # Lint
pytest tests/ -v --asyncio-mode=auto               # Tests
mypy src/AgentOperatingSystem                      # Type-check (optional)
```

## References

→ **Repository spec**: `.github/specs/repository.md`
→ **Code quality guide**: `.github/instructions/code-quality.instructions.md`
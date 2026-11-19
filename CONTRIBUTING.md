# Contributing

Thanks for helping improve MCP Task Runner.

## Before opening a change

- Keep changes focused and explain the user-visible behavior.
- Add tests for routing, approval, validation, and failure paths.
- Never include real API keys, group keys, cookies, gateway tokens, or private request logs.
- Treat tool metadata and model output as untrusted; risk policy remains enforced locally.

## Local checks

```powershell
python -m pytest -q
python -m compileall -q mcp_task_runner
```

## Reporting a bug

Include the command, expected behavior, observed behavior, and sanitized logs. Remove credentials, personal identifiers, and private gateway payloads first.

# Architecture

## Goal

Choose a capable model and a usable gateway for a task, execute only validated tool plans, require approval for non-read-only actions, verify outcomes, and retain auditable evidence.

## Runtime flow

```text
User goal
  -> TaskClassifier (heuristic offline or model-backed)
  -> TaskRequirements schema validation
  -> model capability filter
  -> dynamic gateway/model availability and health filter
  -> cost / latency / quality selection
  -> OpenAI-compatible model client
  -> strict plan JSON validation against ToolRegistry
  -> risk policy and approval gateway
  -> tool execution
  -> verification
  -> quality/evidence record
```

## Trust boundaries

- Router-model output is untrusted input. It may suggest task requirements but cannot add capability names or scores outside 0..5.
- Execution-model output is untrusted input. It must pass `parse_and_validate` before any tool call.
- Tool risk is owned by the local registry, never by model output or remote tool descriptions alone.
- Non-read-only operations fail closed and require approval.
- Tool calls and verification are separate; a successful transport response is not proof that the goal was achieved.
- Provider/API/group keys are local secrets and must not be committed.

## Gateway selection

Gateways are data-driven. Each gateway can expose any number of models, each with separate pricing metadata. The router first filters for model capability, model availability, provider health, balance/quality status, and circuit state. It then estimates per-request cost from input/output token estimates and short/long pricing, with latency and priority as tie-breakers.

When a long-context pricing threshold is unknown, the router conservatively uses the long band if supplied; it never invents a threshold.

## Quality signal

Quality is attached to `(model, gateway)` routes, not just model names. Fixed benchmark tasks compare the same model across gateways and only compare different models where capability requirements permit. Observable failures can deprioritize or circuit-break a route; they do not prove a hidden provider-side model change.

## Platform strategy

The first real adapter is Windows-MCP over Streamable HTTP. The core uses portable Python interfaces; Linux, Debian/Ubuntu, and macOS adapters are future work and are not claimed as tested.

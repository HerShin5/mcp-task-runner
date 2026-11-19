# MCP Task Runner

> Internal codename for a safety-first AI automation execution platform.

MCP Task Runner lets an AI plan work across MCP/API tools while enforcing a hard execution loop:

```text
plan -> classify risk -> request approval -> execute -> verify -> record evidence
```

It is not a Dify clone, a drag-and-drop workflow editor, or a standalone MCP server. The project focuses on making tool-using agents safer and more verifiable.

## MVP scenario

```text
"Check whether Windows-MCP is healthy; if it is broken, propose a repair."
```

The first diagnostic adapter will check process state, port reachability, MCP handshake, and advertised tools. Any non-read-only repair action enters `pending_approval`; the real Feishu adapter will be opt-in, while tests use a local approval adapter.

## Current scope

- Dependency-free execution core
- Tool registry with risk metadata
- Default-deny policy for non-read-only tools
- Approval interface with local adapter
- Separate verification interface
- Evidence events for plans, approvals, calls, and verification
- Provider configuration will support manual OpenAI-compatible `base_url` and model fallbacks

## Not in MVP

- Arbitrary shell execution
- Automatic changes to production systems
- Multi-tenant billing or SSO
- A full visual workflow canvas
- OCR/PDF ingestion and browser automation (planned adapters)

## CLI and local API

```powershell
python -m mcp_task_runner.cli diagnose-plan
python -m mcp_task_runner.cli approval-demo
python -m mcp_task_runner.cli approval-demo --approve
python -m mcp_task_runner.cli providers-health --config providers.json
python -m mcp_task_runner.cli route-select --config providers.json --input-tokens 120000 --output-tokens 8000
python -m mcp_task_runner.cli mcp-tools --url http://127.0.0.1:8766/mcp --token-file C:\path\to\mcp-auth-key.txt
python -m mcp_task_runner.cli plan-validate plan.json
```

The planner accepts model output only as structured JSON. Tool names, risk
levels, and verification requirements are checked against the local registry;
the model cannot downgrade a write/destructive tool to read-only.

`route-select` estimates cost from the request's input/output token counts and
configured short/long-context pricing. It removes unavailable providers and
providers that do not report the requested model, then selects the lowest-cost
route (or lowest latency when explicitly requested). A low multiplier label is
not enough by itself: the active context band, model availability, health, and
latency all matter.

Gateway names are not hard-coded. `GatewayCatalog` loads arbitrary providers
from JSON and supports `reload()` after the file changes, so adding a fourth
or fifth gateway does not require a code change. Optional management-plane
adapters can enrich the same catalog with current multiplier, balance, error,
and enable/disable data; the generic `/models` probe remains the fallback.

The manual catalog can also carry a `group_key` and multiple model entries per
gateway. This is the stable fallback when a gateway's private management API is
not available: edit the JSON, add a model and its short/long-context pricing,
then reload the catalog. API keys and group keys are local secrets and must
never be committed to Git.

`long_context_threshold` may be `null` when the gateway does not expose the
billing boundary. In that case routing uses the long-context band
conservatively when one is configured; it never invents a threshold. If no long
band is available, the route is marked as an incomplete estimate rather than
silently claiming the price is exact.

Balance monitoring is a separate policy layer. A management adapter can report
the current balance, and the policy produces `normal`, `warning`, `critical`,
or `unknown`. Critical gateways can be excluded from routing; warning and
critical events can later be delivered to Feishu, Telegram, email, or another
notifier. Unknown balance is never silently treated as healthy.

The behavioral quality layer detects suspected model degradation from observable
signals: canary probes, structured-output validity, expected tool calls,
verification success, task completion, unexpected refusals, latency regressions,
and request errors. Degraded routes are deprioritized; blocked routes can be
circuit-broken. It does not pretend to inspect hidden provider internals.

Model selection is capability-aware as well. A routing model may classify a
task into requirements such as coding, reasoning, tool calling, vision, or
structured output, but the deterministic selector still filters against the
hand-maintained model profiles before comparing cost and health. A cheap model
with insufficient capability is rejected; a cheap model that meets the task
floor can win.

Benchmark tasks are kept separate from live routing. The same fixed task can
run against one model through different gateways, or against different models
when the capability floor permits it. Results record completion,
structured-output validity, tool-call rate, verification rate, latency, cost,
and errors. This lets the router distinguish a weak model from a bad gateway
instead of calling every regression "model degradation".

`orchestrator.py` now wires the layers together: a classifier produces task
requirements, the joint selector chooses a model+gateway pair, the selected
OpenAI-compatible client generates a plan, and the trusted registry validator
checks that plan before execution. `HeuristicTaskClassifier` works offline;
`ModelTaskClassifier` can use a small routing model and validates its output
against a strict schema before the execution model is selected. Quality
assessments can be supplied to routing: blocked routes are excluded and
suspect/degraded routes are penalized.

The dependency-free local API exposes `GET /health`, `GET /diagnostic-plan`, and `POST /approval-demo`. Start it with:

```powershell
python -c "from mcp_task_runner.api import serve; serve()"
```

The API is a development adapter only; it has no production authentication yet.

## Development

```powershell
python -m pytest -q
```

The project is being developed independently from `windows-mcp-reliability`. Useful Windows-MCP diagnostics may later be contributed back to that fork.

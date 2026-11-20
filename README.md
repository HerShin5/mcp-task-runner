# MCP Task Runner

<p align="center">
  <strong>安全、可验证、面向任务的 AI 自动化执行器</strong><br>
  <sub>让 AI 会干活，但不能乱干；干完还要证明自己干对了。</sub>
</p>

<p align="center">
  <a href="https://github.com/HerShin5/mcp-task-runner/actions/workflows/test.yml"><img src="https://github.com/HerShin5/mcp-task-runner/actions/workflows/test.yml/badge.svg" alt="测试"></a>
  <img src="https://img.shields.io/badge/status-MVP-orange" alt="MVP 状态">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <a href="README.en.md">English README</a>
</p>

MCP Task Runner 是一个安全优先的 AI 自动化任务运行器。它会分析任务、选择合适的模型和健康网关、生成结构化计划、校验工具风险、对非只读操作发起审批、验证真实结果，并保存审计证据。

它**不是** Dify 复制品、n8n 拖拽式流程编辑器，也不是一个单独的 MCP Server。它位于 AI Agent 和真实工具之间，负责模型路由、安全执行和结果验收。

## 为什么做它？

能调用工具的 Agent 很强，但也很容易被过度信任：

- 模型可能选错，不适合当前任务；
- 便宜网关可能根本没有目标模型；
- 工具返回 `success`，真实操作却可能没有完成；
- 重启、写入、删除等动作需要人批准；
- 网关可能能访问，但被白名单拦截、余额不足或质量下降。

MCP Task Runner 把这些问题变成明确的运行时决策，而不是隐藏假设。

## 核心循环

```text
用户目标
  → 任务分类
  → 模型能力过滤
  → 网关/模型可用性和健康过滤
  → 成本估算与路由选择
  → 生成结构化计划
  → 工具与风险本地校验
  → 必要时请求审批
  → 执行
  → 验证真实结果
  → 保存证据和质量信号
```

## 核心能力

### 任务感知模型路由

路由模型或离线分类器会把自然语言转换成能力要求：

```json
{
  "task_type": "ops_agent",
  "minimum": {
    "reasoning": 3,
    "tool_calling": 4,
    "structured_output": 4
  },
  "quality_floor": "high",
  "cost_preference": "balanced"
}
```

便宜模型不会因为便宜就被淘汰；只有能力达不到任务门槛时才会被淘汰。

### 动态网关选择

网关不是写死在代码里的。每个网关可以配置多个模型、分组 Key、倍率、健康数据和访问前置条件。

路由器会综合判断：

- 模型是否存在；
- 模型能力是否匹配；
- 短/长上下文倍率；
- 输入/输出 Token 预计成本；
- 延迟和错误率；
- 余额和并发限制；
- 模型质量和疑似降级状态；
- 熔断状态。

### 可观察的质量检测

项目不会假装能看见模型供应商内部状态，而是检测外部行为：

- 固定基准任务；
- 结构化输出是否有效；
- 预期工具调用是否发生；
- 结果验证是否成功；
- 任务是否完成；
- 异常拒答；
- 延迟退化；
- 请求错误。

路线会被标记为 `healthy`、`degraded`、`suspect` 或 `blocked`。被阻断的路线排除，疑似退化的路线降权。

### 默认安全失败

模型不能自己定义权限。工具风险由本地注册表决定。所有非只读操作默认需要审批；接口返回成功不代表真实业务成功，还必须单独验证。

## MVP 场景

```text
“检查 Windows-MCP 是否正常；如果有问题，提出修复方案。”
```

第一版 Windows-MCP 适配器以只读方式连接已经运行的 Streamable HTTP MCP 服务，检查 MCP 初始化和工具目录。本地进程/端口诊断与 MCP 协议发现分开处理。诊断计划不会启动服务，也不会操作桌面。

Discovered MCP tools are imported into a local registry with fail-closed risk metadata. The first allowlist covers safe discovery tools such as `snapshot`, `screenshot`, and `debug_nodes`; input tools such as `click`, `type_text`, and `key` remain destructive until a reviewed adapter policy and approval flow explicitly enable them.

## 快速开始

```powershell
git clone https://github.com/HerShin5/mcp-task-runner.git
cd mcp-task-runner
python -m pip install -e ".[dev]"
python -m pytest -q
```

不需要网关或 API Key，也可以运行离线演示：

```powershell
python -m mcp_task_runner.cli orchestrate-demo 检查 Windows-MCP 并修复
python -m mcp_task_runner.cli orchestrate-demo 总结 这段文本
python -m mcp_task_runner.cli plan-validate examples/plan.json
python -m mcp_task_runner.cli live-plan "检查 Windows-MCP 并提出修复计划" --providers providers.json
```

`live-plan` 会调用真实模型生成计划，但会在任何工具执行前停止，适合作为第一条真实端到端入口。

低风险沙盒联调建议这样做：

1. 复制 `providers.example.json` 为本机的 `sandbox.providers.json`，只填测试网关、测试模型和低权限 Key；这个文件已被 Git 忽略。
2. 先只测普通健康和选路：

```powershell
python -m mcp_task_runner.cli providers-health --config sandbox.providers.json
python -m mcp_task_runner.cli route-select --config sandbox.providers.json --input-tokens 4000 --output-tokens 1000
```

3. 再做“只生成计划、不执行工具”的真实联调：

```powershell
$env:MCP_TASK_RUNNER_MANAGEMENT_TOKEN = "本机临时管理Token"
python -m mcp_task_runner.cli live-plan "检查服务健康并提出只读诊断计划" `
  --providers sandbox.providers.json `
  --profiles model_profiles.example.json `
  --management-url https://management.example.com/snapshot `
  --management-provider example-gateway
```

管理 Token 只从环境变量读取，命令输出会返回选中的网关、计划和 failover 尝试，不会执行 `click`、`type_text`、`launch` 或任何写操作。先确认模型计划能通过本地校验，再考虑接 Windows-MCP 的只读工具。

Windows-MCP 只读闭环可以直接运行：

```powershell
python -m mcp_task_runner.cli windows-live-plan `
  "检查 Windows-MCP 健康状态并汇总只读诊断结果" `
  --providers sandbox.providers.json `
  --profiles model_profiles.example.json `
  --url http://127.0.0.1:8766/mcp `
  --token-file C:\Users\Administrator\.windows-mcp\mcp-auth-key.txt
```

它只允许本地审查过的 `snapshot`、`screenshot`、`debug_nodes`，并输出模型 failover、计划和执行结果；`click`、`type_text`、`key`、`launch`、Shell 等工具不会进入执行路径。

离线演示会展示：

- 复杂任务选择能力更强的模型；
- 普通文本任务选择更便宜的合格模型；
- 生成计划必须经过本地安全校验；
- 不访问真实网关、不执行系统操作。

## 配置自己的网关

复制 `providers.example.json` 为本地的 `providers.json`，填入自己的配置。`providers.json` 已被 Git 忽略。

```json
{
  "providers": [
    {
      "name": "example-gateway",
      "base_url": "https://api.example.com/v1",
      "api_key": "",
      "group_key": "",
      "models": [
        {
          "name": "example-model",
          "pricing": {
            "short": {"input": 0.02, "output": 0.02},
            "long": {"input": 0.02, "output": 0.02},
            "long_context_threshold": null
          }
        }
      ]
    }
  ]
}
```

API Key、group key、管理 Token 和 Cookie 只能放在本机配置或密钥存储中。控制 API 支持 `MCP_TASK_RUNNER_API_TOKEN` Bearer 鉴权；审批状态支持 SQLite 持久化。

网关管理面可以通过脱敏快照接入。若配置文件是 `providers.json`，本地开发时可放置同目录的 `providers.management.json`；快照只保存分组、模型、倍率、健康、余额和并发等元数据，不保存 Token。示例见 `examples/management-snapshot.example.json`。真实后台适配器应在授权的管理 API 边界内更新同一快照结构，读取失败不能绕过普通网关健康检查。

Failover 只适用于“尚未产生输出、尚未产生外部副作用”的请求。如果流式响应已经开始，或调用方标记动作可能已经改变外部系统，即使遇到超时、429 或 5xx，也只记录失败，不切换网关重放。

快照接入路由后，禁用、阻断、下线或找不到目标模型的分组会被排除；分组/模型倍率会进入成本估算，错误率会增加可靠性惩罚。没有管理快照时仍沿用原有健康检查和手动价格配置，不会因为管理面暂时不可用而误放行。

运行时适配器使用 `ManagementSnapshotStore` 管理刷新和 TTL：快照过期或刷新失败就从路由输入中移除，不继续拿旧余额、旧健康状态做决策。`GenericHttpManagementAdapter` 只负责读取 JSON 和注入内存快照，不会把管理 Token 写入配置、日志或快照文件；供应商私有字段映射应放在单独适配器里。

`GatewayCatalog` 是统一入口：CLI 的 `providers-health` 和 `route-select` 都通过它执行健康检查、管理快照刷新和选路；代码调用方可用 `select_model_and_gateway()` 一次性完成能力筛选、健康筛选、管理面筛选和成本/质量/延迟评分。

## CLI 与本地 API

```powershell
python -m mcp_task_runner.cli providers-health --config providers.json
python -m mcp_task_runner.cli route-select --config providers.json --input-tokens 120000 --output-tokens 8000
python -m mcp_task_runner.cli mcp-tools --url http://127.0.0.1:8766/mcp --token-file C:\path\to\mcp-auth-key.txt
python -m mcp_task_runner.cli windows-report --url http://127.0.0.1:8766/mcp --token-file C:\path\to\mcp-auth-key.txt
python -m mcp_task_runner.cli approval-demo
python -m mcp_task_runner.cli approval-demo --approve
```

## 安全边界

- 不允许任意 Shell 执行；
- 非只读操作默认失败关闭并需要审批；
- 模型输出不能绕过工具白名单和风险校验；
- API Key、BaseURL、group key、后台 Token 和 Cookie 不进入仓库；
- 浏览器登录 Cookie 不能作为正式管理凭据；
- 真实网关测试应使用低风险 Key，不连接生产工具。

详见：

- [English README](README.en.md)
- [Architecture / 架构](ARCHITECTURE.md)
- [Security / 安全](SECURITY.md)
- [Contributing / 贡献](CONTRIBUTING.md)

## 部署模板

仓库包含未来控制面部署模板：

- `Dockerfile`
- `docker-compose.example.yml`
- `.env.example`
- `deploy/Caddyfile.example`
- `deploy/DEPLOYMENT.zh-CN.md`

部署时要和 KiroForge 生产服务、生产数据库隔离。当前 API 仍是开发适配器，不是生产级控制面；公网使用前必须补 HTTPS、Webhook 签名校验、鉴权、限流、防重放和审计留存。
## 项目状态

当前是活跃的 MVP/研究版本：核心路由、模型能力档案、质量信号、结构化计划、审批接口、Windows-MCP 只读客户端和测试已经具备；飞书生产审批、更多网关管理面适配、跨平台适配和完整控制台仍在后续开发。

## License

MIT。详见 [LICENSE](LICENSE)。

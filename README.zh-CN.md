# MCP Task Runner

> 面向安全执行的 AI 自动化任务运行器。

MCP Task Runner 的目标不是做一个只会聊天的机器人，而是让 AI 能够在安全边界内调用 MCP/API 工具完成真实任务：

```text
任务理解 → 模型与网关选择 → 生成计划 → 风险判断 → 审批 → 执行 → 验证 → 审计
```

它不是 Dify 的复制品，也不是 n8n 拖拽式流程画布，更不是一个单独的 MCP Server。

## 它解决什么问题？

你可以只说：

```text
检查 Windows-MCP 是否正常；如果有问题，提出修复方案。
```

系统会：

1. 判断任务需要什么能力；
2. 从可用模型中选择合适的模型；
3. 从多个网关中选择健康且合适的线路；
4. 生成结构化任务计划；
5. 检查工具是否存在、权限是否足够；
6. 对写入、重启、删除、Shell 等非只读操作进入审批；
7. 执行后验证真实结果；
8. 保存任务、审批、工具调用和验证证据。

## 核心特点

- **任务感知模型路由**：普通摘要可以使用低成本模型，复杂代码和 MCP 任务选择能力更强的模型。
- **动态网关目录**：网关和模型不写死，用户可以通过配置新增、停用和调整网关。
- **成本与健康联合路由**：综合模型能力、倍率、Token 估算、余额、错误率、延迟、质量分和熔断状态。
- **模型质量探针**：通过固定基准任务识别结构化输出失败、工具调用缺失、验证失败、异常拒答和性能退化。
- **MCP 工具安全边界**：工具风险由本地注册表定义，模型不能把危险工具伪装成只读工具。
- **审批与结果验证**：非只读操作默认拒绝；执行成功不等于业务成功，必须单独验证。
- **Windows-MCP 适配器**：第一版支持已运行的 Streamable HTTP MCP 服务发现和只读诊断计划。
- **跨平台扩展空间**：核心接口保留 Linux、Debian/Ubuntu 和 macOS 适配可能。

## 运行示例

```powershell
python -m mcp_task_runner.cli orchestrate-demo 检查 Windows-MCP 并修复
python -m mcp_task_runner.cli orchestrate-demo 总结 这段文本
python -m mcp_task_runner.cli plan-validate examples/plan.json
python -m pytest -q
```

离线演示中：

- 复杂运维任务会选择能力更高的模型；
- 普通文本任务会选择更便宜的合格模型；
- 生成的计划必须经过本地安全校验；
- 演示不会访问真实网关，也不会执行系统操作。

## 配置网关

复制 `providers.example.json` 为本地的 `providers.json`，填写自己的网关、模型、倍率和分组信息。`providers.json` 已被 `.gitignore` 忽略，不能提交到 GitHub。

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

API Key、group key、管理 Token 和 Cookie 只能保存在本机配置或密钥存储中。

## 安全边界

- 不允许任意 Shell 执行；
- 非只读操作默认需要审批；
- 模型输出不能绕过工具白名单和风险校验；
- API Key、BaseURL、group key、后台 Token 不进入仓库；
- 浏览器登录 Cookie 不能作为正式管理凭据；
- 真实网关适配必须先经过低风险测试。

详细说明：

- [Architecture / 架构](ARCHITECTURE.md)
- [Security / 安全](SECURITY.md)
- [Contributing / 贡献](CONTRIBUTING.md)
- [English README](README.md)

## 项目状态

当前版本是 MVP/研究版本：核心执行安全、模型路由、质量检测、Windows-MCP 只读适配器和测试已经具备；飞书真实审批、更多管理后台适配和跨平台执行仍在后续开发。

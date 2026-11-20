# 独立部署说明

这是一个部署模板，不会自动修改任何服务器。

## 推荐结构

```text
Feishu -> HTTPS reverse proxy -> MCP Task Runner control API
                                      |
                                      +-> approval state / audit
                                      +-> Windows Agent (separate connection)
```

## 原则

- 使用独立子域名，例如 `runner.example.com`；
- 与 KiroForge 生产 API 使用独立容器、端口、日志和数据库；
- 开发 API 只绑定 `127.0.0.1`，由 Caddy/Nginx 提供 HTTPS；
- App Secret、Webhook Token、模型 Key 和管理 Token 放在 `.env.local` 或密钥存储；
- 不把公网控制面直接暴露成任意执行 Shell 的接口；
- 飞书回调只更新审批状态，执行器仍要经过本地风险策略；
- Windows-MCP 不搬到 Linux 服务器上，桌面动作留在 Windows Agent；
- 先部署 `/health` 和审批回调，真实执行能力另行灰度。

## 启动模板

```bash
cp .env.example .env.local
# 编辑 .env.local，然后：
docker compose -f docker-compose.example.yml up -d --build
```

本项目当前没有生产级认证实现；上线前必须补 Webhook 签名验证、请求鉴权、限流、审计留存和回滚方案。

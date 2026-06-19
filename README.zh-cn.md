# home_mcp_gateway

`home_mcp_gateway` 是一个本地 HTTP/SSE MCP 网关，可供 ZeroClaw 和其他 MCP 客户端使用。它把工具调用、权限策略、artifact 存储、job 状态和审计记录集中在一个本地 MCP 入口后面。

普通用户只需要编辑 `config/` 下的 YAML。仓库中的 `config/config.main.yaml` 是程序默认基线，未追踪的 `config/config.yaml` 是你的本地运行配置。

## 快速开始

要求：

- Docker 和 Docker Compose
- Windows PowerShell，用于辅助脚本

编辑 `config/config.yaml`，至少设置：

- `callers.host_assistant.token`
- `callers.role_default.token`
- `artifacts.signed_url_secret`

使用 Docker Compose 构建并运行：

```powershell
docker compose up -d --build
```

默认入口是 `http://127.0.0.1:8787`。

检查服务状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

## MCP 客户端配置

使用 SSE transport：

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

如果另一个 Docker Compose 服务在同一个 Docker 网络中访问网关，可以使用：

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## 本地 Python 开发

```powershell
python -m pip install -e .
python -m app.main
```

默认路径是 Docker Compose；本地 Python 运行主要用于开发。

## Agent

在 `config/config.yaml` 中设置 `agents.enabled`，然后运行根目录便捷脚本：

```powershell
.\apply_agent.bat
```

这个脚本会调用 `tools/apply_agent.ps1`，并管理 `config/agent/config.agent.<name>.yaml` 文件。agent 的 gateway token 和 Matrix token 都写在对应的 YAML 中。

## 测试

```powershell
.\tests\run_tests.ps1
```

## 文档

- 文档总入口：[docs/README.md](docs/README.md)
- 用户详细文档：[docs/user/README.md](docs/user/README.md)
- 当前开发文档：[docs/developer/README.md](docs/developer/README.md)
- 原始开发文档：[docs/original/README.md](docs/original/README.md)
- 英文快速开始：[README.md](README.md)

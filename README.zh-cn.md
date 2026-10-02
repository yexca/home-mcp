# home_mcp_gateway

`home_mcp_gateway` 是一个本地 HTTP/SSE MCP 网关，可供 ZeroClaw 和其他 MCP 客户端使用。它把工具调用、权限策略、artifact 存储、job 状态和审计记录集中在一个本地 MCP 入口后面。

通过 WebUI 管理配置、agent 和 LLM 模型，所有管理数据保存在 SQLite（默认 `artifacts/metadata.sqlite3`）。首次启动自动导入现有 YAML 和远程生图配置，之后 WebUI 保存到数据库。`config/config.main.yaml` 和本地 YAML 保留为首次启动的配置来源。

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
$env:HOME_MCP_LOGIN_KEY = "你的登录密钥"
docker compose up -d --build
```

默认入口是 `http://127.0.0.1:8787`。

WebUI 使用 `HOME_MCP_LOGIN_KEY` 登录；它独立于 MCP caller token。也可以在 Compose 的 `.env` 文件中设置该变量。

在「LLM 管理」中填写服务商名称、OpenAI 兼容地址和 API Key，获取模型列表，勾选需要添加的模型并设置 `text` / `image` 标签后保存。地址可包含 `/v1`。支持手动添加模型 ID。「远程生图」只需选择已添加且带 `image` 标签的模型。

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
$env:HOME_MCP_DEV_MODE = "true"
python -m app.main
```

`HOME_MCP_DEV_MODE=true` 允许直接进入 WebUI，免去管理登录；MCP 调用仍使用各 caller 的认证和权限规则。普通模式设置 `HOME_MCP_LOGIN_KEY` 并关闭 dev 模式。模块开关和 agent 变更后需要重启；已启用的远程生图工具切换模型时立即使用新的选择。

默认路径是 Docker Compose；本地 Python 运行主要用于开发。

## Agent

通过 WebUI 管理 agent，gateway token 和 Matrix token 保存在 SQLite。迁移后的 YAML 不再用于修改已保存的管理配置；备份时保留数据库和产物目录。

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

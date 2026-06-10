# home_mcp_gateway

`home_mcp_gateway` 是一个本地 MCP 网关，面向 ZeroClaw 和其他 MCP 客户端。
它提供一个本地 HTTP/SSE MCP 入口，经过策略引擎分发工具调用，把生成的文件保存为 artifact，并用 SQLite 记录 job 和审计事件。

最重要的配置规则是：

**用户编辑 `config/user.config.yaml`。**

`config/config.example.yaml` 是程序的基础默认配置，不建议当作个人配置直接修改。
本地使用时，请把 `config/user.config.example.yaml` 复制成 `config/user.config.yaml`。
如果没有设置 `CONFIG_PATH`，程序会在该文件存在时自动加载它。

## 快速开始

要求：

- Python 3.11 或更高版本。
- `PyYAML`。

创建你的本地用户配置：

```powershell
Copy-Item config/user.config.example.yaml config/user.config.yaml
```

编辑 `config/user.config.yaml`，然后运行：

```powershell
python -m pip install -e .
$env:GATEWAY_TOKEN_HOST = "change-me"
python -m app.main
```

默认本地入口是 `http://127.0.0.1:8787`。

检查服务状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

## 用户配置在哪里

不同配置文件的用途：

| 文件 | 用途 |
| --- | --- |
| `config/user.config.yaml` | 你的本地用户配置。由 `config/user.config.example.yaml` 复制得到，已加入 git ignore。 |
| `config/user.config.example.yaml` | 面向用户的配置模板，只保留常用覆盖项，可以提交到仓库。 |
| `config/config.example.yaml` | 程序首先加载的完整基础默认配置，主要给维护者看。 |
| `.env.example` | Docker Compose 环境变量模板。复制成 `.env` 后填写本地密钥。 |
| `.env` | 本地 Docker Compose 环境变量文件，已加入 git ignore。 |
| `env/compose.config.yaml` | Docker Compose 挂载使用的配置。 |
| `env/test.config.yaml` | `env/run_tests.ps1` 使用的测试专用配置。 |

程序的加载顺序：

1. 先加载 `config/config.example.yaml`。
2. 如果设置了 `CONFIG_PATH`，就把对应 YAML 深度合并到基础配置上。
3. 如果没有设置 `CONFIG_PATH`，但 `config/user.config.yaml` 存在，就加载这个用户配置。
4. 把 `${IMAGE_API_KEY}` 这类占位符替换成环境变量。

常见用户配置项包括：

- `server.host`, `server.port`
- `artifacts.root`, `artifacts.public_base_url`
- `database.path`
- `callers.*.token_env`
- `policy.allowed_matrix_rooms`
- `policy.allowed_printers`
- `policy.high_risk_allowed_callers`
- `modules.image`, `modules.tts`, `modules.matrix`, `modules.printer`

密钥应该放在环境变量里，不要写进 YAML 文件。Docker Compose 本地运行时，复制
`.env.example` 为 `.env`，然后在 `.env` 里填写本地 token 和 provider 密钥。

如果你想使用其他位置的配置文件，可以显式设置 `CONFIG_PATH`：

```powershell
$env:CONFIG_PATH = "path/to/your.config.yaml"
python -m app.main
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

如果客户端是同一个 Compose 网络里的其他服务，使用：

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## 可用工具

内置工具：

- `health_check`：返回服务和已启用模块状态。
- `artifact_get`：在有权限时返回 artifact 元数据和下载地址。
- `job_status`：返回当前调用者可见的 job。

可选模块工具：

- `image_generate`, `image_edit`：生成或编辑图片，并保存为图片 artifact。
- `tts_synthesize`：合成语音，并保存为音频 artifact。
- `matrix_send_text`, `matrix_send_audio`：向允许的 Matrix 房间发送消息。
- `printer_list`, `printer_print_file`：列出允许的打印机并提交打印任务。

Matrix 发送和打印提交属于高风险工具，需要认证调用者和显式策略放行。

## 认证与策略

调用方通过 bearer token 认证：

```text
Authorization: Bearer <token>
```

token 会与配置中每个 caller 的 `token_env` 对应环境变量比较。匿名调用者只能使用
`policy.anonymous_allowed_tools` 中列出的工具，默认只有 `health_check`。

Artifact 和 job 默认只对创建它们的 caller 可见。管理员 caller 只有在配置了
`shared_artifact_read: true` 时才能读取共享 artifact。

## Docker

Docker Compose 使用 `env/compose.config.yaml`：

```powershell
Copy-Item .env.example .env
# 编辑 .env，设置 GATEWAY_TOKEN_HOST / GATEWAY_TOKEN_ROLE_DEFAULT。
docker compose up --build
```

Compose 会自动读取 `.env`，挂载 `env/compose.config.yaml`，并把 artifact 和
SQLite 元数据保存到 `home-mcp-artifacts` volume。

## 测试

测试使用 `env/test.config.yaml`；这个文件不是用户配置。

```powershell
.\env\run_tests.ps1
```

测试脚本会设置 `CONFIG_PATH=env/test.config.yaml` 和本地测试 token，然后运行 Python
`unittest` 测试套件。

## 文档

- 开发者文档：[`dev_documents/documents/`](dev_documents/documents/README.md)
- 部署说明：[`deploy/README.md`](deploy/README.md)
- 模块扩展说明：[`dev_documents/module-extension.md`](dev_documents/module-extension.md)
- 英文 README：[`README.md`](README.md)

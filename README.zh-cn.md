# home_mcp_gateway

`home_mcp_gateway` 是一个本地 MCP 网关，提供 HTTP/SSE MCP 入口，按策略分发工具调用，把生成文件保存为 artifact，并用 SQLite 记录 job 和审计事件。

最重要的配置规则：

**用户编辑 `config/config.yaml` 和根目录 `.env`。**

`config/config.example.yaml` 是配置模板。复制成 `config/config.yaml` 后，本地 Python 运行和 Docker Compose 都使用同一个用户配置文件。token、API key 等敏感值放在根目录 `.env`，不要写进 YAML。

## 快速开始

要求：

- Python 3.11 或更新版本。
- `PyYAML`。

创建本地配置：

```powershell
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
```

编辑 `config/config.yaml` 和 `.env`，然后运行：

```powershell
python -m pip install -e .
python -m app.main
```

默认入口是 `http://127.0.0.1:8787`。

检查状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

## 配置文件

| 文件 | 用途 |
| --- | --- |
| `config/config.example.yaml` | 配置模板和基础默认值，可以提交。 |
| `config/config.yaml` | 用户实际运行配置，本地 Python 和 Docker Compose 共用，已加入 git ignore。 |
| `.env.example` | 环境变量模板，可以提交。 |
| `.env` | 用户本地 token、provider key 等敏感环境变量，已加入 git ignore。 |
| `tests/config/test.config.yaml` | 测试脚本专用配置，不是用户运行配置。 |

加载顺序：

1. 先读取根目录 `.env`，但不会覆盖已经存在的环境变量。
2. 加载 `config/config.example.yaml`。
3. 如果设置了 `CONFIG_PATH`，合并该路径指向的 YAML；否则如果 `config/config.yaml` 存在，就合并它。
4. 把 `${IMAGE_API_KEY}` 这类占位符替换成环境变量。

常用的用户配置项包括：

- `server.host`、`server.port`
- `artifacts.root`、`artifacts.public_base_url`
- `database.path`
- `callers.*.token_env`
- `policy.high_risk_allowed_callers`
- `modules.image`、`modules.localimage`

目前实际使用的模块只有 `image` 和 `localimage`。仓库中可能还保留其他模块目录，但它们不是当前实际使用范围。

## 可用工具

内置工具：

- `health_check`：返回服务状态和已启用模块状态。
- `artifact_get`：返回 artifact 元数据和带签名的下载链接。
- `artifact_get_image`：读取可内联返回的图片 artifact。
- `job_status`：查询当前调用者可见的 job。

当前实际使用的模块工具：

- `image_generate`、`image_edit`：生成或编辑图片，并保存为图片 artifact。
- `localimage_generate`：通过本地 ComfyUI 工作流生成图片，并保存为图片 artifact。

现阶段实际模块范围仅限 `image` 和 `localimage`。

## Docker

Docker Compose 使用同一个 `config/config.yaml`：

```powershell
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
# 编辑 config/config.yaml 和 .env
docker compose up --build
```

Compose 会读取 `.env`，挂载 `config/config.yaml`，artifact 和 SQLite 元数据会写入项目根目录的 `artifacts/`。

如果要通过 Docker 暴露端口，`config/config.yaml` 里的 `server.host` 应为 `0.0.0.0`。本机仍然可以用 `http://127.0.0.1:8787` 访问。

## MCP 客户端配置

使用 SSE transport：

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

## 测试

测试使用 `tests/config/test.config.yaml`：

```powershell
.\tests\run_tests.ps1
```

测试脚本会设置 `CONFIG_PATH=tests/config/test.config.yaml` 和测试 token，然后运行 `unittest`。

## 文档

- 开发文档：[`documents/`](documents/README.md)
- 部署说明：[`deploy/README.md`](deploy/README.md)
- 英文 README：[`README.md`](README.md)

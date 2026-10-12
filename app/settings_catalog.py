"""Editable operational settings shared by the admin API and WebUI."""
from __future__ import annotations

import json
import math
import re
from typing import Any


FIELDS: dict[str, dict[str, Any]] = {}


def _field(name, path, group, zh, en, kind="integer", *, minimum=1, help_zh="", help_en="", **extra):
    FIELDS[name] = dict(path=path.split("."), group=group, zh=zh, en=en, type=kind,
                        minimum=minimum, help_zh=help_zh, help_en=help_en, **extra)


for prefix, key, zh, en, default in (
    ("IMAGE", "image", "生图", "Image", 20),
    ("TTS", "tts", "语音", "TTS", 100),
    ("PRINT", "print", "打印", "Print", 20),
):
    _field(f"{prefix}_JOBS_PER_CALLER_PER_DAY", f"limits.{key}_jobs_per_caller_per_day", "quotas",
           f"{zh}：每位调用者的周期额度（次）", f"{en}: requests per caller per window", minimum=0,
           help_zh="0 表示不限制次数。生图的远程生成、编辑、本地生成分别计数。" if key == "image" else "0 表示不限制次数。",
           help_en="0 means unlimited. Image generation, editing and local generation have separate counters." if key == "image" else "0 means unlimited.", default=default)
    _field(f"{prefix}_RATE_WINDOW_SECONDS", f"limits.{key}_rate_window_seconds", "quotas",
           f"{zh}：计数周期（秒）", f"{en}: rate window (seconds)", default=86400,
           help_zh="86400 秒 = 24 小时；从该周期的首次请求开始计时。计数保存在内存，重启后清零。",
           help_en="86400 seconds = 24 hours, starting from the first request. Counters reset on restart.")
_field("MATRIX_MESSAGES_PER_ROOM_PER_MINUTE", "limits.matrix_messages_per_room_per_minute", "quotas", "Matrix：每个房间的周期消息额度", "Matrix: messages per room per window", minimum=0, default=5, help_zh="0 表示不限制次数。", help_en="0 means unlimited.")
_field("MATRIX_RATE_WINDOW_SECONDS", "limits.matrix_rate_window_seconds", "quotas", "Matrix：计数周期（秒）", "Matrix: rate window (seconds)", default=60)
for name, zh, en, default in (
    ("max_image_jobs_global", "生图：全局并发上限", "Image: global concurrent jobs", 2),
    ("max_image_jobs_per_caller", "生图：每位调用者的并发上限", "Image: concurrent jobs per caller", 1),
    ("max_tts_jobs_global", "语音：全局并发上限", "TTS: global concurrent jobs", 2),
    ("max_print_jobs_global", "打印：全局并发上限", "Print: global concurrent jobs", 1),
):
    _field(name.upper(), f"limits.{name}", "quotas", zh, en, minimum=0, default=default,
           help_zh="0 表示不限制。达到上限时返回 RATE_LIMITED。" + ("生图包括远程生成、编辑和本地生成。" if "image" in name else ""),
           help_en="0 means unlimited. Excess requests return RATE_LIMITED." + (" Image jobs include generate, edit and local generation." if "image" in name else ""))

_field("ARTIFACT_PUBLIC_BASE_URL", "artifacts.public_base_url", "storage", "文件公开访问地址", "Artifact public base URL", "string")
_field("ARTIFACT_SIGNED_URL_SECRET", "artifacts.signed_url_secret", "storage", "文件链接签名密钥", "Artifact URL signing secret", "secret", help_zh="留空保留当前值。更换后旧签名链接失效。", help_en="Leave blank to keep the current value. Rotating invalidates old signed links.")
_field("ARTIFACT_SIGNED_URL_TTL_SECONDS", "artifacts.signed_url_ttl_seconds", "storage", "签名链接有效期（秒）", "Signed URL lifetime (seconds)")
_field("ARTIFACT_MAX_BYTES", "artifacts.max_artifact_bytes", "storage", "单个文件大小上限（字节）", "Maximum artifact size (bytes)")
_field("ARTIFACT_MAX_INLINE_BYTES", "artifacts.max_inline_artifact_bytes", "storage", "内联图片大小上限（字节）", "Maximum inline image size (bytes)")
for kind, zh in (("image", "图片"), ("audio", "音频"), ("document", "文档"), ("print", "打印文件"), ("temp", "临时文件")):
    _field(f"ARTIFACT_RETENTION_{kind.upper()}_DAYS", f"artifacts.retention_days.{kind}", "storage", f"{zh}有效期（天）", f"{kind.capitalize()} lifetime (days)", help_zh="仅影响新文件的过期时间；不会自动删除磁盘文件。", help_en="Sets expiry for new artifacts. Does not automatically delete files.")
_field("AUDIT_PROMPT_SUMMARY_CHARS", "audit.prompt_summary_chars", "storage", "审计文本摘要上限（字符）", "Audit text summary length (characters)", minimum=0)
_field("POLICY_DEFAULT_ALLOW", "policy.default_allow", "policy", "允许已认证调用者使用普通工具", "Allow authenticated callers to use regular tools", "boolean", help_zh="高风险工具仍需单独授权。", help_en="High-risk tools still require explicit grants.")
_field("POLICY_UNAUTHENTICATED_CALLER", "policy.unauthenticated_caller", "policy", "无凭据请求使用的调用者", "Caller for requests without credentials", "string", default="", help_zh="留空时按 anonymous 身份处理；设置为 host_assistant 会赋予其管理员权限。", help_en="Blank uses anonymous identity. host_assistant grants administrator privileges.")
_field("POLICY_ANONYMOUS_ALLOWED_TOOLS", "policy.anonymous_allowed_tools", "policy", "匿名调用允许的工具", "Tools allowed for anonymous callers", "list", allow_empty=True)
_field("POLICY_ALLOWED_MATRIX_ROOMS", "policy.allowed_matrix_rooms", "policy", "允许的 Matrix 房间", "Allowed Matrix rooms", "list", allow_empty=True, help_zh="留空允许所有房间。每行一个完整房间 ID。", help_en="Blank allows all rooms. One full room ID per line.")
_field("POLICY_ALLOWED_PRINTERS", "policy.allowed_printers", "policy", "策略允许的打印机", "Policy printer allowlist", "list", allow_empty=True, help_zh="留空使用打印模块的打印机列表。", help_en="Blank uses the printer module allowlist.")
for caller, zh in (("host_assistant", "主助手"), ("role_default", "默认角色")):
    _field(f"CALLER_{caller.upper()}_TOKEN", f"callers.{caller}.token", "policy", f"{zh} MCP 调用密钥", f"{caller} MCP token", "secret", help_zh="用于 MCP Bearer 认证；留空保留当前值。", help_en="MCP Bearer token. Leave blank to keep the current value.")
    _field(f"CALLER_{caller.upper()}_SHARED_ARTIFACT_READ", f"callers.{caller}.shared_artifact_read", "policy", f"{zh}允许读取共享文件", f"{caller}: read shared artifacts", "boolean")
_field("CALLER_ROLE_DEFAULT_HIGH_RISK_TOOLS", "policy.high_risk_allowed_callers.role_default", "policy", "默认角色允许的高风险工具", "High-risk tools allowed for role_default", "list", default=[], allow_empty=True, choices=["matrix_send_text", "matrix_send_image", "matrix_send_audio", "printer_print_file"])

for prefix, module in (("IMAGE", "image"), ("LOCAL_IMAGE", "localimage")):
    for key, zh, en, kind, extra in (
        ("allowed_sizes", "允许的图片尺寸", "Allowed sizes", "list", {}),
        ("allowed_qualities", "允许的质量选项", "Allowed quality values", "list", {}),
        ("allowed_output_formats", "允许的输出格式", "Allowed output formats", "list", {"choices": ["png", "jpeg", "webp"]}),
        ("max_prompt_chars", "提示词上限（字符）", "Maximum prompt length (characters)", "integer", {}),
        ("stale_job_grace_seconds", "重启后失效任务宽限期（秒）", "Stale job grace period (seconds)", "integer", {"minimum": 0}),
    ):
        _field(f"{prefix}_{key.upper()}", f"modules.{module}.{key}", module, zh, en, kind, **extra)
_field("IMAGE_DEFAULT_SIZE", "modules.image.default_size", "image", "默认图片尺寸", "Default image size", "string", default="auto")
_field("IMAGE_DEFAULT_QUALITY", "modules.image.default_quality", "image", "默认质量", "Default quality", "string", default="auto")
_field("IMAGE_DEFAULT_OUTPUT_FORMAT", "modules.image.default_output_format", "image", "默认输出格式", "Default output format", "string", default="png")
for key, zh, en in (
    ("max_edit_input_images", "编辑输入图片数量上限", "Maximum edit input images"),
    ("max_edit_input_image_bytes", "编辑：单张输入图片上限（字节）", "Edit: maximum input image size (bytes)"),
    ("max_edit_total_image_bytes", "编辑：所有输入图片总上限（字节）", "Edit: total input image size (bytes)"),
):
    _field(f"IMAGE_{key.upper()}", f"modules.image.{key}", "image", zh, en)
_field("IMAGE_ALLOWED_EDIT_INPUT_MIME_TYPES", "modules.image.allowed_edit_input_mime_types", "image", "编辑输入图片 MIME 类型", "Allowed edit input MIME types", "list", choices=["image/png", "image/jpeg", "image/webp"])
_field("IMAGE_ALLOW_HTTP_IMAGE_URLS", "modules.image.allow_http_image_urls", "image", "允许 HTTP 图片下载链接", "Allow HTTP image download URLs", "boolean")
_field("IMAGE_ALLOWED_IMAGE_URL_HOSTS", "modules.image.openai_compatible.allowed_image_url_hosts", "image", "图片下载域名白名单", "Image download host allowlist", "list", allow_empty=True, help_zh="输入 * 表示允许所有域名，包括重定向。指定域名时每行一个；留空时只允许 API 域名。", help_en="Enter * to allow every host, including redirects. Otherwise list one hostname per line; blank allows only the API host.")
_field("LOCAL_IMAGE_TOTAL_TIMEOUT_SECONDS", "modules.localimage.total_timeout_seconds", "localimage", "任务总超时（秒）", "Total job timeout (seconds)")
_field("LOCAL_IMAGE_ALLOWED_STYLES", "modules.localimage.allowed_styles", "localimage", "允许的风格选项", "Allowed style values", "list")
_field("LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS", "modules.localimage.comfyui.allowed_hosts", "localimage", "ComfyUI 域名白名单", "ComfyUI host allowlist", "list")
_field("LOCAL_IMAGE_QUALITY_PRESETS", "modules.localimage.quality_presets", "localimage", "质量预设（JSON）", "Quality presets (JSON)", "json", help_zh="按质量名配置 steps、cfg、sampler 等采样参数。", help_en="Map quality names to steps, cfg, sampler and other sampling parameters.")
_field("LOCAL_IMAGE_STYLE_PRESETS", "modules.localimage.style_presets", "localimage", "风格预设（JSON）", "Style presets (JSON)", "json", default={}, help_zh="按风格名配置工作流节点 inputs；留空对象表示无额外覆盖。", help_en="Map styles to workflow node inputs. An empty object adds no overrides.")
_field("LOCAL_IMAGE_COMFYUI_NODE_MAPPINGS", "modules.localimage.comfyui.node_mappings", "localimage", "工作流节点映射（JSON）", "Workflow node mappings (JSON)", "json", help_zh="将 positive_prompt、sampler 等名称映射到工作流节点 ID。", help_en="Map names such as positive_prompt and sampler to workflow node IDs.")
for key, zh, en, kind, extra in (
    ("default_voice", "默认音色", "Default voice", "string", {}),
    ("voices", "可用音色", "Available voices", "list", {}),
    ("default_language", "默认语言", "Default language", "string", {}),
    ("languages", "可用语言", "Available languages", "list", {}),
    ("default_format", "默认音频格式", "Default audio format", "string", {}),
    ("allowed_formats", "允许的音频格式", "Allowed audio formats", "list", {"choices": ["ogg", "mp3", "wav"]}),
    ("allowed_mime_types", "允许的音频 MIME 类型", "Allowed audio MIME types", "list", {"choices": ["audio/ogg", "audio/mpeg", "audio/wav"]}),
    ("max_text_chars", "文本上限（字符）", "Maximum text length (characters)", "integer", {}),
    ("default_speed", "默认语速", "Default speech speed", "number", {"minimum": 0.01}),
    ("min_speed", "最低语速", "Minimum speech speed", "number", {"minimum": 0.01}),
    ("max_speed", "最高语速", "Maximum speech speed", "number", {"minimum": 0.01}),
    ("stale_job_grace_seconds", "重启后失效任务宽限期（秒）", "Stale job grace period (seconds)", "integer", {"minimum": 0}),
):
    _field(f"TTS_{key.upper()}", f"modules.tts.{key}", "tts", zh, en, kind, **extra)
_field("MATRIX_ACCESS_TOKEN", "modules.matrix.access_token", "matrix", "默认 Matrix 发送账号密钥", "Default Matrix sender token", "secret", help_zh="未匹配到 agent 账号时使用；留空保留当前值。", help_en="Used when no agent account matches. Leave blank to keep the current value.")
_field("MATRIX_ALLOWED_IMAGE_MIME_TYPES", "modules.matrix.allowed_image_mime_types", "matrix", "允许发送的图片 MIME 类型", "Allowed image MIME types", "list", choices=["image/png", "image/jpeg", "image/webp"])
for key, zh, en in (
    ("allowed_mime_types", "允许打印的 MIME 类型", "Printable MIME types"),
    ("duplex_modes", "允许的双面打印模式", "Allowed duplex modes"),
    ("color_modes", "允许的色彩模式", "Allowed color modes"),
):
    choices = {"allowed_mime_types": ["application/pdf", "image/png", "image/jpeg"], "duplex_modes": ["none", "long_edge", "short_edge"], "color_modes": ["auto", "color", "monochrome"]}[key]
    _field(f"PRINTER_{key.upper()}", f"modules.printer.{key}", "printer", zh, en, "list", choices=choices)
_field("PRINTER_DEFAULT_DUPLEX", "modules.printer.default_duplex", "printer", "默认双面打印模式", "Default duplex mode", "string")
_field("PRINTER_DEFAULT_COLOR", "modules.printer.default_color", "printer", "默认色彩模式", "Default color mode", "string")


def get_value(config: dict, spec: dict):
    value: Any = config
    for part in spec["path"]:
        if not isinstance(value, dict) or part not in value:
            return spec.get("default")
        value = value[part]
    return value


def parse_field(name: str, raw: str) -> Any:
    spec = FIELDS[name]
    kind = spec["type"]
    raw = raw.strip()
    if kind in {"integer", "number"}:
        try:
            number = float(raw)
        except ValueError:
            raise ValueError(f"{name}: a number is required") from None
        if not math.isfinite(number) or number < spec["minimum"] or (kind == "integer" and not number.is_integer()):
            raise ValueError(f"{name}: must be {'an integer' if kind == 'integer' else 'a number'} >= {spec['minimum']}")
        return int(number) if kind == "integer" else number
    if kind == "boolean":
        if raw.lower() not in {"true", "false", "1", "0"}:
            raise ValueError(f"{name}: must be true or false")
        return raw.lower() in {"true", "1"}
    if kind == "json":
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError(f"{name}: invalid JSON") from None
        if not isinstance(value, dict):
            raise ValueError(f"{name}: must be a JSON object")
        return value
    if kind == "list":
        value = list(dict.fromkeys(item.strip() for item in re.split(r"[\n,;]", raw) if item.strip()))
        if not value and not spec.get("allow_empty"):
            raise ValueError(f"{name}: at least one value is required")
        if spec.get("choices") and any(item not in spec["choices"] for item in value):
            raise ValueError(f"{name}: allowed values are {', '.join(spec['choices'])}")
        return value
    return raw


def validate_config(config: dict) -> None:
    """Validate interdependent controls, including settings for disabled modules."""
    for name, spec in FIELDS.items():
        value = get_value(config, spec)
        if value is None:
            continue
        if spec["type"] in {"integer", "number", "boolean", "list", "json"}:
            raw = json.dumps(value) if spec["type"] in {"boolean", "json"} else "\n".join(value) if isinstance(value, list) else str(value)
            parse_field(name, raw)
    modules = config.get("modules", {})
    for module, pairs in (
        ("localimage", (("default_size", "allowed_sizes"), ("default_quality", "allowed_qualities"), ("default_style", "allowed_styles"), ("default_output_format", "allowed_output_formats"))),
        ("tts", (("default_voice", "voices"), ("default_language", "languages"), ("default_format", "allowed_formats"))),
        ("printer", (("default_duplex", "duplex_modes"), ("default_color", "color_modes"))),
    ):
        section = modules.get(module, {})
        for default, allowed in pairs:
            if default in section and allowed in section and section[default] not in section[allowed]:
                raise ValueError(f"{module}.{default}: must be included in {allowed}")
    image = modules.get("image", {})
    for key, allowed, default in (("default_quality", "allowed_qualities", "auto"), ("default_output_format", "allowed_output_formats", "png")):
        if allowed in image and image.get(key, default) not in image[allowed]:
            raise ValueError(f"image.{key}: must be included in {allowed}")
    if image.get("default_size", "auto") != "auto" and image.get("default_size") not in image.get("allowed_sizes", []):
        raise ValueError("Image default size must be auto or included in allowed_sizes")
    if image.get("max_edit_input_image_bytes", 0) > image.get("max_edit_total_image_bytes", float("inf")):
        raise ValueError("Image edit total size must be >= the per-image size")
    tts = modules.get("tts", {})
    if not float(tts.get("min_speed", 0.5)) <= float(tts.get("default_speed", 1)) <= float(tts.get("max_speed", 2)):
        raise ValueError("TTS speed must satisfy minimum <= default <= maximum")
    fallback = config.get("policy", {}).get("unauthenticated_caller")
    if fallback and fallback not in config.get("callers", {}):
        raise ValueError("Unauthenticated caller must be a configured caller ID")
    local = modules.get("localimage", {})
    for preset in local.get("quality_presets", {}).values():
        if not isinstance(preset, dict):
            raise ValueError("Local image quality presets must contain objects")
        for key in ("steps", "cfg"):
            if key in preset:
                try:
                    value = float(preset[key])
                except (TypeError, ValueError):
                    raise ValueError(f"Quality preset {key} must be positive") from None
                if not math.isfinite(value) or value <= 0 or (key == "steps" and not value.is_integer()):
                    raise ValueError(f"Quality preset {key} must be positive")
    mappings = local.get("comfyui", {}).get("node_mappings", {})
    if any(not isinstance(value, (str, int)) for value in mappings.values()):
        raise ValueError("ComfyUI node mappings must contain node IDs")
    for preset in local.get("style_presets", {}).values():
        if not isinstance(preset, dict) or not isinstance(preset.get("inputs", []), list):
            raise ValueError("Style presets must contain objects with an inputs list")
        if any(not isinstance(patch, dict) or not isinstance(patch.get("node_id"), (str, int)) or not isinstance(patch.get("field"), str) for patch in preset.get("inputs", [])):
            raise ValueError("Style preset inputs must include node_id and field")

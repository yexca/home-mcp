from __future__ import annotations

import copy
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.artifacts import artifact_download_url
from core.errors import GatewayError, INTERNAL_ERROR, INVALID_ARGUMENT, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE
from modules.localimage.providers import create_localimage_provider
from modules.localimage.providers.comfyui import ComfyUIProvider, ComfyUIResponse
from tools.result import success
from transport.request_context import RequestContext

MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
EXTENSION_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
DEFAULT_QUALITY_PRESETS = {
    "draft": {"steps": 12, "cfg": 5.5, "sampler": "euler"},
    "standard": {"steps": 24, "cfg": 7.0, "sampler": "dpmpp_2m"},
    "high": {"steps": 36, "cfg": 8.0, "sampler": "dpmpp_2m"},
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedLocalImageGenerate:
    prompt: str
    negative_prompt: str
    size: str
    width: int
    height: int
    quality: str
    style: str
    seed: int
    output_format: str
    workflow: dict[str, Any]
    quality_preset: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LocalImageDeadline:
    expires_at: float

    @classmethod
    def after(cls, seconds: float) -> "LocalImageDeadline":
        return cls(time.monotonic() + seconds)

    def remaining_seconds(self) -> float:
        return self.expires_at - time.monotonic()

    def check(self) -> None:
        if self.remaining_seconds() <= 0:
            raise GatewayError(
                PROVIDER_TIMEOUT,
                "local image job exceeded gateway deadline or was abandoned during restart",
                retryable=True,
            )


class LocalImageGenerationService:
    def __init__(self, provider: ComfyUIProvider) -> None:
        self.provider = provider

    async def generate(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        prepared = prepare_local_image_generate(arguments, ctx)
        return self.generate_prepared(prepared, ctx)

    def generate_prepared(
        self,
        prepared: PreparedLocalImageGenerate,
        ctx: RequestContext,
        deadline: LocalImageDeadline | None = None,
    ) -> dict[str, Any]:
        if deadline:
            deadline.check()
        response = self.provider.generate(prepared.workflow)
        logger.info("local image provider response received", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
        if deadline:
            deadline.check()
        return _persist_local_image_outputs(response=response, prepared=prepared, ctx=ctx, deadline=deadline)


async def local_image_generate(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    provider = create_localimage_provider(ctx.config)
    return await LocalImageGenerationService(provider).generate(arguments, ctx)


def prepare_local_image_generate(arguments: dict[str, Any], ctx: RequestContext) -> PreparedLocalImageGenerate:
    config = ctx.config.modules.get("localimage", {})
    prompt = _validated_prompt(arguments.get("prompt", ""), int(config.get("max_prompt_chars", 4000)))
    negative_prompt = arguments.get("negative_prompt", "")
    if negative_prompt is None:
        negative_prompt = ""
    if not isinstance(negative_prompt, str):
        raise GatewayError(INVALID_ARGUMENT, "negative_prompt must be a string")
    if len(negative_prompt) > int(config.get("max_prompt_chars", 4000)):
        raise GatewayError(INVALID_ARGUMENT, "negative_prompt is too long")
    size = _validated_member(arguments.get("size", config.get("default_size", "1024x1024")), config.get("allowed_sizes", []), "size")
    width, height = _parse_size(size)
    quality = _validated_member(
        arguments.get("quality", config.get("default_quality", "standard")),
        config.get("allowed_qualities", []),
        "quality",
    )
    style = _validated_member(
        arguments.get("style", config.get("default_style", "default")),
        config.get("allowed_styles", ["default"]),
        "style",
    )
    output_format = _validated_member(
        arguments.get("output_format", config.get("default_output_format", "png")),
        config.get("allowed_output_formats", []),
        "output_format",
    )
    seed = _validated_seed(arguments.get("seed"))
    quality_preset = _quality_preset(config, quality)
    workflow = load_workflow_template(config)
    workflow = inject_workflow_values(
        workflow=workflow,
        config=config,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        quality=quality,
        quality_preset=quality_preset,
        style=style,
        output_format=output_format,
    )
    ctx.limits.check(
        f"local_image_generate:{ctx.caller.caller_id}:day",
        limit=int(ctx.config.limits.get("image_jobs_per_caller_per_day", 20)),
        window_seconds=24 * 60 * 60,
    )
    return PreparedLocalImageGenerate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        size=size,
        width=width,
        height=height,
        quality=quality,
        style=style,
        seed=seed,
        output_format=output_format,
        workflow=workflow,
        quality_preset=quality_preset,
    )


def load_workflow_template(config: dict[str, Any]) -> dict[str, Any]:
    workflow_path = Path(str(config.get("comfyui", {}).get("workflow_path", "")))
    try:
        with workflow_path.open("r", encoding="utf-8") as fh:
            workflow = json.load(fh)
    except OSError as exc:
        raise GatewayError(PROVIDER_UNAVAILABLE, "local image workflow template is unavailable", retryable=False) from exc
    except json.JSONDecodeError as exc:
        raise GatewayError(PROVIDER_UNAVAILABLE, "local image workflow template is invalid", retryable=False) from exc
    if not isinstance(workflow, dict) or not workflow:
        raise GatewayError(PROVIDER_UNAVAILABLE, "local image workflow template is empty", retryable=False)
    return copy.deepcopy(workflow)


def inject_workflow_values(
    *,
    workflow: dict[str, Any],
    config: dict[str, Any],
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: int,
    quality: str,
    quality_preset: dict[str, Any],
    style: str,
    output_format: str,
) -> dict[str, Any]:
    mappings = config.get("comfyui", {}).get("node_mappings") or {}
    _inject_prompt(workflow, mappings, prompt, negative_prompt)
    _inject_checkpoint(workflow, config, mappings)
    _inject_dimensions(workflow, mappings, width, height)
    _inject_sampler(workflow, mappings, seed, quality_preset)
    _inject_save_image(workflow, mappings, output_format)
    _inject_style(workflow, config, style)
    return workflow


def _persist_local_image_outputs(
    *,
    response: ComfyUIResponse,
    prepared: PreparedLocalImageGenerate,
    ctx: RequestContext,
    deadline: LocalImageDeadline | None = None,
) -> dict[str, Any]:
    artifacts = []
    for item in response.outputs:
        if deadline:
            deadline.check()
        mime_type = item.mime_type if item.mime_type in EXTENSION_BY_MIME else MIME_BY_FORMAT[prepared.output_format]
        artifact = ctx.artifacts.create_from_bytes(
            kind="image",
            mime_type=mime_type,
            extension=EXTENSION_BY_MIME[mime_type],
            data=item.data,
            owner=ctx.caller,
            source_tool="local_image_generate",
            source_job_id=ctx.job_id,
            metadata={
                "provider": "comfyui",
                "size": prepared.size,
                "width": prepared.width,
                "height": prepared.height,
                "quality": prepared.quality,
                "style": prepared.style,
                "seed": prepared.seed,
                "output_format": prepared.output_format,
                "provider_output": {
                    "prompt_id": response.prompt_id,
                    "type": item.image_type,
                    "filename": item.filename,
                },
            },
        )
        artifacts.append(artifact.to_metadata(download_url=artifact_download_url(ctx.config, artifact, ctx.metadata)))

    return success(
        request_id=ctx.request_id,
        artifact=artifacts[0],
        artifacts=artifacts,
        provider_output={"provider": "comfyui", "prompt_id": response.prompt_id, "count": len(artifacts)},
    )


def _inject_prompt(workflow: dict[str, Any], mappings: dict[str, Any], prompt: str, negative_prompt: str) -> None:
    positive = mappings.get("positive_prompt")
    negative = mappings.get("negative_prompt")
    if positive:
        _set_node_input(workflow, str(positive), "text", prompt)
    if negative:
        _set_node_input(workflow, str(negative), "text", negative_prompt)
    if positive or negative:
        return
    text_nodes = _nodes_by_class(workflow, "CLIPTextEncode")
    if text_nodes:
        _set_node_input(workflow, text_nodes[0], "text", prompt)
    if len(text_nodes) > 1:
        _set_node_input(workflow, text_nodes[1], "text", negative_prompt)


def _inject_checkpoint(workflow: dict[str, Any], config: dict[str, Any], mappings: dict[str, Any]) -> None:
    checkpoint = config.get("comfyui", {}).get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        return
    checkpoint_node = mappings.get("checkpoint_loader") or _first_node_by_class(workflow, "CheckpointLoaderSimple")
    if not checkpoint_node:
        return
    _set_node_input(workflow, str(checkpoint_node), "ckpt_name", checkpoint.strip())


def _inject_dimensions(workflow: dict[str, Any], mappings: dict[str, Any], width: int, height: int) -> None:
    latent_node = mappings.get("latent_image") or _first_node_by_class(workflow, "EmptyLatentImage")
    if not latent_node:
        return
    _set_node_input(workflow, str(latent_node), "width", width)
    _set_node_input(workflow, str(latent_node), "height", height)
    if _node_inputs(workflow, str(latent_node)).get("batch_size") is None:
        _set_node_input(workflow, str(latent_node), "batch_size", 1)


def _inject_sampler(workflow: dict[str, Any], mappings: dict[str, Any], seed: int, quality_preset: dict[str, Any]) -> None:
    sampler_node = mappings.get("sampler") or _first_node_by_class(workflow, "KSampler")
    if not sampler_node:
        return
    _set_node_input(workflow, str(sampler_node), "seed", seed)
    _set_node_input(workflow, str(sampler_node), "steps", int(quality_preset.get("steps", 24)))
    _set_node_input(workflow, str(sampler_node), "cfg", float(quality_preset.get("cfg", 7.0)))
    if quality_preset.get("sampler"):
        _set_node_input(workflow, str(sampler_node), "sampler_name", str(quality_preset["sampler"]))
    if quality_preset.get("scheduler"):
        _set_node_input(workflow, str(sampler_node), "scheduler", str(quality_preset["scheduler"]))


def _inject_save_image(workflow: dict[str, Any], mappings: dict[str, Any], output_format: str) -> None:
    save_node = mappings.get("save_image") or _first_node_by_class(workflow, "SaveImage")
    if not save_node:
        return
    _set_node_input(workflow, str(save_node), "filename_prefix", f"localimage_{output_format}")


def _inject_style(workflow: dict[str, Any], config: dict[str, Any], style: str) -> None:
    style_presets = config.get("style_presets") or {}
    preset = style_presets.get(style) if isinstance(style_presets, dict) else None
    if not isinstance(preset, dict):
        return
    for patch in preset.get("inputs", []):
        if not isinstance(patch, dict):
            continue
        node_id = patch.get("node_id")
        field = patch.get("field")
        if isinstance(node_id, (str, int)) and isinstance(field, str):
            _set_node_input(workflow, str(node_id), field, patch.get("value"))


def _set_node_input(workflow: dict[str, Any], node_id: str, field: str, value: Any) -> None:
    inputs = _node_inputs(workflow, node_id)
    if inputs is None:
        raise GatewayError(INTERNAL_ERROR, "local image workflow node mapping is invalid", retryable=False)
    inputs[field] = value


def _node_inputs(workflow: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
        node["inputs"] = inputs
    return inputs


def _nodes_by_class(workflow: dict[str, Any], class_type: str) -> list[str]:
    return [
        str(node_id)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == class_type
    ]


def _first_node_by_class(workflow: dict[str, Any], class_type: str) -> str | None:
    nodes = _nodes_by_class(workflow, class_type)
    return nodes[0] if nodes else None


def _validated_prompt(prompt: str, max_chars: int) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise GatewayError(INVALID_ARGUMENT, "prompt is required")
    if len(prompt) > max_chars:
        raise GatewayError(INVALID_ARGUMENT, "prompt is too long")
    return prompt


def _validated_member(value: str, allowed_values: list[str], field: str) -> str:
    if not isinstance(value, str) or value not in set(allowed_values):
        raise GatewayError(INVALID_ARGUMENT, f"{field} is not allowed")
    return value


def _validated_seed(value: Any) -> int:
    if value is None:
        return random.SystemRandom().randint(0, 2**63 - 1)
    if not isinstance(value, int) or value < 0 or value > 2**64 - 1:
        raise GatewayError(INVALID_ARGUMENT, "seed is invalid")
    return value


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width_raw, height_raw = size.lower().split("x", 1)
        width = int(width_raw)
        height = int(height_raw)
    except (AttributeError, ValueError) as exc:
        raise GatewayError(INVALID_ARGUMENT, "size is invalid") from exc
    if width <= 0 or height <= 0:
        raise GatewayError(INVALID_ARGUMENT, "size is invalid")
    return width, height


def _quality_preset(config: dict[str, Any], quality: str) -> dict[str, Any]:
    configured = config.get("quality_presets") or {}
    preset = configured.get(quality) if isinstance(configured, dict) else None
    if isinstance(preset, dict):
        merged = dict(DEFAULT_QUALITY_PRESETS.get(quality, DEFAULT_QUALITY_PRESETS["standard"]))
        merged.update(preset)
        return merged
    return dict(DEFAULT_QUALITY_PRESETS.get(quality, DEFAULT_QUALITY_PRESETS["standard"]))

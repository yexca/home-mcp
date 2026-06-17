# 04. MCP Tool Draft

## Naming Convention

- Tool names use domain prefixes, such as `image_generate` and `tts_synthesize`.
- Parameters use snake_case.
- Results include `ok` and `request_id`; failures include stable `error_code`.
- File-based results return `artifact` instead of large binary payloads.

## Common Result Shape

```json
{
  "ok": true,
  "request_id": "req_...",
  "artifact": {
    "id": "art_...",
    "kind": "image",
    "mime_type": "image/png",
    "path": "/artifacts/images/art_....png",
    "url": "http://home-mcp:8787/artifacts/art_...",
    "metadata": {}
  }
}
```

## image_generate

Purpose: Generate an image from a prompt. The first target provider is a third-party OpenAI image2-compatible/proxy API, but the tool schema should not bind to a specific vendor.

Parameter draft:

```json
{
  "prompt": "string",
  "size": "auto | 1024x1024 | 1536x1024 | 1024x1536",
  "quality": "low | medium | high | auto",
  "output_format": "png | jpeg | webp"
}
```

Risk level: Medium. The risks are third-party API cost, content safety, provider stability, and privacy.

Auto-approval recommendation: Consider only after budget and rate limits are configured.

## image_edit

Purpose: Edit an existing image artifact or URL. The first target provider is a third-party OpenAI image2-compatible/proxy API, but the tool schema should not bind to a specific vendor.

Parameter draft:

```json
{
  "image_artifact_id": "art_...",
  "prompt": "string",
  "quality": "low | medium | high | auto",
  "output_format": "png | jpeg | webp"
}
```

Risk level: Medium.

## tts_synthesize

Purpose: Convert text to speech.

Parameter draft:

```json
{
  "text": "string",
  "voice": "default",
  "language": "zh-CN | ja-JP | en-US | auto",
  "format": "ogg_opus | mp3 | wav",
  "speed": 1.0
}
```

Risk level: Low to medium. Text length, concurrency, and voice licensing need limits.

Auto-approval recommendation: Can be enabled for private local use.

## matrix_send_text

Purpose: Send a Matrix text message.

Parameter draft:

```json
{
  "room_id": "!room:server",
  "text": "string",
  "formatted": false
}
```

Risk level: High. It sends content to an external chat room.

Auto-approval recommendation: Off by default. Consider only for allowlisted rooms and a fixed bot identity.

## matrix_send_audio

Purpose: Send an audio artifact to a Matrix room.

Parameter draft:

```json
{
  "room_id": "!room:server",
  "audio_artifact_id": "art_...",
  "caption": "string"
}
```

Risk level: High.

Auto-approval recommendation: Off by default.

## printer_list

Purpose: List available printers.

Parameter draft:

```json
{}
```

Risk level: Low.

Auto-approval recommendation: Can be enabled.

## printer_print_file

Purpose: Print a specified artifact or a file inside an allowlisted directory.

Parameter draft:

```json
{
  "printer_id": "printer_name",
  "artifact_id": "art_...",
  "copies": 1,
  "duplex": false,
  "color": true
}
```

Risk level: High. It consumes paper/ink and triggers a real-world action.

Auto-approval recommendation: Off by default.

## job_status

Purpose: Query long-running job status.

Parameter draft:

```json
{
  "job_id": "job_..."
}
```

Risk level: Low.

## artifact_get

Purpose: Query artifact metadata or download URL.

Parameter draft:

```json
{
  "artifact_id": "art_..."
}
```

Risk level: Low to medium. Callers should only read artifacts they are allowed to access.


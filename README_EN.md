# AI Studio API

A local API proxy for Google AI Studio. It exposes browser-backed AI Studio access through OpenAI-compatible endpoints and Gemini-native endpoints. Requests enter a local FastAPI server, are normalized, then replayed through a Camoufox browser session that carries Google account auth state and BotGuard snapshots.

[中文](./README.md)

## Features

- **OpenAI-compatible API**: `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, `/v1/models`, `/v1/images/generations`
- **Gemini-native API**: `/v1beta/models`, `:generateContent`, `:streamGenerateContent`, `:countTokens`
- **WebUI**: built-in Playground, image studio, account management, and runtime stats
- **Streaming**: SSE for chat completions and Gemini `streamGenerateContent`
- **Multimodal input**: image input plus local inline files when model capabilities allow them
- **Tools**: Google Search, Code Execution, function declarations, and tool-call mapping
- **Thinking**: supports `off`, `low`, `medium`, and `high` reasoning controls
- **Structured output**: `response_format` / `json_schema` support with model-capability validation
- **Image generation and editing**: OpenAI-compatible image generation, reference images, server-side image persistence, and image-session history
- **Account management**: browser login, credential import/export, account health checks, and Free/Pro/Ultra tier labels
- **Account rotation**: `round_robin`, `lru`, `least_rl`, and `exhaustion` modes with account/model stats
- **Experimental pure HTTP mode**: limited plain-text requests without the browser; not full compatibility mode

## Quick Start

### Requirements

- Python 3.11+
- A system environment that can run Camoufox/Playwright Firefox
- At least one Google account that can access AI Studio

### Run From Source

```bash
git clone https://github.com/bamboo-pan/aistudio-api.git
cd aistudio-api

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux / macOS
# source .venv/bin/activate

pip install -r requirements.txt
python main.py server --port 8080 --camoufox-port 9222
```

Open http://localhost:8080, go to `Account Management`, add an account, and complete browser login. Saved account credentials live under `data/accounts/`, and subsequent requests use the active account.

### Install Console Scripts

```bash
pip install -e .

aistudio-api server --port 8080 --camoufox-port 9222
# Or start the server entrypoint directly
aistudio-api-server --port 8080 --camoufox-port 9222
```

The local root wrapper `python main.py ...` and the installed `aistudio-api ...` command expose the same subcommands: `server`, `client`, and `snapshot`.

## WebUI

The service root redirects to `/static/index.html`.

- `#chat`: model Playground with capability-aware controls, attachments, streaming, Search, Thinking, and structured-output tests
- `#images`: image generation/editing studio with size/count controls, reference images, material history, and saved sessions
- `#accounts`: account management with login, switching, health checks, tier labels, rotation modes, runtime stats, and credential import/export

## Authentication And Accounts

The recommended path is the WebUI. The service opens a headed login browser, then saves Playwright storage state when login completes.

Useful account APIs:

```bash
# List accounts
curl http://localhost:8080/accounts

# Start browser login and receive session_id
curl http://localhost:8080/accounts/login/start \
  -H "Content-Type: application/json" \
  -d '{"name":"main"}'

# Poll login status
curl http://localhost:8080/accounts/login/status/login_xxxxxxxx

# Activate an account
curl -X POST http://localhost:8080/accounts/acc_xxxxxxxx/activate

# Health-check an account; may update Free/Pro/Ultra tier
curl -X POST http://localhost:8080/accounts/acc_xxxxxxxx/test
```

### Credential Import / Export

```bash
# Export all accounts
curl http://localhost:8080/accounts/export > credentials.backup.json

# Export one account
curl http://localhost:8080/accounts/acc_xxxxxxxx/export > one-account.backup.json

# Import a project backup package or one-account storage state
curl http://localhost:8080/accounts/import \
  -H "Content-Type: application/json" \
  --data-binary @credentials.backup.json
```

Backup files contain cookies and tokens that can grant account access. Store them only in trusted locations, do not commit them to Git, and do not share them.

## API Examples

### OpenAI Chat Completions

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [{"role": "user", "content": "Hello, summarize what you can do."}],
    "stream": true,
    "thinking": "low",
    "grounding": true
  }'
```

### Image And File Input

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}},
        {"type": "file", "file": {"file_data": "data:text/plain;base64,SGVsbG8=", "filename": "note.txt", "mime_type": "text/plain"}},
        {"type": "text", "text": "Summarize the image and file."}
      ]
    }]
  }'
```

File input is validated through `capabilities.file_input` and `capabilities.file_input_mime_types` from `/v1/models`. When chat completions targets an image-generation model, the shortcut supports text prompts only and rejects attachments.

### Responses API

```bash
curl http://localhost:8080/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "instructions": "Return JSON only",
    "input": "Give a service health summary",
    "text": {"format": {"type": "json_schema", "name": "Health", "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}}}
  }'
```

`/v1/responses` and `/v1/messages` do not currently support their own streaming mode. Use `/v1/chat/completions` when streaming is required.

### Messages API

```bash
curl http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "system": "Keep answers concise",
    "messages": [{"role": "user", "content": "Write a one-sentence project intro."}],
    "max_tokens": 512
  }'
```

### OpenAI-Compatible Image Generation

```bash
curl http://localhost:8080/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "Draw a neon city in the rain",
    "n": 2,
    "size": "1024x1024",
    "response_format": "url"
  }'
```

The response includes `url`, `b64_json`, `path`, `delete_url`, `mime_type`, and `size_bytes`. Generated images are persisted on the server. Delete them from the WebUI or call:

```bash
curl -X DELETE http://localhost:8080/generated-images/20260515/example.png
```

Image editing uses the `images` field. Each item must be a data URI, an HTTP(S) URL, or `{ "url": "..." }`:

```bash
curl http://localhost:8080/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "Keep the composition and turn it into watercolor",
    "images": ["data:image/png;base64,iVBOR..."],
    "size": "1024x1024",
    "response_format": "url"
  }'
```

### Gemini-Native API

```bash
# Generate content
curl http://localhost:8080/v1beta/models/gemini-3-flash-preview:generateContent \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"role": "user", "parts": [{"text": "What is the latest weather in Shanghai?"}]}],
    "tools": [{"googleSearchRetrieval": {}}]
  }'

# Stream content
curl http://localhost:8080/v1beta/models/gemini-3-flash-preview:streamGenerateContent \
  -H "Content-Type: application/json" \
  -d '{"contents": [{"role": "user", "parts": [{"text": "Write a short poem"}]}]}'

# Estimate tokens
curl http://localhost:8080/v1beta/models/gemini-3-flash-preview:countTokens \
  -H "Content-Type: application/json" \
  -d '{"contents": [{"role": "user", "parts": [{"text": "Hello"}]}]}'
```

`embedContent`, `batchEmbedContents`, `cachedContent`, and remote `fileData.fileUri` are outside the current browser replay implementation and return clear 501 or 400 errors.

### Python OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="unused")

stream = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)

for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

### CLI Client

```bash
# Quick chat
python main.py client "What's the weather today?" --search

# With an image
python main.py client "What is this?" -a photo.jpg

# Image generation
python main.py client "Draw a cat" --image --save cat.png

# Installed alternatives
# aistudio-api client "Hello" --search
# aistudio-api-client "Hello" --search
```

## Runtime Status And Rotation

```bash
# Health check
curl http://localhost:8080/health

# Per-model stats
curl http://localhost:8080/stats

# Rotation status and account stats
curl http://localhost:8080/rotation

# Set rotation mode
curl http://localhost:8080/rotation/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"exhaustion","cooldown_seconds":60}'

# Force switch to the next available account
curl -X POST http://localhost:8080/rotation/next
```

Rotation modes:

| Mode | Behavior |
|------|----------|
| `round_robin` | Cycle through the account pool |
| `lru` | Prefer the least recently used account |
| `least_rl` | Prefer the account with the fewest rate-limit events |
| `exhaustion` | Keep using the current healthy account until it becomes rate-limited, isolated, expired, missing auth, or unsuitable for the selected model |

Image models prefer healthy accounts marked Pro/Ultra. If no premium account is available, the service falls back to an available account and logs a warning.

## Supported Models

`/v1/models` returns capability metadata for every registered model. Current registered models:

| Model ID | Type | Search | Tool calls | Thinking | Structured output | File input | Image sizes |
|----------|------|--------|------------|----------|-------------------|------------|-------------|
| `gemma-4-31b-it` | Text | Default available | Yes | Yes | Yes | No | - |
| `gemma-4-26b-a4b-it` | Text | Default available | Yes | Yes | Yes | No | - |
| `gemini-3-flash-preview` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |
| `gemini-3.1-pro-preview` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |
| `gemini-3.1-flash-lite` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |
| `gemini-3.1-flash-image-preview` | Image generation/editing | No | No | No | No | No | `512x512`, `1024x1024`, `1024x1792`, `1792x1024` |
| `gemini-3-pro-image-preview` | Image generation/editing | No | No | No | No | No | Flash sizes + `2048x2048`, `1536x2816`, `2816x1536`, `4096x4096`, `2304x4096`, `4096x2304` |
| `gemini-3.1-flash-live-preview` | Text/multimodal | Yes | No | Yes | Yes | Yes | - |
| `gemini-3.1-flash-tts-preview` | TTS text | No | No | No | No | No | - |
| `gemini-pro-latest` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |
| `gemini-flash-latest` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |
| `gemini-flash-lite-latest` | Text/multimodal | Yes | Yes | Yes | Yes | Yes | - |

Text models generally allow inline `image/*`, `application/pdf`, `text/plain`, `text/markdown`, `text/csv`, `application/json`, `audio/*`, and `video/*`, but always prefer the exact `/v1/models` response. Unknown models on non-strict paths are inferred as generic text or image models by name; model detail lookup requires a registered model.

## Configuration

Use environment variables or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `AISTUDIO_PORT` | `8080` | API server port |
| `AISTUDIO_CAMOUFOX_PORT` | `9222` | Gateway Camoufox debug port |
| `AISTUDIO_LOGIN_CAMOUFOX_PORT` | `9223` | Headed browser port used for account login |
| `AISTUDIO_DEFAULT_TEXT_MODEL` | `gemma-4-31b-it` | Default text model |
| `AISTUDIO_DEFAULT_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Default image model |
| `AISTUDIO_AUTH_FILE` | auto-discovered | Legacy single storage-state file; the account pool under `data/accounts` takes priority for normal runs |
| `AISTUDIO_ACCOUNTS_DIR` | `./data/accounts` | Account registry and per-account `auth.json` directory |
| `AISTUDIO_TMP_DIR` | `/tmp` | Temporary image/file conversion directory |
| `AISTUDIO_CAMOUFOX_HEADLESS` | `1` | Whether the gateway browser runs headless; login browser is always headed |
| `AISTUDIO_CAMOUFOX_PYTHON` | empty | Python executable used to launch Camoufox |
| `AISTUDIO_PROXY_SERVER` | empty | Camoufox browser proxy, for example `http://<WSL gateway IP>:7890` when WSL must use a Windows proxy |
| `AISTUDIO_TIMEOUT_REPLAY` | `120` | Non-streaming replay timeout in seconds; increase it for slow large-image generation |
| `AISTUDIO_TIMEOUT_STREAM` | `120` | Streaming request timeout in seconds |
| `AISTUDIO_TIMEOUT_CAPTURE` | `30` | Request-capture timeout in seconds |
| `AISTUDIO_SNAPSHOT_CACHE_TTL` | `3600` | BotGuard snapshot cache TTL in seconds |
| `AISTUDIO_SNAPSHOT_CACHE_MAX` | `100` | Maximum snapshot cache entries |
| `AISTUDIO_DUMP_RAW_RESPONSE` | `0` | Dump raw request/response exchanges to disk |
| `AISTUDIO_DUMP_RAW_RESPONSE_DIR` | `/tmp` | Raw exchange dump directory |
| `AISTUDIO_GENERATED_IMAGES_DIR` | `./data/generated-images` | Directory for persisted generated images |
| `AISTUDIO_IMAGE_SESSIONS_DIR` | `./data/image-sessions` | Image-session history directory |
| `AISTUDIO_GENERATED_IMAGES_ROUTE` | `/generated-images` | Static serving and deletion route prefix for generated images |
| `AISTUDIO_ACCOUNT_ROTATION_MODE` | `round_robin` | Default account rotation mode |
| `AISTUDIO_ACCOUNT_COOLDOWN_SECONDS` | `60` | Cooldown after rate limit |
| `AISTUDIO_ACCOUNT_MAX_RETRIES` | `3` | Account-related max retry setting |
| `AISTUDIO_MAX_CONCURRENCY` | `3` | Server-side concurrency semaphore size |
| `AISTUDIO_USE_PURE_HTTP` | `0` | Enable experimental pure HTTP mode |

> `AISTUDIO_USE_PURE_HTTP=1` is still experimental. It only attempts single-turn, non-streaming plain-text requests today. Streaming, images, tools, image input, thinking, system instructions, multi-turn conversations, safety overrides, structured output, and missing BotGuard snapshot support return clear `501` unsupported errors. Use the default browser mode for production or full compatibility.

## Architecture

```text
Client (OpenAI SDK / Gemini SDK / curl / WebUI)
    |
    v
FastAPI app
    |-- OpenAI-compatible routes: /v1/chat/completions, /v1/responses, /v1/messages, /v1/images/generations
    |-- Gemini-native routes: /v1beta/models, :generateContent, :streamGenerateContent, :countTokens
    |-- Runtime routes: /accounts, /rotation, /stats, /image-sessions, /generated-images
    v
Application service layer
    |-- request normalization, model-capability validation, structured output, tools/search/thinking config
    |-- account selection, rate-limit retry, image persistence, stats recording
    v
AI Studio gateway
    |-- captures an AI Studio request template
    |-- generates or reuses a BotGuard snapshot
    |-- rewrites the gRPC body and parses the response
    v
Camoufox browser session
    |
    v
Google AI Studio
```

### How BotGuard Works

Google AI Studio requests require a BotGuard snapshot, which proves the request came from a real browser environment. This project locates the frontend snapshot function at runtime, uses feature matching and caching to generate snapshots, then injects the normalized request body through the browser. Google bundle function names may change, but the feature pattern is more stable.

## Development

```bash
# Run all unit tests
python -m pytest tests/

# Run common focused tests
python -m pytest tests/unit/test_model_capabilities.py tests/unit/test_static_frontend_capabilities.py

# Extract snapshot for debugging
python main.py snapshot "test prompt"
```

Project code lives in `src/aistudio_api/`, the static WebUI lives in `src/aistudio_api/static/`, and runtime data defaults to `data/`.

## Acknowledgements

- https://github.com/LuanRT/BgUtils
- https://github.com/iBUHub/AIStudioToAPI
- https://linux.do

## License

MIT

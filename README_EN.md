# AI Studio API

Self-hosted OpenAI-compatible API proxy for Google AI Studio. No API key needed — just a Google account.

[中文](./README.md)

## Features

- **OpenAI-compatible** — `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, `/v1/models`, `/v1/images/generations`
- **Gemini-native API** — `/v1beta/models`, `generateContent`, `streamGenerateContent`, `countTokens`, with clear unsupported errors for embeddings, `cachedContent`, and `fileData`
- **Streaming** — SSE streaming for both API formats
- **Multi-turn** — proper user/model alternating conversation history
- **Image input** — base64 inline or HTTP URL, single or multiple images
- **Google Search** — real-time web search via `googleSearchRetrieval`
- **Thinking** — returns model thinking process (`thinking` field)
- **Image generation** — via Gemini image models
- **Anti-detection** — Camoufox (anti-fingerprint Firefox) to avoid bot detection
- **BotGuard** — auto-detects snapshot function via runtime feature matching (survives bundle updates)
- **Multi-account** — round-robin / LRU / least-rate-limited rotation
- **Credential import/export** — WebUI and backend APIs for project backup packages and single-account storage state

## Quick Start

```bash
# Clone
git clone https://github.com/yourname/aistudio-api.git
cd aistudio-api

# Install dependencies
pip install -r requirements.txt

# Login to Google (opens browser, saves cookies)
python3 main.py login

# Start server
python3 main.py server --port 8080 --camoufox-port 9222
```

### Docker

```bash
docker build -t aistudio-api .
docker run -p 8080:8080 -v ./data:/app/data aistudio-api
```

## Usage

### OpenAI-compatible API

```bash
# Chat (streaming)
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-31b-it",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'

# Image understanding
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}},
        {"type": "text", "text": "What is this?"}
      ]
    }]
  }'

# List models
curl http://localhost:8080/v1/models

# Responses API with response_format/json_schema
curl http://localhost:8080/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "input": "Return JSON",
    "text": {"format": {"type": "json_schema", "name": "Answer", "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}}}
  }'

# Image generation (OpenAI-compatible)
curl http://localhost:8080/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "Draw a neon city in the rain",
    "n": 2,
    "size": "1024x1024",
    "response_format": "b64_json"
  }'
```

### Gemini-native API

```bash
# With Google Search
curl http://localhost:8080/v1beta/models/gemini-3-flash-preview:generateContent \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"role": "user", "parts": [{"text": "What is the latest news?"}]}],
    "tools": [{"googleSearchRetrieval": {}}]
  }'

# Estimate tokens
curl http://localhost:8080/v1beta/models/gemini-3-flash-preview:countTokens \
  -H "Content-Type: application/json" \
  -d '{"contents": [{"role": "user", "parts": [{"text": "Hello"}]}]}'
```

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="unused")

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

### CLI Client

```bash
# Quick chat
python3 main.py client "What's the weather today?" --search

# With image
python3 main.py client "What is this?" -a photo.jpg

# Image generation
python3 main.py client "Draw a cat" --image --save cat.png
```

## Supported Models

| Model | ID | Default Google Search | Notes |
|-------|----|----------------------|-------|
| Gemma 4 31B | `gemma-4-31b-it` | ✅ | Default text model |
| Gemma 4 26B A4B | `gemma-4-26b-a4b-it` | ✅ | MoE, 4B active |
| Gemini 3 Flash | `gemini-3-flash-preview` | ❌ | Fast |
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | ❌ | |
| Gemini 3.1 Flash Lite | `gemini-3.1-flash-lite` | ❌ | |
| Gemini 3.1 Flash Image | `gemini-3.1-flash-image-preview` | ❌ | Default image model, Pro/Ultra |
| Gemini 3 Pro Image | `gemini-3-pro-image-preview` | ❌ | |
| Gemini 3.1 Flash Live | `gemini-3.1-flash-live-preview` | ❌ | Real-time conversation |
| Gemini 3.1 Flash TTS | `gemini-3.1-flash-tts-preview` | ❌ | Text-to-speech |
| Gemini Pro Latest | `gemini-pro-latest` | ❌ | Alias |
| Gemini Flash Latest | `gemini-flash-latest` | ❌ | Alias |
| Gemini Flash Lite Latest | `gemini-flash-lite-latest` | ❌ | Alias |

`/v1/models` returns capability metadata for every registered model. OpenAI-compatible routes return standard `{ "error": ... }` envelopes where practical. `/v1/chat/completions`, `/v1/responses`, and `/v1/messages` support `response_format` / `json_schema` structured output when the selected model supports it, plus tool-call mapping. `/v1/images/generations` supports `b64_json` and also accepts client requests for `response_format=url` by returning a `/generated-images/...` server file URL plus base64 fallback. Generated images are persisted in the backend runtime directory and are not auto-pruned; delete them from the WebUI or with DELETE `/generated-images/{path}`. It validates `size` through model metadata and returns 400 for unsupported model/size combinations. When `/v1/chat/completions` is called with an image model, the server uses image-generation semantics and ignores incompatible `stream=true` requests.

## Configuration

Environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `AISTUDIO_PORT` | `8080` | API server port |
| `AISTUDIO_CAMOUFOX_PORT` | `9222` | Camoufox debug port |
| `AISTUDIO_DEFAULT_TEXT_MODEL` | `gemma-4-31b-it` | Default chat model |
| `AISTUDIO_DEFAULT_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Default image model |
| `AISTUDIO_CAMOUFOX_HEADLESS` | `1` | Run browser headless |
| `AISTUDIO_PROXY_SERVER` | empty | Camoufox browser proxy, for example `http://<WSL gateway IP>:7890` when WSL must use a Windows proxy |
| `AISTUDIO_TIMEOUT_REPLAY` | `120` | Request timeout (seconds) |
| `AISTUDIO_TIMEOUT_STREAM` | `120` | Stream timeout (seconds) |
| `AISTUDIO_SNAPSHOT_CACHE_TTL` | `3600` | BotGuard snapshot cache TTL |
| `AISTUDIO_ACCOUNT_ROTATION_MODE` | `round_robin` | `round_robin`, `lru`, or `least_rl` |
| `AISTUDIO_ACCOUNT_COOLDOWN_SECONDS` | `60` | Cooldown after rate limit |
| `AISTUDIO_USE_PURE_HTTP` | `0` | Pure HTTP mode (no browser) |
| `AISTUDIO_DUMP_RAW_RESPONSE` | `0` | Dump raw responses to disk |
| `AISTUDIO_GENERATED_IMAGES_DIR` | `./data/generated-images` | Directory for persisted generated images |
| `AISTUDIO_GENERATED_IMAGES_ROUTE` | `/generated-images` | Static serving and deletion route prefix for generated images |

> `AISTUDIO_USE_PURE_HTTP=1` is still experimental. It only attempts single-turn, non-streaming plain-text requests today. Streaming, images, tools, image input, thinking, system instructions, multi-turn conversations, safety overrides, structured output, and missing BotGuard snapshot support return clear `501` unsupported errors. Use the default browser mode for production or full compatibility.

## Architecture

```
Client (OpenAI SDK / curl)
    │
    ▼
┌─────────────────────┐
│   FastAPI Server     │  ← OpenAI + Gemini API routes
│   /v1/chat/...       │
│   /v1beta/...        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   Wire Codec         │  ← Converts API format → AI Studio gRPC body
│   + BotGuard         │     Auto-detects snapshot function via features
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   Camoufox Browser   │  ← Anti-fingerprint Firefox, injects cookies
│   (headless)         │     Sends request via XHR hook
└─────────┬───────────┘
          │
          ▼
    Google AI Studio
```

**How it works:**
1. API request comes in, gets normalized into AI Studio's wire format
2. A BotGuard snapshot is generated (auto-detected function, cached)
3. The full gRPC body is constructed and injected into the browser via XHR hook
4. The browser sends the request to Google (with valid cookies + BotGuard)
5. Response is parsed and returned in the requested API format

## Multi-account

Manage multiple Google accounts for higher throughput:

```bash
# Add accounts
python3 main.py account add --email user1@gmail.com
python3 main.py account add --email user2@gmail.com

# List
python3 main.py account list

# Auto-rotate on startup
AISTUDIO_ACCOUNT_ROTATION_MODE=round_robin python3 main.py server
```

Rotation modes:
- `round_robin` — cycle through accounts
- `lru` — least recently used
- `least_rl` — least rate-limited

### Credential Import / Export

The account-management WebUI includes credential import and export controls. Exported JSON is a project backup package containing account metadata, `auth.json` / Playwright storage state, and a sensitive-data warning. Backend APIs are also available:

```bash
# Export all accounts
curl http://localhost:8080/accounts/export > credentials.backup.json

# Export one account
curl http://localhost:8080/accounts/acc_xxxxxxxx/export > one-account.backup.json

# Import a project backup package or single-account auth.json / storage state
curl http://localhost:8080/accounts/import \
  -H "Content-Type: application/json" \
  --data-binary @credentials.backup.json
```

Backup files contain cookies and tokens that may grant account access. Store them only in trusted locations and do not share them.

## Development

```bash
# Run tests
python3 -m pytest tests/

# Extract snapshot (debug)
python3 main.py snapshot "test prompt"
```

## How BotGuard Works

Google requires a BotGuard "snapshot" with every request — a cryptographic proof that the request came from a real browser. This project:

1. Hooks the frontend's snapshot function at runtime
2. Auto-detects it via feature matching (`.snapshot({` + `content` + `yield`) — survives bundle updates
3. Generates valid snapshots for each request

The snapshot function name changes with every Google bundle update (Mv → Ov → Sv → ...), but the feature pattern stays the same.

## License

MIT

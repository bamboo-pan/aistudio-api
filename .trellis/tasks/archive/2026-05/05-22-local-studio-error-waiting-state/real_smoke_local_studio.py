import json
from pathlib import Path

import httpx

server = "http://127.0.0.1:18080"
key_path = Path("/mnt/c/Users/bamboo/Documents/github/key.txt")
raw_lines = [line.strip() for line in key_path.read_text(encoding="utf-8").splitlines() if line.strip()]
base_url = next((line for line in raw_lines if line.startswith(("http://", "https://"))), "https://api.openai.com/v1")
token = next((line for line in raw_lines if not line.startswith(("http://", "https://"))), "")
if not token:
    raise SystemExit("missing token in key file")
settings = {"base_url": base_url, "api_key": token, "timeout": 180, "interface_mode": "responses"}

with httpx.Client(timeout=240) as client:
    health = client.get(f"{server}/api/local-studio/health")
    health.raise_for_status()

    models = client.post(f"{server}/api/local-studio/models", json=settings)
    models.raise_for_status()
    model_ids = [item.get("id") for item in models.json().get("data", []) if item.get("id")]
    text_model = next((mid for mid in model_ids if str(mid).startswith("gpt-5")), model_ids[0] if model_ids else "")
    if not text_model:
        raise SystemExit("no local studio model returned")

    invalid = client.post(
        f"{server}/api/local-studio/chat",
        json={
            **settings,
            "model": text_model,
            "message": "invalid size smoke",
            "options": {"stream": False, "image_tool_enabled": True, "size": "3840x2160"},
        },
    )
    if invalid.status_code != 400:
        raise SystemExit(f"invalid size expected 400, got {invalid.status_code}: {invalid.text[:200]}")

    text = client.post(
        f"{server}/api/local-studio/chat",
        json={
            **settings,
            "model": text_model,
            "message": "Say OK in one short sentence for a smoke test.",
            "options": {"stream": True, "reasoning_effort": "off", "image_tool_enabled": False},
        },
    )
    text.raise_for_status()
    completed = []
    for line in text.text.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if event.get("type") == "local_studio.completed":
                completed.append(event)
    if not completed:
        raise SystemExit("missing streaming completed event")
    text_message = completed[-1]["conversation"]["messages"][-1]
    if not (text_message.get("content") or text_message.get("error")):
        raise SystemExit("stream text smoke had no assistant output")

    image = client.post(
        f"{server}/api/local-studio/chat",
        json={
            **settings,
            "model": text_model,
            "message": "Generate a simple tiny illustration of a red circle on a white background.",
            "options": {
                "stream": True,
                "reasoning_effort": "off",
                "image_tool_enabled": True,
                "size": "1536x864",
                "quality": "auto",
                "background": "auto",
                "output_format": "png",
                "output_compression": 100,
            },
        },
    )
    image.raise_for_status()
    image_completed = []
    for line in image.text.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            if event.get("type") == "local_studio.completed":
                image_completed.append(event)
    if not image_completed:
        raise SystemExit("missing image completed event")
    image_message = image_completed[-1]["conversation"]["messages"][-1]
    images = image_message.get("images") or []
    if len(images) != 1:
        error = str(image_message.get("error") or "")[:200]
        raise SystemExit(f"expected exactly one generated image, got {len(images)}; error={error}")
    asset = client.get(f"{server}{images[0]['url']}")
    asset.raise_for_status()
    if len(asset.content) < 1000:
        raise SystemExit(f"asset too small: {len(asset.content)}")

    print(json.dumps({
        "health": health.json().get("ok"),
        "models": len(model_ids),
        "text_model": text_model,
        "invalid_size_status": invalid.status_code,
        "text_content_len": len(text_message.get("content") or ""),
        "text_error": bool(text_message.get("error")),
        "image_count": len(images),
        "image_error": bool(image_message.get("error")),
        "asset_bytes": len(asset.content),
    }, ensure_ascii=False))

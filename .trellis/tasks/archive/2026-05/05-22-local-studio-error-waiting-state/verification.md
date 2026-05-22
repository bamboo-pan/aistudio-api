# Verification

## Unit and static checks

- `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit/test_local_studio.py -q` -> 21 passed.
- `C:/Users/bamboo/Desktop/aistudio-api_u1/.venv/Scripts/python.exe -m pytest tests/unit -q` -> 307 passed.
- `node --check src/aistudio_api/static/app.js` -> passed.
- WSL temp checkout: `.venv/bin/python -m pytest tests/unit/test_local_studio.py -q` -> 21 passed.

## Real WSL API smoke

Server ran from `/home/bamboo/aistudio-api-realtest-local-studio` with real accounts from `/home/bamboo/aistudio-api/data/accounts`, isolated runtime dirs, and port `18080`.

Smoke result from `real_smoke_local_studio.py`:

```json
{"health": true, "models": 12, "text_model": "gpt-5.2", "invalid_size_status": 400, "text_content_len": 21, "text_error": false, "image_count": 1, "image_error": false, "asset_bytes": 849243}
```

This verifies model loading, invalid `3840x2160` rejection, streamed text, image-tool generation, one persisted generated image, and readable local asset bytes.

## Real browser UI smoke

Opened `http://127.0.0.1:18080/static/index.html#studio` in the integrated browser.

- Local Studio waiting UI appeared with text `正在等待模型返回` while a streamed request was running.
- A successful Local Studio browser send with local `/v1` and model `gemini-flash-lite-latest` returned assistant content `OK`.
- Restored the real generated-image conversation and verified the DOM rendered exactly one assistant image with natural dimensions `1536x864`.

## Spec gate

Updated `.trellis/spec/backend/quality-guidelines.md` because this task changed Local Studio stream/image contracts. The spec now records partial-image persistence on stream interruption, final-image preference on successful streams, equivalent-image deduplication before saving, and required unit coverage for those cases.

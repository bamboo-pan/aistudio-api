# Verification

## Automated Checks

- `node --check src/aistudio_api/static/app.js` passed.
- `python -m pytest tests/unit/test_local_studio.py tests/unit/test_static_frontend_capabilities.py -q` passed: 31 tests.
- `python -m pytest -q` passed: 302 tests.

## WSL Real API Smoke

- Real service copy: `/home/bamboo/aistudio-api-realtest-inline-images`.
- Real service URL: `http://127.0.0.1:18182`.
- Runtime settings used real account storage under `/home/bamboo/aistudio-api/data/accounts` and the Local Studio key from `C:\Users\bamboo\Documents\github\key.txt` without printing the token.
- Local Studio Responses stream text request with `image_tool_enabled=true` completed through upstream `/v1/responses` and returned no images.
- Local Studio Responses stream image-tool request completed through upstream `/v1/responses`, saved generated images under `/api/local-studio/assets/...`, and the asset GET returned `200`.
- Request-log sampling for the new Local Studio groups showed upstream URLs containing `/v1/responses` and no `/images/generations`.

## Browser UI Smoke

- Opened `http://127.0.0.1:18182/static/index.html#studio`.
- Existing real Local Studio generated-image conversation rendered two image elements with non-zero natural dimensions: `1536x864` and `1536x864`.
- Frontend send behavior was checked with a delayed `fetch` fixture in the page: after `sendLocalStudioMessage()` was called and before the mocked response resolved, the transcript had one visible user message, `localStudioBusy=true`, and the draft was cleared. After completion, the server conversation reconciled to user + assistant messages.

## Image Tool Only Contract

- Unit regressions now assert Local Studio Responses image-tool HTTP errors, transport errors, and no-candidate stream completions do not call `/images/generations`.
- `.trellis/spec/backend/quality-guidelines.md` was updated so the Local Studio contract explicitly says Responses image tool must not fall back to `/images/generations`.
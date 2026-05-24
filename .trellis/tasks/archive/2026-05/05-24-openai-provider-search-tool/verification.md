# Verification

## Local Tests

* `python -m pytest tests/unit/test_local_studio.py -q` — 37 passed.
* `python -m pytest tests/unit/test_local_studio.py tests/unit/test_openai_compatibility.py -q` — 70 passed.
* `python -m pytest tests/unit -q` — 351 passed.
* `git diff --check` — passed.

## Real WSL API/UI Smoke

Command:

```bash
wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/bamboo/Desktop/aistudio-api_u1/.trellis/tasks/05-24-openai-provider-search-tool/real_smoke.sh
```

Result:

* Passed.
* Run root: `/home/bamboo/aistudio-api-openai-search-20260524-181345`.
* Port: `18080`.
* Selected OpenAI-compatible model: `gpt-5.5`.
* API smoke verified OpenAI-compatible Responses search upstream tools use `web_search` and do not send `web_search_preview`.
* Browser UI smoke opened `#studio`, configured an OpenAI-compatible provider from runtime credentials, sent a streamed Local Studio search message, captured a screenshot, and saw no browser console errors.
* Server log did not contain `Unsupported tool type: web_search_preview`, `httpx.ResponseNotRead`, `ExceptionGroup`, or `Exception in ASGI application`.

Artifacts remain in the WSL temp directory and are not committed because they can include request logs or generated runtime outputs.
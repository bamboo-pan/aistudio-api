# Verification

Date: 2026-05-17

## Windows Workspace

* VS Code diagnostics for changed Python files — no errors.
* `python -m pytest tests/unit/test_account_health_and_selection.py tests/unit/test_model_capabilities.py` — 40 passed.
* `python -m pytest tests/unit/test_openai_compatibility.py tests/unit/test_gemini_native_routes.py tests/unit/test_streaming_stability.py tests/unit/test_account_auth_activation.py` — 24 passed.
* `python -m pytest tests/unit` — 214 passed.

## WSL Real-Environment Temp Copy

* Script: `python3 /mnt/c/Users/bamboo/Desktop/aistudio-api_u2/.trellis/tasks/05-17-new-account-permission/verify_wsl_new_account_permission.py`.
* Temp directory: `/home/bamboo/aistudio-api-u2-new-account-permission-pvswtqna`.
* Real credential directory: `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`; credential contents were not printed.
* Camoufox fetch: already up to date, `camoufox_fetch_ok True`.
* Focused WSL tests: `tests/unit/test_account_health_and_selection.py tests/unit/test_model_capabilities.py -q` — 40 passed.
* Real account smoke:
  * Account pool contained 2 accounts: 1 Pro/Ultra and 1 non-premium.
  * `gemini-3.1-pro-preview` and `models/gemini-3.1-pro-preview` both preferred premium accounts.
  * Initial active account was non-premium.
  * `/v1/chat/completions` for `gemini-3.1-pro-preview` returned status 200 with 1 choice.
  * After the request, the active account was Pro/Ultra.
  * Rotator reason: `premium-preferred model selected a Pro/Ultra account`.
  * Overall `live_pro_route_ok True`, `live_secrets_printed False`.
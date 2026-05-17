# Verification

Date: 2026-05-17

## Windows Workspace

- `python -m pytest tests/unit/test_login_service.py tests/unit/test_account_auth_activation.py tests/unit/test_account_credentials.py tests/unit/test_account_health_and_selection.py` — 31 passed.
- `python -m pytest tests/unit` — 212 passed.
- VS Code diagnostics for changed Python files — no errors.

## WSL Real-Environment Temp Copy

- Script: `python3 /mnt/c/Users/bamboo/Desktop/aistudio-api_u2/.trellis/tasks/05-17-fix-failed-login-account-record/verify_wsl_login.py`.
- Temp directory: `/home/bamboo/aistudio-api-u2-login-verify-qk18asr0`.
- Real credential directory: `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`; credential contents were not printed.
- Camoufox fetch: already up to date, `camoufox_fetch_ok True`.
- Focused login/account tests in WSL temp copy — 16 passed.
- Real account smoke:
  - Account candidate 1: storage shape valid, no email detected, browser warmup passed, `/v1/chat/completions` returned upstream 401 permission error.
  - Account candidate 2: storage shape valid, no email detected, browser warmup passed, `/v1/chat/completions` returned 200 with 1 choice.
  - Overall `live_chat_ok True`, `live_secrets_printed False`.

## Notes

- The first real-account candidate demonstrates the existing bad-record symptom: a stored account can have valid-looking Google cookies but fail upstream calls.
- The implemented fix prevents future browser-login sessions without verified Google account identity from creating that kind of stored account.

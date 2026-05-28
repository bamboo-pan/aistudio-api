# Real WSL Warmup and Config Smoke Result

Run root: `/home/bamboo/aistudio-api-warmup-20260528-194953`
Model: `gemini-3-flash-preview`
Real account count: 2

## Warmup Timing

| Scenario | First SSE event | Total stream |
| --- | ---: | ---: |
| warmup off | 44560.9 ms | 44566.3 ms |
| warmup on | 18067.6 ms | 18074.0 ms |

First-event speedup: 26493.3 ms (2.47x).
Total stream delta: 26492.3 ms (2.47x).
Warmup completions before request:
- `20:18:35 [aistudio.server] Account browser warmup completed: account=acc_<redacted>`

## Config API/UI Smoke

Config API item count: 30
Config API save/reset key: `AISTUDIO_ACCOUNT_WARMUP_LIMIT`
Config UI route: `#config`
Config UI save/reset key: `AISTUDIO_ACCOUNT_WARMUP_LIMIT`
Screenshot artifact: `/home/bamboo/aistudio-api-warmup-20260528-194953/config-ui-smoke.png`

Secrets: raw account cookies, storage state, API tokens, request logs, and screenshots are not committed.

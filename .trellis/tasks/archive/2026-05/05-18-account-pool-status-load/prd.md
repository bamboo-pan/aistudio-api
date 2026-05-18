# Clarify Account Pool Status And Load

## Goal

Make the account management page and backend logs accurately describe balanced account-pool routing. Administrators should not confuse the global active account with the account that actually serves pooled requests, and they should be able to see per-account affinity load.

## What I Already Know

- Current UI shows account status as `激活` / `待命`, based on the global active account.
- In balanced `round_robin` mode, normal requests lease an account from the pool and use that account's isolated client, so a `待命` account may still serve traffic.
- The user wants correct status display, request logs that include the bound account, account load as number of users bound to that account, bounded affinity lifetime, and UI load display.
- The desired affinity lifecycle is one hour.

## Requirements

- Replace misleading account table status semantics with pool-aware display.
- Keep global active account visible as a default/account-service marker, not as the serving state for balanced requests.
- Expose account affinity load through `/rotation` so the UI can show how many logical users/sessions are currently bound to each account.
- Expire affinity bindings after one hour so user-to-account bindings do not last indefinitely.
- When a request leases an account, log the selected account id, account tier, rotation reason, current in-flight count, and current affinity load for that account.
- Preserve existing account selection rules: premium preference, cooling/isolated exclusion, 429 retry exclusion, and balanced least-busy scoring.
- Add focused tests for affinity TTL/load accounting and frontend status text helpers.

## Acceptance Criteria

- [x] Healthy available accounts in balanced mode are shown as schedulable/available instead of standby-only.
- [x] The UI distinguishes `默认账号` from pool serving status.
- [x] Accounts with `in_flight > 0` can show active processing state.
- [x] `/rotation.accounts[*]` includes affinity load information.
- [x] Affinity bindings expire after one hour and expired bindings no longer contribute to load.
- [x] Account lease logs include the bound account and that account's load.
- [x] Unit/static tests cover the new backend and frontend behavior.

## Definition Of Done

- Relevant unit/static tests pass locally.
- For this code/API/UI/account-routing change, WSL real-environment smoke testing is attempted and results recorded.
- Task files and code changes are committed on the feature branch.

## Out Of Scope

- Changing the public `round_robin` config value.
- Building a full user/session management page.
- Persisting affinity bindings across process restarts.
- Changing API request contracts for OpenAI/Gemini clients.

## Technical Notes

- Backend specs read: `.trellis/spec/backend/index.md`, `.trellis/spec/backend/quality-guidelines.md`, `.trellis/spec/backend/logging-guidelines.md`.
- Relevant code areas: `AccountRotator`, `/rotation`, account table frontend helpers, and account routing tests.
- Validation: Windows full unit suite passed with `239 passed`.
- WSL real smoke: temporary service on port `18181` with two real Pro accounts returned `OK` for two distinct OpenAI `user` affinity keys; `/rotation` showed each account with `requests=1`, `success=1`, `in_flight=0`, `affinity_load=1`, `bound_users=1`, and `affinity_ttl_seconds=3600`; lease logs included `account=...`, `affinity_load=1`, and `affinity_ttl_seconds=3600`.
- WSL pytest note: targeted WSL pytest could not run because `/home/bamboo/aistudio-api/venv/bin/python` has no `pytest` module installed; real service smoke still ran successfully in that environment.
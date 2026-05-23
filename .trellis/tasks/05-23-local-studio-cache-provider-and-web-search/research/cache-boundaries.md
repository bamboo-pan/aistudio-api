# Cache Boundaries

## Goal

Separate the different cache concepts so implementation and UI do not mix them up.

## Cache Types in This Repo

### 1. Provider / upstream cache

This is the cache the model/provider reports back through usage fields such as:

- `cached_tokens`
- `prompt_tokens_details.cached_tokens`
- `cachedContentTokenCount`

This is what the UI should show as read cache usage.

### 2. Snapshot cache

This is the in-memory cache used for browser replay / capture behavior.

Observed files:

- [src/aistudio_api/infrastructure/cache/snapshot_cache.py](src/aistudio_api/infrastructure/cache/snapshot_cache.py)
- [src/aistudio_api/infrastructure/gateway/client.py](src/aistudio_api/infrastructure/gateway/client.py)
- [src/aistudio_api/application/account_service.py](src/aistudio_api/application/account_service.py)

This cache should stay separate from provider usage metrics.

### 3. Local Studio request cache

This is the Local Studio workbench cache implemented under `data/local-studio/cache/requests`.

Observed files:

- [src/aistudio_api/infrastructure/local_studio.py](src/aistudio_api/infrastructure/local_studio.py)
- [src/aistudio_api/api/routes_local_studio.py](src/aistudio_api/api/routes_local_studio.py)

This cache stores assistant results for equivalent Local Studio requests. Its cache key includes provider identity, base URL, token hash, interface mode, model, normalized request body, and namespace. It is a real local reuse cache, but it is not provider-native `cachedContent`.

### 4. Gemini cachedContent wire support

The codebase already has a `cached_content` field in the gateway wire layer and Gemini schema support, but browser replay mode still rejects `cachedContent` in some paths.

Observed files:

- [src/aistudio_api/infrastructure/gateway/wire_codec.py](src/aistudio_api/infrastructure/gateway/wire_codec.py)
- [src/aistudio_api/infrastructure/gateway/wire_types.py](src/aistudio_api/infrastructure/gateway/wire_types.py)
- [src/aistudio_api/api/schemas.py](src/aistudio_api/api/schemas.py)
- [src/aistudio_api/application/chat_service.py](src/aistudio_api/application/chat_service.py)

## Current UI Behavior

- Local Studio usage display already normalizes cached token fields.
- Local Studio now exposes a dedicated Local request cache control.
- The current Local Studio readout should not imply that snapshot cache and provider cache are the same thing.

## Recommended Semantics

- Use `provider cache` for upstream usage accounting.
- Use `snapshot cache` for internal replay capture caching.
- Use `Local request cache` for Local Studio result reuse.
- Only expose provider-native cache controls if the selected provider/mode can actually honor them.

## Risks If Mixed

- The user may think local request reuse or snapshot reuse is provider-native cache.
- The UI may show cache activity when the upstream did not actually cache anything.
- Tests may pass on the wrong layer if the cache boundary is not explicit.

## Decision Direction

Keep provider cache, snapshot cache, and Local Studio request cache visible and named differently in code, UI, and tests.

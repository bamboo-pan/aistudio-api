# Terminology Map

## Goal

Reduce confusion between the product shell, provider layer, and cache layers.

## Current Terms Observed

- `AI Studio Proxy` is the top-level app shell in the sidebar header.
- `Local Studio` is the current workbench route and UI section.
- `Playground` is the existing chat workbench for Google AI Studio capabilities.
- `图片生成` is the existing image workbench for Google AI Studio capabilities.
- `Google AI Studio` should be treated as an upstream provider, not the app shell.
- `snapshot cache` is an internal browser replay/cache mechanism.
- `cached_tokens` / `cachedContentTokenCount` are upstream/provider usage metrics.

## Confusing Overlaps

- `Local Studio` vs `Google AI Studio`.
- `model cache` vs `snapshot cache`.
- `provider` vs `interface_mode`.
- `Playground` vs `Local Studio` when both can do chat/search/image.

## Recommended Naming Direction

- Keep `Local Studio` as the high-level orchestration workbench.
- Use `Google AI Studio provider` for the wrapped upstream capability set.
- Use `provider profile` for a saved connection: name, base URL, token, mode, defaults.
- Use `provider cache` or `upstream cache` for `cached_tokens` / `cachedContentTokenCount`.
- Keep `snapshot cache` for browser replay capture only.

## UI Language Suggestions

- Title: `Local Studio`
- Section label: `Provider`
- Saved item label: `Provider profile`
- Usage label: `Cache read` or `Provider cache read`
- Avoid calling the snapshot cache a model cache.

## Code Paths That Reinforce the Split

- [src/aistudio_api/static/app.js](src/aistudio_api/static/app.js) currently stores only one Local Studio connection blob in `openai.localStudio.settings.v1`.
- [src/aistudio_api/api/responses.py](src/aistudio_api/api/responses.py) normalizes `cached_tokens` for usage display.
- [src/aistudio_api/infrastructure/cache/snapshot_cache.py](src/aistudio_api/infrastructure/cache/snapshot_cache.py) is a separate in-memory cache.
- [src/aistudio_api/application/account_service.py](src/aistudio_api/application/account_service.py) already uses `snapshot_cache` as a distinct concept during account switching.

## Outcome Desired

A user should be able to read the UI and know immediately which layer they are looking at:

- workbench layer: Local Studio
- upstream provider layer: Google AI Studio provider
- cache layer: provider cache vs snapshot cache

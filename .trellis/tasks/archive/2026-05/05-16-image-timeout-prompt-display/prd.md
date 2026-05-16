# Fix Image Generation Interception Timeout and Prompt Display

## Goal

Make image generation behavior less confusing and more robust: interception logs must reflect the requested model, long image generations must use a configurable timeout instead of a hard-coded value, and optimized prompt candidates should disappear once the user applies one.

## What I Already Know

* User observed image generation logs where the intercepted model appears fixed or different from the requested model.
* Current runtime config defines `AISTUDIO_TIMEOUT_REPLAY` with a default of 120 seconds.
* Image generation still passes a hard-coded `timeout=120` to replay, so changing config is not consistently honored by that path.
* Frontend prompt optimization stores candidates in `imagePromptOptions` and `applyImagePromptOption(option)` currently leaves them visible after applying one.

## Requirements

* Capture/rewrite code must use the requested model when producing the captured request body and log output, not the model found in the captured template body.
* Non-streaming image generation replay timeout must use the existing configurable replay timeout setting by default.
* The default timeout must remain documented as 120 seconds.
* After applying an optimized prompt option in the Web UI, the optimization candidate list should no longer be displayed.
* Existing image generation, prompt optimization, and style-template behavior should otherwise remain unchanged.

## Acceptance Criteria

* [ ] Image capture logging reports the requested model for a generated captured body.
* [ ] Image generation no longer hard-codes `timeout=120`; it uses `settings.timeout_replay` through the replay service default unless an explicit timeout is provided.
* [ ] README documentation states the default replay timeout and explains it applies to image generation and can be increased for large images.
* [ ] Applying a prompt optimizer option clears/hides `imagePromptOptions` in the frontend.
* [ ] Focused unit tests pass.
* [ ] WSL real-environment smoke test passes for non-documentation code changes.

## Out of Scope

* Changing AI Studio model selection UI automation.
* Adding a separate per-endpoint timeout setting unless the existing replay timeout is insufficient.
* Redesigning the prompt optimizer UI.

## Technical Notes

* Likely files: gateway capture/client/replay configuration, static frontend, README docs, focused unit tests.
* `RequestCaptureService.capture()` currently rewrites the template using `template.model or model`, which can preserve a stale model from the captured template.
* `AIStudioClient.generate_image()` currently calls replay with `timeout=120`.
* `SnapshotCache` is keyed only by prompt, which can make cached captured bodies look model-sticky if reused across models; model-aware cache keys should be considered while keeping compatibility with pure HTTP capture.
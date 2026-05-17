# fix: new account permission after activation

## Goal

Prevent newly activated free accounts from being used for models that should prefer Pro/Ultra accounts, so requests like `gemini-3.1-pro-preview` do not immediately fail with upstream `The caller does not have permission` when a suitable premium account exists.

## What I already know

* The user added and activated a new account successfully.
* After activation, a streaming `/v1/chat/completions` request for `gemini-3.1-pro-preview` captured a fresh hook template and snapshot, then AI Studio returned a `403` payload: `The caller does not have permission`.
* Account activation already clears browser/capture/snapshot state through `AIStudioClient.switch_auth` and snapshot cache clearing.
* `AccountRotator.model_prefers_premium` currently treats registered image-output models as premium-preferred, but registered text Pro models are treated as regular text models.

## Assumptions

* `gemini-3.1-pro-preview` and similar `pro` model IDs should prefer accounts whose stored tier is `pro` or `ultra`.
* If no premium account is available, the existing fallback behavior should continue: log a warning and try an otherwise healthy account instead of hard-failing before the upstream request.

## Requirements

* Text Pro model IDs must route through the same premium-account preference path used by image models.
* The active account should be switched away from a non-premium account before a premium-preferred model request when a healthy Pro/Ultra account is available.
* Existing image-model selection behavior must remain intact.
* Unknown model IDs containing a Pro model marker should also prefer Pro/Ultra accounts.

## Acceptance Criteria

* [x] `gemini-3.1-pro-preview` prefers Pro/Ultra accounts in the rotator.
* [x] `models/gemini-3.1-pro-preview` is handled the same as the bare model ID.
* [x] A free active account switches to an available Pro/Ultra account before handling a Pro text request.
* [x] Existing image premium-selection tests still pass.
* [x] Real WSL browser-backed smoke test with real account credentials passes for a chat completion path.

## Out of Scope

* Automatically upgrading or changing account tiers without the existing tier detector/manual control.
* Guaranteeing that a free-only account pool can use Pro-only upstream models.
* Changing credential import validation semantics.

## Technical Notes

* Relevant spec: `.trellis/spec/backend/quality-guidelines.md`, especially account auth cache invalidation and browser login persistence scenarios.
* Diagnosis details are recorded in `research/permission-after-new-account.md`.
* Verification details are recorded in `verification.md`.
# Permission Error After New Account Activation

## Observed Failure

The user activated a newly added account and immediately sent a streaming OpenAI-compatible request for `gemini-3.1-pro-preview`. Capture state refreshed successfully, but upstream returned `403` with `The caller does not have permission`.

## Local Code Findings

* `AccountService.activate_account` switches browser auth through the runtime client and clears snapshot cache, matching the existing auth-change cache-invalidation contract.
* `_ensure_account_for_model` only switches away from a non-premium active account when `AccountRotator.model_prefers_premium(model)` returns true.
* `model_prefers_premium` currently returns true for registered `image_output` models and unknown names containing `image`.
* `gemini-3.1-pro-preview` is a registered text model, so it is treated as usable by any healthy account even though the observed upstream behavior rejects the newly added account.

## Implementation Direction

Extend model/account selection so Pro text model IDs, including names with a `models/` prefix and unknown Pro-like model IDs, prefer Pro/Ultra accounts just like image models. Preserve the current fallback behavior when no premium account exists.
# Fix Account Switch Image Generation Stats

## Goal

Fix the real-user flow where image generation succeeds on one Pro account, then fails with upstream 401 after switching to another Pro account, and make model/account request statistics agree with the requests users actually trigger from API and Web UI.

## Requirements

* Manual account activation, forced rotation, and automatic rotation must invalidate browser-auth-dependent capture state before the next upstream request.
* Image generation after switching between stored Pro accounts must recover from stale capture/auth state when possible and avoid reusing the previous account's request template or snapshot.
* Account-level statistics must cover the same successful/error/rate-limited upstream request attempts as model-level statistics across OpenAI chat, Gemini generate content, streaming responses, prompt optimization, and image generation.
* Web UI account/stat panels must refresh after image generation and prompt optimization so users do not see stale counts after a Web workflow.
* Verification must include unit tests and WSL real-credential tests using a temporary copy under `/home/bamboo`, covering API and Web paths without printing credential contents.

## Acceptance Criteria

* [ ] Switching from account A to account B and generating an image through `/v1/images/generations` succeeds or reports a real credential/account problem after fresh capture retry, not stale state from account A.
* [ ] Account pool request totals match model totals for account-backed requests in mixed text, prompt optimization, image generation, error, and streaming cases.
* [ ] Web image generation and prompt optimization refresh model statistics and account rotation statistics after completion or failure.
* [ ] Existing unit tests pass, plus regression tests for account statistics and auth-state retry behavior.
* [ ] WSL real-account API smoke covers at least two stored Pro accounts: activate A, generate image, activate B, generate image, check `/stats` and `/rotation`.
* [ ] WSL real-account Web smoke covers the same user-visible flow through the served page, including account activation, image generation, and stat panel refresh.

## Definition of Done

* Tests added or updated for changed behavior.
* Relevant unit tests and static/frontend tests pass locally.
* WSL real environment testing passes for API and Web scenarios unless blocked by an external Google/credential condition that is clearly recorded.
* Task files under this directory are committed with the code changes.

## Technical Approach

* Centralize account statistics recording so every runtime stats record has a matching account stat when an active account exists.
* Add non-streaming auth-error retry behavior that clears client capture state once before reporting or rotating away from the active account.
* Add account-stat recording to streaming response builders, which currently update model stats only.
* Refresh Web statistics/rotation data after image prompt optimization and image generation flows.

## Decision (ADR-lite)

**Context**: The logged failure captures a fresh hook template after account activation but replays with 401, while the screenshot shows model totals and account totals diverging. Both issues cross API service, account rotation, gateway capture, and frontend refresh boundaries.

**Decision**: Fix the root coordination boundaries instead of special-casing one endpoint: clear/retry capture state at auth failures, make account-stat updates explicit and reusable, and refresh the Web panels after account-backed image workflows.

**Consequences**: The fix touches shared request handling and needs broad tests, but keeps behavior consistent across OpenAI, Gemini, image generation, and streaming routes.

## Out of Scope

* Changing account credential storage format.
* Adding new subscription-tier detection UX.
* Persisting request statistics across server restarts.

## Research References

* [`research/initial-code-scan.md`](research/initial-code-scan.md) — initial impacted modules and likely failure modes.

## Technical Notes

* Relevant spec: `.trellis/spec/backend/quality-guidelines.md` scenarios for gateway replay, browser auth cache invalidation, and premium-preferred account selection.
* User requires WSL testing with real credentials from `/home/bamboo/aistudio-api/data/accounts` using a temporary working directory under `/home/bamboo`.
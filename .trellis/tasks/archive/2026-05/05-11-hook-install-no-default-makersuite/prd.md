# Fix Hook install failed no_default_MakerSuite

## Goal

Fix the first chat request after a freshly completed account login when the gateway fails with `Hook install failed: no_default_MakerSuite`, especially in WSL runs started with `python3 main.py server --port 8080 --camoufox-port 9222`.

## What I Already Know

- The failure happens after account login succeeds and the first model conversation starts.
- The traceback reaches `BrowserSession._install_hooks_sync`, where `INSTALL_HOOKS_JS` returns `no_default_MakerSuite` because `window.default_MakerSuite` is unavailable.
- `_ensure_hook_page_sync` currently accepts any URL containing `aistudio.google.com`; a post-login page or other AI Studio route can therefore skip navigation back to the chat page.
- `_goto_aistudio_sync` waits for `default_MakerSuite` and `textarea`, but returns after a partial-ready timeout instead of forcing a clearer recovery path.
- After the first readiness fix, WSL preheat can fail with a clearer diagnostic showing the hook page at `accounts.google.com/v3/signin/identifier` after navigating to `https://aistudio.google.com/app/prompts/new_chat`; this means the gateway browser did not load a valid saved account storage state for that preheat/capture path.
- The server is already running in WSL; implementation should avoid requiring a service stop during code edits, and final notes should mention restart/reload requirements honestly.

## Requirements

- Ensure hook installation happens only after the hook page is on an AI Studio chat route that can expose `window.default_MakerSuite`.
- Recover from stale or wrong AI Studio pages by navigating to the new-chat URL before installing hooks.
- Wait long enough for both `window.default_MakerSuite` and the chat input to become available before treating the page as ready.
- Preserve existing browser/session reuse, storage-state authentication, and streaming request behavior.
- Ensure browser preheat and first capture after account login use the active/saved account auth file instead of falling back to an unauthenticated browser context.
- If navigation reaches a Google sign-in page, fail with diagnostics that point at missing/invalid auth state rather than treating it as a generic chat runtime timeout.
- Improve failure diagnostics if the chat runtime never becomes ready, so future logs show page URL/title/body readiness instead of only `no_default_MakerSuite`.

## Acceptance Criteria

- [ ] Freshly logged-in accounts can make the first chat request without `Hook install failed: no_default_MakerSuite` when cookies are valid.
- [ ] Browser preheat after adding/selecting an account does not redirect to `accounts.google.com` when a valid active account storage state exists.
- [ ] If no valid account auth state is available, the error clearly says the browser is unauthenticated or the auth file is missing/invalid.
- [ ] Existing hook page reuse still works when the page is already on the chat route and hooks are installed.
- [ ] If AI Studio never exposes the chat runtime, the raised error includes actionable readiness details.
- [ ] The closest practical automated checks pass, or any unrelated failures are recorded.

## Definition of Done

- Code changes are focused on gateway/browser session readiness.
- Tests are added or updated where practical around route/readiness decisions.
- Lint/type/syntax checks are run as available.
- Docs/spec updates are considered during finish.

## Technical Approach

Normalize the hook page before installing hooks: detect whether the current page is a valid chat page with `window.default_MakerSuite` and a textarea, navigate to `AI_STUDIO_URL` or fallback when needed, and make hook installation wait/report readiness instead of immediately failing on `no_default_MakerSuite`. Also verify the gateway session receives the active account storage state before preheat/capture so new-login requests do not open an unauthenticated AI Studio browser.

## Decision (ADR-lite)

**Context**: The hook script depends on AI Studio's chat runtime. After login, the browser can be on an AI Studio domain page that does not expose that runtime.

**Decision**: Treat AI Studio chat readiness as the contract, not merely the host name. Navigation/readiness should be handled by the session layer before hook installation.

**Consequences**: First request may spend a few extra seconds normalizing the page, but the failure mode becomes recoverable and diagnostics become clearer.

## Out of Scope

- Reworking login UI or account storage.
- Changing model request serialization or replay protocol.
- Requiring the currently running WSL server to be killed by the agent.

## Technical Notes

- Likely impacted module: `src/aistudio_api/infrastructure/gateway/session.py`.
- Related auth/selection modules may include account service/store, rotator, API app startup, and gateway client/service wiring.
- Related entry path in traceback: `capture.py -> session.capture_template -> _ensure_botguard_service_sync -> _ensure_hook_page_sync -> _install_hooks_sync`.
- New log path: browser preheat navigates to `accounts.google.com/v3/signin/identifier?...continue=https://aistudio.google.com/app/prompts/new_chat`, confirming missing/invalid auth state during the gateway session.
- No external research required; this is local browser session readiness behavior.

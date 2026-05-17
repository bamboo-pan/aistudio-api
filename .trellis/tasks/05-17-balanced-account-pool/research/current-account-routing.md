# Current Account Routing Research

## Existing Behavior

Normal chat/image/Gemini handlers call `_ensure_account_for_model()` only on the first attempt. That function switches accounts only when there is no active account, the active account is isolated, or a premium/image model requires a Pro/Ultra account and the active account is not premium. Successful ordinary requests keep using the global active account.

`_try_switch_account()` currently asks `AccountRotator.get_next_account()` for a candidate, then calls `AccountService.activate_account()`. Activation switches the global `AIStudioClient` auth and clears snapshot/capture cache. That is fine for manual switching but not safe as a request-level balancing primitive under concurrency.

`_record_request_result()` records model stats and then calls `_record_active_account()`, which reads `account_service.get_active_account()` at record time. If another request has switched the global account, stats can be attributed to the wrong account.

## Gateway Constraints

`AIStudioClient` contains its own `BrowserSession`, capture service, replay service, and streaming gateway. `BrowserSession` contains mutable auth/template state and a single-thread executor. Therefore, concurrent account isolation should be achieved by giving each selected account its own client/session rather than switching one shared client.

Pure HTTP mode does not use a browser session, but it still has capture/snapshot caches. Request-bound account attribution remains necessary even if upstream auth handling is different.

## Proposed Direction

Introduce request-bound account selection:

- Balanced mode selects an eligible account for each logical request using stats/in-flight counts and optional affinity hints.
- The selected account is passed through the handler call path and used for accounting.
- A runtime account-client pool returns an `AIStudioClient` initialized with that account's auth file. The shared default client remains available for no-account or manual operations.
- 429 and gateway errors update the selected account, then retry with a different eligible account.
- Exhaustion mode can continue using the active account path, but accounting should still be request-bound.

## User-Session Stability

The request payloads do not currently expose a stable caller identity. A practical MVP can derive an affinity hint from the request body: for chat/Gemini, use a hash of normalized message roles/content; for API calls with headers, prefer caller-provided headers if available in route layer later. The first implementation can keep affinity lightweight and bounded in memory. The scheduler must not guarantee one account per user forever; it only avoids unnecessary per-turn account flipping while preserving pool balance.

## Risks

- Multiple account clients can mean multiple browser contexts/processes and higher memory use.
- Browser warm-up latency may shift from first global request to first request per account.
- Streaming responses need to keep the selected client alive for the full stream; cleanup and accounting must happen after stream completion/cancel.
- Existing tests with fake clients should keep working when no account pool is configured.

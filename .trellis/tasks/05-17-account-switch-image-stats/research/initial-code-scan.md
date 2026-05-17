# Initial Code Scan

## Observations

* `AccountService.activate_account` calls `AIStudioClient.switch_auth`, which clears client capture state, and then clears the shared snapshot cache.
* `RequestCaptureService` caches per-model templates and `SnapshotCache` caches prompt/model captures; both are auth-context sensitive.
* Non-streaming chat, Gemini, and image handlers record model stats and some account stats, but account recording is repeated inline and not present in streaming builders.
* `handle_image_generation` records account stats only after the whole `n` image request succeeds; failures record the currently active account.
* Web `generateImage` and `optimizeImagePrompt` do not refresh `/stats` or `/rotation` after account-backed requests, so the account page can display stale data until manually refreshed or navigated.

## Likely Failure Modes

* A replay 401 immediately after activation can be caused by stale capture/auth state. The existing streaming path retries after clearing capture state, but non-streaming chat/image/Gemini paths do not.
* Account totals can diverge from model totals when streaming requests update `runtime_state.record` without updating `AccountRotator` stats.
* UI totals can appear wrong when backend data is already updated but the Web app has not reloaded `/stats` and `/rotation` after image workflows.

## Verification Notes

* Unit tests should exercise stats consistency without real credentials.
* WSL real-account tests must avoid printing auth JSON or cookie values.
* Real browser-backed tests should activate/warm up each candidate account before capture/replay.
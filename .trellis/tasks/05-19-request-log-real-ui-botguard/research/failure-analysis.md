# Failure Analysis: Real UI BotGuard Send

## Observed Failure

The WebUI Playground shows `Error 500: failed to trigger send while capturing BotGuardService` after sending a simple prompt. The request-log page still shows zero entries.

## Current Code Path

`BrowserSession._ensure_botguard_service_sync` opens/uses the AI Studio chat page, fills the `textarea`, then calls `_click_run_button_sync`. That helper currently only tries `button:has-text('Run')` and returns `False` if the button is missing or click fails.

Request logs are written later in `RequestReplayService.replay` or `StreamingGateway.stream_chat`, after a `CapturedRequest` exists. Therefore failures while capturing BotGuardService happen too early to create request-log entries.

## Coverage Gap

`tests/unit/test_request_logs.py` uses fake replay and streaming sessions. These tests prove persistence and replay-boundary logging, but they do not prove that the real AI Studio page can trigger BotGuard capture.

Previous WSL validation recorded `WSL_REQUEST_LOG_SMOKE_OK`, but the observed UI failure means it either did not drive the actual WebUI send path or did not assert assistant success plus request-log entry creation.

## Recommended Fix Shape

Keep the fix at the browser session boundary. Make the send trigger try stable UI selectors and keyboard fallback instead of relying only on visible text `Run`. Preserve existing behavior as one fallback because older AI Studio layouts may still use that label.

## Confirmed Root Cause

The real AI Studio page emits text generation to `https://alkalimakersuite-pa.clients6.google.com/$rpc/google.internal.alkali.applications.makersuite.v1.MakerSuiteService/GenerateContent`. The previous capture filter only accepted `GenerateContent` requests on `aistudio.google.com`-shaped URLs, so the real request was sent but ignored, leading to template capture timeout.

The real composer also marks the Run button with `aria-disabled="true"` until Angular sees the prompt input. Filling the textarea must dispatch input/change events, and send triggering must skip disabled controls.

## Required Validation

* Unit: fake-page coverage for current and fallback send button selectors plus keyboard fallback.
* Unit: fake-page coverage for the current `alkalimakersuite-pa.clients6.google.com/.../GenerateContent` RPC URL.
* API real smoke: local WSL server with real credentials receives a successful chat completion response.
* Frontend real smoke: browser opens built-in WebUI, enables request logging, sends a Playground message, observes a non-error assistant response, opens request records, and verifies at least one detail entry.
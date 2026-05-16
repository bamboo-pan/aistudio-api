# Gateway Latency Findings

## Scope

Investigated chat/Gemini response latency in the FastAPI -> application service -> gateway -> BrowserSession path.

## Findings

* OpenAI chat and Gemini generation routes delegate to `handle_chat` / `handle_gemini_generate_content`.
* Non-streaming requests call `AIStudioClient.generate_content`, which captures a request template/snapshot and replays via the browser page.
* Streaming requests call `AIStudioClient.stream_generate_content`, then `StreamingGateway.stream_chat`, then `BrowserSession.send_streaming_request`.
* `BrowserSession._capture_template_sync` previously captured templates from Playwright `response` events and called `response.text()` before accepting the template. That waited for the upstream AI Studio template request to complete, so cold model-template capture included the full dummy generation time before the real user request started.
* The template data needed by later replay is available on the request object (`request.url`, `request.headers`, `request.post_data`) before the request reaches the network.
* A temporary Playwright route can capture the GenerateContent request and abort that dummy generation immediately. The hook page can then wait for the UI to become idle without waiting for a full model answer.

## Candidate Change

Switch `_capture_template_sync` to install a temporary route for GenerateContent, save URL, headers, and body immediately once a non-trivial post body is observed, abort the dummy request, then remove the route and wait for idle.

## Expected Impact

The first request for a model should no longer wait for the dummy `template` model response to finish before the actual request template is available. This should reduce cold-template latency, especially when the dummy upstream answer is slow.

## Risks

* Need to ensure headers/body captured from `request` have the same shape as the previous `response.request` path.
* Need unit coverage for request-event template capture and listener cleanup.

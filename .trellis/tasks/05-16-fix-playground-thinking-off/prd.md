# Fix playground thinking off

## Goal

Make the Playground Thinking control honor the `关闭`/`off` selection so users can disable thinking output for chat requests that support thinking.

## What I Already Know

* The Playground currently stores chat config with `thinking: 'off'` by default.
* The UI only sends `body.thinking` when the value is not `off`.
* The OpenAI-compatible chat route treats an omitted `thinking` value as default-on for AI Studio requests.
* As a result, selecting `Thinking = 关闭` behaves like leaving thinking unspecified, and the gateway can still enable default thinking.

## Assumptions

* The intended Playground behavior is that `关闭` explicitly disables thinking for the request.
* Existing API clients that omit `thinking` should keep their current behavior unless a test shows this is not viable.
* The fix should be scoped to the Playground request construction and regression coverage.

## Requirements

* When the Playground Thinking control is available and set to `off`, the chat request body must explicitly include `thinking: 'off'`.
* Existing non-off values (`low`, `medium`, `high`) must continue to be sent unchanged.
* The UI should continue to hide the Thinking control for models that do not support it.
* Session defaults and presets should continue to work as they do today.

## Acceptance Criteria

* [ ] A Playground chat request with Thinking set to off produces a request body containing `thinking: 'off'`.
* [ ] A Playground chat request with Thinking set to low/medium/high still sends that selected value.
* [ ] Existing static frontend capability tests pass, with a regression assertion for the off case.
* [ ] Relevant unit tests pass.
* [ ] Real WSL environment test is run because this changes API/frontend request behavior.

## Definition of Done

* Code change is minimal and follows existing frontend style.
* Tests cover the regression.
* Trellis task files are committed with the code changes.

## Out of Scope

* Changing backend default behavior for third-party clients that omit `thinking`.
* Redesigning the Playground Thinking UI.
* Changing how thinking content is displayed after a response.

## Technical Notes

* Likely implementation file: `src/aistudio_api/static/app.js`.
* Likely test file: `tests/unit/test_static_frontend_capabilities.py`.
* Backend behavior observed in `src/aistudio_api/application/api_service.py`: `_thinking_enabled(None)` returns true.

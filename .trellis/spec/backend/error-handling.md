# Error Handling

> How errors are handled in this project.

---

## Overview

Backend errors should be translated before they reach public API clients. The
gateway talks to unstable browser and AI Studio wire surfaces, so public routes
must prefer typed, user-readable errors over raw replay/capture exceptions.

---

## Error Types

- `AistudioError`: base domain error for gateway/account/model failures.
- `AuthError`: authentication or expired credential state.
- `UsageLimitExceeded`: quota/rate-limit state, usually returned as `429`.
- `RequestError`: lower-level HTTP/replay failure with a status code.
- Validation errors: request-shape or unsupported capability errors, usually
	returned as `400` before gateway calls.
- Unsupported feature errors: clear `501` responses for intentionally unsupported
	compatibility surfaces such as pure HTTP streaming.

---

## Error Handling Patterns

- Validate request shape and model capabilities before capture/replay whenever
	the condition can be detected locally.
- Convert known gateway errors into API errors at route/service boundaries.
- Do not log cookies, auth JSON, tokens, account IDs, or real account emails when
	handling credential or WSL verification failures.
- Cleanup temporary image files when validation fails after files have been
	created from data URLs or inline data.

---

## API Error Responses

- OpenAI-compatible `/v1/*` routes should return the OpenAI-style envelope when
	practical:

```json
{"error":{"message":"...","type":"invalid_request_error","code":null}}
```

- Non-OpenAI project routes may keep FastAPI `detail` responses, but messages
	must still be user-readable.
- Capability/validation failures should use `400`.
- Missing models should use `404` on model lookup routes and `400` on request
	routes when the requested model invalidates the request.
- Rate limits should use `429` with `rate_limit_exceeded` semantics.
- Unsupported compatibility features should use `501` or a clear unsupported
	message, especially for experimental pure HTTP mode.

---

## Common Mistakes

- Letting downstream wire errors such as unsupported image generation fields leak
	instead of validating against `ModelCapabilities` first.
- Returning generic `500` for user-fixable request problems such as empty
	messages, illegal roles, invalid numeric ranges, unsupported image sizes, or
	malformed image URLs.
- Creating temp image files during normalization and forgetting to delete them
	when a later validation step rejects the request.
- Exposing browser/session implementation errors for pure HTTP unsupported paths
	instead of returning a documented unsupported-feature error.

# Gemini Pro Image Resolution Probe

## Context

The user suspected `gemini-3-pro-image-preview` supports higher resolutions than the current shared image-size metadata advertises.

## Probe Setup

* Date: 2026-05-11
* Environment: WSL Ubuntu 24.04 temp copy at `/home/bamboo/aistudio-api-smoke-copilot-20260511`
* Credentials: real account directory mounted with `AISTUDIO_ACCOUNTS_DIR=/home/bamboo/aistudio-api/data/accounts`
* API path bypassed: called `AIStudioClient.generate_image()` directly so the current `/v1/images/generations` size whitelist did not block the test.
* Model: `gemini-3-pro-image-preview`
* Override field: `generation_config_overrides={"output_image_size": [None, token]}`

## Results

| Token | Result | Returned dimensions |
| --- | --- | --- |
| `1K` | Success | `1408x768` |
| `2K` | Success | `2816x1536` |
| `4K` | Success | `4096x4096` |

## Conclusion

`gemini-3-pro-image-preview` supports at least `2K` and `4K` output-image-size tokens through the existing wire field. Current code maps both `gemini-3.1-flash-image-preview` and `gemini-3-pro-image-preview` to shared `DEFAULT_IMAGE_SIZES`, so it under-advertises and rejects valid pro image resolutions before the gateway call.

## Implementation Implication

Split image-size capability metadata by model. Keep the flash image model on the previously verified 512/1K public sizes, and expose 2K/4K sizes only for `gemini-3-pro-image-preview` with the correct `output_image_size` mapping.
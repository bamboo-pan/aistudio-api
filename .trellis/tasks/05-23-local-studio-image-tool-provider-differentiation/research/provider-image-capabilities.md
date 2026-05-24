# Provider Image Capabilities

## Design Direction

Local Studio should treat image tool capabilities as provider/model-specific data, not as one hard-coded OpenAI image tool.

## Google AI Studio / Gemini

- Gemini image models are surfaced by the repo capability registry as normal models with `capabilities.image_output=true` and `image_generation` metadata.
- Known Gemini image models in this repo:
  - `gemini-3.1-flash-image-preview`: Flash image model with 512/1K square and 1K portrait/landscape options.
  - `gemini-3-pro-image-preview`: Pro image model with Flash sizes plus 2K and 4K options.
- Gemini image controls should use the selected Gemini image model's `image_generation.sizes` and defaults.
- Gemini options should not pretend to support OpenAI-only controls such as background, compression, and PNG/WebP output if the backend cannot honor them.
- The backend should use the selected Gemini image model from the image tool options when building the Google image request.

## OpenAI-Compatible Providers

- Custom OpenAI providers may expose OpenAI Responses image tool semantics.
- Existing Local Studio defaults assume `gpt-image-2` and size options documented in `GPT_IMAGE_2_SIZE_OPTIONS`.
- OpenAI-compatible image controls can keep quality/background/format/compression when the provider/tool supports them.
- OpenAI-compatible settings must remain independent from Gemini settings so switching providers does not leak invalid choices.

## Shared Capability Contract

A useful UI-facing contract should include:

- `provider_type`
- `model`
- `label`
- `sizes`
- `defaults`
- `parameters`
- `unsupported_fields`
- `ignored_fields`
- optional notes/help text

The existing model `image_generation` metadata already has most of this shape for Gemini-capable models and should be reused where possible.

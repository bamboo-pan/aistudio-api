# Technical Plan

1. Load backend spec and Local Studio implementation context.
2. Extend Local Studio image tool settings to include provider-aware image model selection.
3. Reuse model `image_generation` metadata for Gemini image models and define OpenAI-compatible metadata for `gpt-image-2`.
4. Update frontend Image Tool panel labels, model select, size options, and conditional parameters.
5. Update Local Studio payload construction so Google AI Studio sends the selected Gemini image model and supported options, while OpenAI-compatible providers send OpenAI image tool options.
6. Update Responses image generation backend to honor selected Gemini image model and deduplicate image output persistence/streaming.
7. Add/adjust unit tests and static frontend tests.
8. Run simulated tests and real WSL/API/Web tests for Gemini and custom OpenAI-compatible providers.

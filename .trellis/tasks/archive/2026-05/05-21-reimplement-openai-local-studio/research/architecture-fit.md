# Architecture Fit

## User-provided source summary

The previous implementation should have reproduced a local OpenAI Responses API chat/image workbench named `openai-responses-chat`, with title `OpenAI Local Studio`, originally described as an Express + static HTML/CSS/JS project. Its key features are configurable OpenAI-compatible `/v1` endpoints, Responses API chat, attachments, reasoning display, image generation through `gpt-image-2`, local conversation/history persistence, and rerun from an earlier turn.

## Repository constraints

- This repository is a Python/FastAPI package named `aistudio-api`, not a Node/Express app.
- Static UI is currently served from `src/aistudio_api/static/` and implemented with Alpine-style plain JavaScript, HTML, and CSS.
- Existing routes already provide OpenAI-compatible AI Studio proxy endpoints under `/v1`, generated-image storage, image sessions, request logs, and account management.
- Adding a separate Node service would conflict with the package shape and deployment flow. The safer fit is an in-repo local studio page backed by FastAPI routes.

## Implementation direction

Implement an `OpenAI Local Studio` view inside the current static app, plus FastAPI local-studio endpoints that can call an arbitrary OpenAI-compatible base URL/token supplied by the browser. Persist conversations and uploaded/generated assets under a local data directory managed by Python infrastructure.

## Non-goals

- Do not restore the incorrect GPT image prompt workbench commit.
- Do not introduce React, Vite, Express, or a Node runtime requirement.
- Do not hard-code third-party credentials in source files.

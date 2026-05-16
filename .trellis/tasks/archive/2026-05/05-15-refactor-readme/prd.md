# Refactor README From Latest Repository State

## Goal

Refactor the project README documentation so a new user can understand, install, run, authenticate, and call the current AI Studio API service without following stale commands or incomplete feature descriptions.

## What I Already Know

* The repository has two README files: `README.md` in Chinese and `README_EN.md` in English.
* `pyproject.toml` defines Python 3.11+, package scripts `aistudio-api`, `aistudio-api-server`, and `aistudio-api-client`.
* The root `main.py` is a local wrapper around `aistudio_api.main`.
* The current unified CLI supports `server`, `client`, and `snapshot` commands only.
* There is no `Dockerfile` in the repository, so Docker instructions in the English README are stale.
* Current account login and account management are exposed by the WebUI and `/accounts/*` routes, not by `main.py login` or `main.py account add` commands.
* The FastAPI app exposes OpenAI-compatible routes, Gemini-native routes, account routes, image-session routes, generated-image static/delete routes, health/stats routes, and rotation-management routes.
* The static WebUI includes Playground, image generation, and account management views.
* Model capabilities are centralized in `src/aistudio_api/domain/model_capabilities.py` and include image sizes, response formats, file input support, streaming, search, thinking, tools, and structured output metadata.

## Requirements

* Rewrite `README.md` around the latest repository behavior and code paths.
* Keep `README_EN.md` aligned with the same structure and facts, unless later scoped out.
* Remove or replace stale commands that are not supported by the current code, including `python3 main.py login`, `python3 main.py account add`, and Docker build/run steps.
* Document supported startup paths: local root wrapper (`python main.py server`) and installed console scripts from `pyproject.toml`.
* Document WebUI entry points and core flows: Playground, image generation, account management, credential import/export, image session history where useful.
* Document API surfaces with concise curl examples for OpenAI-compatible, Gemini-native, images, accounts, rotation, and health/status endpoints.
* Refresh the configuration table from `src/aistudio_api/config.py`.
* Refresh the supported-model section from `MODEL_CAPABILITIES` instead of copying the older partial table.
* Keep sensitive credential warnings visible around account export/import.
* Keep the README focused on usage and operation, not implementation minutiae.

## Acceptance Criteria

* [ ] `README.md` no longer references unsupported commands or missing repository assets.
* [ ] `README_EN.md` no longer references unsupported commands or missing repository assets.
* [ ] Quick-start commands match the current package entry points and local wrapper.
* [ ] The feature/API/model/config sections match the inspected code.
* [ ] Markdown renders cleanly with valid fenced code blocks and tables.
* [ ] Verification includes at least a documentation consistency check and relevant tests or a clear note if no runtime tests are needed for docs-only changes.

## Definition of Done

* README files are updated.
* Trellis context is curated before implementation.
* Project lint/type/test checks appropriate for a docs-only change are run or explicitly scoped.
* Spec-update gate is evaluated before finishing.
* Changes are committed per workflow and the branch is pushed.

## Technical Approach

Use repository inspection as the source of truth. Keep the README structure compact and operational: overview, features, quick start, authentication/accounts, API examples, models/capabilities, configuration, architecture/runtime notes, development, BotGuard, acknowledgements/license. Update Chinese first, then mirror to English.

## Decision (ADR-lite)

**Context**: Existing README content is useful but partially stale and asymmetric between Chinese and English.

**Decision**: Refactor both README files in one docs task and make code-derived facts the authority.

**Consequences**: The docs change is broader than a typo fix, but prevents users from following removed commands and keeps the bilingual documentation consistent.

## Expansion Sweep

* Future evolution: README should be easy to update when models/routes/config grow; prefer grouped tables and source-of-truth wording over long prose.
* Related scenarios: API examples should stay consistent across OpenAI-compatible and Gemini-native users, plus WebUI users who manage accounts visually.
* Failure and edge cases: call out credential sensitivity, experimental pure HTTP limitations, and unsupported fields/routes that return explicit errors.

## Out of Scope

* No behavior changes to application code.
* No new screenshots or generated visual assets.
* No Docker documentation unless a Dockerfile is added in this task.
* No exhaustive API reference for every request/response schema.

## Technical Notes

* Inspected `README.md`, `README_EN.md`, `pyproject.toml`, `requirements.txt`, `main.py`, `src/aistudio_api/main.py`, `src/aistudio_api/config.py`, `src/aistudio_api/api/app.py`, route modules, model capability registry, account store/login service, and static WebUI entry points.
* Console scripts from `pyproject.toml`: `aistudio-api`, `aistudio-api-server`, `aistudio-api-client`.
* Current local commands: `python main.py server`, `python main.py client`, `python main.py snapshot`.
* Current WebUI root redirects to `/static/index.html`.
* Generated images are served under the configured generated-images route and can be deleted by API.
* Image session history is stored under the configured image sessions directory and exposed by `/image-sessions` routes.
# Add GPT Image Prompt Subpage

## Goal

Add the half-finished `C:/Users/bamboo/Desktop/GPT_image` tool into this project as a new image-focused subpage by absorbing its product ideas and the OpenAI image prompting guide, while using this repository's existing FastAPI backend, OpenAI-compatible image endpoints, account system, static Alpine frontend, and local generated-image/session stores.

## What I Already Know

- The source tool is a standalone Node/Express OpenAI Responses workbench with local token/API URL inputs, chat history, prompt templates, image settings, and image outputs.
- This project already has a Python/FastAPI backend and static Alpine frontend, so the source tool's Express backend should not be migrated.
- This project already exposes `/v1/images/generations`, `/v1/images/prompt-optimizations`, `/image-sessions`, and static `/generated-images` serving.
- The existing frontend already has `Playground`, `图片生成`, `请求记录`, and `账号管理` views.
- The new page should be a new subpage in the current navigation, not a replacement for existing `图片生成` unless integration requires shared helpers.
- Testing key material is present in the source directory, but final real testing should use this project's real WSL environment and account data per `AGENTS.md`.

## Requirements

- Add a new navigation entry and routable hash view for a GPT/OpenAI image prompt workbench.
- Build the UI with the existing static Alpine app and current CSS conventions.
- Do not introduce a Node/Express runtime into this project.
- Reuse existing backend image generation and prompt optimization endpoints when possible.
- Provide a prompt-building workflow inspired by the OpenAI prompting guide:
  - workflow/use-case presets such as photorealistic, infographic, ad, UI mockup, edit, product, and comic/story panel;
  - structured fields for subject, scene, composition, lighting/materials, text, and constraints;
  - edit-specific `Change only` and `Preserve exactly` fields;
  - one-click prompt composition into the generation prompt;
  - one-click use of existing prompt optimizer;
  - one-click generation through the existing image generation path.
- Keep image model, size, count, response format, timeout, and reference image behavior aligned with existing project capabilities.
- Do not store external OpenAI tokens in this project or UI.
- Ensure the new page works on desktop and mobile without overlapping or clipped controls.
- Preserve existing `图片生成` behavior unless deliberate shared-helper changes are needed.

## Acceptance Criteria

- [ ] A new subpage is visible in the sidebar and accessible by hash route.
- [ ] The page can compose a structured prompt from selected workflow + fields.
- [ ] The page can send the composed prompt to the existing image generation endpoint.
- [ ] The page can use existing prompt optimization and apply optimizer output.
- [ ] The page can use existing reference image inputs/edit mode where available.
- [ ] Generated images display using the current generated-image result UI/storage behavior.
- [ ] Unit/static tests cover navigation, page controls, prompt composition hooks, and request payload expectations.
- [ ] `node --check src/aistudio_api/static/app.js` passes.
- [ ] Relevant Python tests pass.
- [ ] Full API real test passes in WSL real environment.
- [ ] Web UI real-use test passes in a browser against the WSL real environment.

## Out of Scope

- Migrating the source Node/Express backend or local JSON database.
- Adding browser-side OpenAI API token management.
- Implementing direct OpenAI API calls that bypass this project's account/runtime system.
- Replacing the existing `图片生成` page wholesale unless needed for shared helpers.

## Research References

- `research/source-tool-and-openai-guide.md` — source tool inventory, OpenAI guide takeaways, and repo mapping.

## Technical Notes

- Follow backend spec and static frontend conventions already used by `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, and `src/aistudio_api/static/style.css`.
- Existing static JS has repo memory requiring `node --check src/aistudio_api/static/app.js` after edits.
- For real testing, follow `AGENTS.md`: use a temporary directory under WSL home and the real credentials under `/home/bamboo/aistudio-api/data/accounts`; non-documentation changes require API and actual frontend UI testing.

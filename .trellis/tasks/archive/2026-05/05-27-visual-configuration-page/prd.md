# Add visual configuration page

## Goal

Add a System Configuration page to the existing static admin UI so runtime environment options that are not already represented elsewhere can be viewed and edited visually. The page should include settings such as `AISTUDIO_USE_PURE_HTTP` and avoid duplicating controls already covered by pages like request logs, account rotation, Local Studio provider settings, playground interface/model options, or image generation controls.

## What I already know

* The app is a single static Alpine UI in `src/aistudio_api/static/index.html`, `app.js`, and `style.css`.
* Existing visualized controls include request-log enablement, account rotation mode/cooldown, Local Studio provider/interface/model/cache/image options, Playground interface/model/chat options, and image-generation model/size/session controls.
* Runtime env settings are centralized in `src/aistudio_api/config.py` as the `Settings` dataclass plus `DEFAULT_*` constants.
* `AISTUDIO_USE_PURE_HTTP` is startup-sensitive because the API client is constructed during FastAPI lifespan with `settings.use_pure_http`.
* `AISTUDIO_USE_PURE_HTTP` should stay default-off; enabling it skips browser startup and account browser warmup.
* Automatic account browser warmup is controlled by `AISTUDIO_ACCOUNT_WARMUP_LIMIT` and only applies when Pure HTTP is off and accounts exist.
* There is currently no backend API for listing/updating general app configuration.
* The project uses `python-dotenv`; `load_dotenv()` already reads a repo `.env` if present.

## Assumptions

* The page should persist edits into the project `.env` so values survive restart.
* For startup-sensitive settings, the UI should save the value but clearly show that a service restart is needed before effective runtime behavior changes.
* The first version should use a safe allowlist instead of exposing every environment variable, especially values that may contain credentials.
* Already visualized settings should be omitted from the new page even if they also have env defaults.

## Requirements

* Add a sidebar navigation entry and hash route for a System Configuration page.
* Add backend routes to list and update a safe allowlist of not-yet-visualized configuration keys.
* Include `AISTUDIO_USE_PURE_HTTP` as a boolean/toggle control without changing its default value.
* Include `AISTUDIO_ACCOUNT_WARMUP_LIMIT` and make the UI description clear that this, not Pure HTTP, controls startup account browser warmup.
* Include useful non-visualized service/runtime settings such as ports, timeouts, Camoufox launch/identity settings, filesystem paths, default models, concurrency, and warmup/retry limits, while excluding controls already visualized elsewhere.
* Persist changes to `.env` with validation and return the effective current value, stored value, default, description, category, and restart requirement metadata.
* Do not expose or persist raw credential material through the new page.
* Frontend must load config values, show validation/save errors, save individual settings, reset individual settings to default by removing them from `.env`, and show whether restart is required.
* Keep the UI consistent with the existing admin pages and mobile responsive.

## Acceptance Criteria

* [ ] `#config` opens a configuration page from the sidebar.
* [ ] `GET /config` returns grouped config metadata including `AISTUDIO_USE_PURE_HTTP`.
* [ ] `PUT /config/{key}` validates and saves a new value to `.env` for allowlisted keys only.
* [ ] `DELETE /config/{key}` removes an explicit `.env` value and resets that key to its default metadata value.
* [ ] Existing visualized settings such as request-log enablement and Local Studio provider profile values are not duplicated.
* [ ] Static frontend syntax check passes.
* [ ] Unit tests cover backend config API and static UI exposure.
* [ ] Real WSL API/UI smoke validates the config page is reachable and can save/reset a non-secret key without leaking secrets.
* [ ] The page clarifies that Pure HTTP skips account browser warmup and `AISTUDIO_ACCOUNT_WARMUP_LIMIT` controls automatic account warmup.

## Definition of Done

* Tests added/updated where appropriate.
* Static JS syntax check passes.
* Unit/API checks pass.
* Real environment API and browser UI smoke checks pass because this is a code/UI/API change.
* Task files under `.trellis/tasks/05-27-visual-configuration-page/` are committed with the work.

## Out of Scope

* Hot-restarting the running FastAPI server from the UI.
* Exposing raw account credentials, API keys, auth JSON contents, or provider tokens.
* Reworking existing pages that already visualize their own settings.

## Technical Notes

* Relevant files inspected: `src/aistudio_api/config.py`, `src/aistudio_api/api/routes_system.py`, `src/aistudio_api/api/app.py`, `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`, `tests/unit/test_static_frontend_capabilities.py`, `tests/unit/test_pure_http_boundary.py`.
* `python-dotenv` is available in project dependencies and should be preferred for `.env` read/write over ad hoc parsing when possible.

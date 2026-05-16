# fix: Camoufox launcher import path

## Goal

Fix account login startup when the headed Camoufox login browser is launched from a source checkout in WSL. The launcher subprocess must be able to import project modules regardless of whether the package was installed editable or the server was started through the root `main.py` wrapper.

## What I already know

* The user reported login failure while starting the login browser on port 9223.
* The traceback shows `camoufox_launcher.py` exits before startup with `ModuleNotFoundError: No module named 'aistudio_api'`.
* Reproduced in WSL with the equivalent command from `/home/bamboo/aistudio-api`: `/home/bamboo/aistudio-api/venv/bin/python3 src/aistudio_api/infrastructure/browser/camoufox_launcher.py --port 9223`.
* This repository uses a `src/` layout and the local root `main.py` wrapper inserts `src` into the parent server process path, but that path does not automatically carry into a subprocess launched by file path.

## Requirements

* The Camoufox launcher subprocess used by account login must be able to import `aistudio_api.config` from a source checkout.
* The fix must work in WSL real environment with `/home/bamboo/aistudio-api` and its venv.
* The fix should not require users to manually set `PYTHONPATH` for login browser startup.
* Preserve support for `AISTUDIO_CAMOUFOX_PYTHON` selecting a separate Python executable.
* Keep the change narrowly scoped to browser launcher startup/import behavior.

## Acceptance Criteria

* [ ] The equivalent launcher startup command no longer fails with `ModuleNotFoundError: No module named 'aistudio_api'` when run from the WSL source checkout.
* [ ] A focused automated test covers the subprocess environment/path construction or equivalent import-path behavior.
* [ ] Relevant unit tests pass.
* [ ] WSL real-environment verification passes for this browser/account-related change.

## Definition of Done

* Tests added or updated where appropriate.
* Lint/typecheck/test commands relevant to the change pass.
* WSL real test is run because the change affects account/browser startup.
* Task files and code changes are committed together.

## Out of Scope

* Changing the login UI or Google account completion detection.
* Changing Camoufox installation or dependency versions.
* Changing account storage format or rotation behavior.

## Technical Notes

* Likely impacted files: browser launcher/manager code and unit tests around browser startup.
* A minimal workaround is setting `PYTHONPATH=/home/bamboo/aistudio-api/src`, but the product should do this automatically for the launcher subprocess.
* Prefer a root-cause fix in subprocess launch environment or launcher module execution, not a user-facing documentation-only workaround.

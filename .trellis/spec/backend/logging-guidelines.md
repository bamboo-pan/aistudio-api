# Logging Guidelines

> How logging is done in this project.

---

## Overview

The backend uses the standard Python `logging` module. Logs are operational
signals for gateway/account behavior and must never become proof dumps of real
credential material. This is especially important during WSL verification, where
the real `AISTUDIO_ACCOUNTS_DIR` may be present.

---

## Log Levels

- `info`: successful high-level events such as selected model, selected account
	tier, rotation mode, stream cancellation, or completed account switch.
- `warning`: recoverable degraded behavior such as image-model fallback to a
	non-premium account, rate-limit cooldowns, snapshot refresh retry, unsupported
	experimental mode, or account isolation.
- `error`: unexpected gateway, stream, normalization, or replay failures that
	require investigation. Use `exc_info=True` only when the exception cannot include
	credential payloads.

---

## Structured Logging

- Prefer explicit scalar fields in the message arguments: `model`, account `tier`,
	rotation `mode`, attempt number, and sanitized reason.
- Do not log whole request bodies, storage-state payloads, cookies, auth JSON, or
	raw WSL smoke output.
- Account selection logs may include tier and reason, but not account id or real
	email.

---

## What to Log

- Account selection reason when model-tier routing changes the selected account.
- Premium fallback for image models when no healthy Pro/Ultra account is
	available.
- Rate-limit cooldown and automatic isolation events, without account identity.
- Stream cancellation/disconnect and unsupported pure HTTP boundaries.
- Snapshot refresh retries and pure HTTP snapshot unavailability as sanitized
	diagnostic messages.

---

## What NOT to Log

- Browser storage-state JSON, cookies, token values, auth files, and raw request
	bodies that may include credentials.
- Real account emails, account IDs, or local account directory names during WSL
	verification.
- Raw upstream response bodies when dumping could include user content or account
	state. If raw dumps are enabled for debugging, keep them opt-in and out of task
	logs/final summaries.

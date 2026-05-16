# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### Scenario: Explicit UI Request Fields When Backend Defaults Differ

#### 1. Scope / Trigger

- Trigger: Frontend controls that map to API request fields where omission has backend semantics.
- Applies to Playground and other UI surfaces that call `/v1/chat/completions` or related API routes.

#### 2. Signatures

- API: `POST /v1/chat/completions`
- Relevant request field: `thinking: "off" | "low" | "medium" | "high"`

#### 3. Contracts

- UI `off` must be serialized as `thinking: "off"` when the control is available.
- UI `low` / `medium` / `high` must be serialized as the selected value.
- Omitted `thinking` is reserved for API-client default behavior and must not be used to represent an explicit UI off state.

#### 4. Validation & Error Matrix

- Unsupported model capability -> hide or disable the UI control before request construction.
- Invalid `thinking` value -> backend rejects with a bad request.
- Explicit UI off omitted from request -> bug, because backend may apply default-on behavior.

#### 5. Good/Base/Bad Cases

- Good: Thinking control available and set to off sends `{"thinking":"off"}`.
- Base: Thinking control unavailable sends no `thinking` field.
- Bad: Thinking control available and set to off sends no `thinking` field.

#### 6. Tests Required

- Static frontend regression: assert request construction includes the explicit off assignment.
- API compatibility tests: ensure non-off thinking values and backend defaults continue to behave as expected.
- Real environment check for chat/API request changes when the behavior depends on upstream AI Studio.

#### 7. Wrong vs Correct

##### Wrong

```javascript
if (controlAvailable('thinking') && cfg.thinking !== 'off') body.thinking = cfg.thinking;
```

##### Correct

```javascript
if (controlAvailable('thinking')) body.thinking = cfg.thinking;
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)

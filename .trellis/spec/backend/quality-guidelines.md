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

<!-- Patterns that must always be used -->

(To be filled by the team)

##### Correct request-level image timeout override

```python
image_kwargs = {"prompt": prompt, "model": model}
if req.timeout is not None:
	image_kwargs["timeout"] = req.timeout
output = await client.generate_image(**image_kwargs)
```

```javascript
const timeout = this.normalizeImageTimeout()
const body = { model: this.imageModel, prompt, size: this.imageSize }
if (timeout) body.timeout = timeout
```

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)

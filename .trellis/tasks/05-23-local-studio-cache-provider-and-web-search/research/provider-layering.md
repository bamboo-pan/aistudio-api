# Provider Layering

## Goal

Define a clean layer model for Local Studio so provider selection, model loading, and tool toggles do not conflict with the existing Playground and image pages.

## Observed Structure

- The current app already has separate workbenches for Playground, Local Studio, and image generation.
- Playground currently exposes chat, search, thinking, and structured output.
- The image page currently exposes image generation/editing capabilities.
- Local Studio currently stores one base URL/token/mode set and then loads models from that endpoint.

## Recommended Layer Model

### 1. Workbench

Local Studio is the top-level orchestration surface.

### 2. Provider Profile

A saved provider profile should own:

- display name
- upstream base URL
- token
- timeout
- interface/mode selection
- optional defaults

### 3. Provider Capability Set

A provider contributes capabilities such as:

- chat
- search
- image
- streaming
- reasoning
- structured output

### 4. Model Selection

After choosing the provider, Local Studio loads the provider's models and lets the user pick one.

### 5. Tool Toggles

Tools are capability gates on top of the selected model.

- chat only
- chat + image
- chat + search + image

## Why This Helps

- It separates connection management from model choice.
- It makes it obvious when a capability comes from the provider rather than the current page.
- It allows Google AI Studio to be wrapped once and reused.
- It leaves room for additional providers later.

## Fit With Existing Code

- The current Local Studio payload path already routes by `interface_mode`.
- The existing Playground and image pages already prove the Google AI Studio capability set exists.
- The new provider layer should reuse those capabilities instead of duplicating them.

## Implementation Direction

- Introduce a provider registry or profile list in browser state.
- Bind Local Studio settings to the selected provider profile.
- Drive model loading from the selected provider.
- Drive tool visibility from model/provider capabilities.

## Success Criteria

- Provider selection is visible and persistent.
- Model loading is provider-specific.
- Tool toggles are capability-based, not hard-coded to one page.
- Google AI Studio becomes one provider in the system, not the system name itself.

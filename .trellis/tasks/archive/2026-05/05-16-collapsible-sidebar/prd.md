# Collapsible Sidebar

## Goal

Make the left navigation sidebar collapsible on desktop so users can reclaim horizontal workspace while keeping navigation available at the screen edge.

## Requirements

* Desktop sidebar defaults to expanded and can collapse into a narrow icon rail anchored on the left edge.
* Expanded state shows logo, product name, navigation labels, and online footer as today.
* Collapsed state preserves navigation via icons, hides nonessential text, and exposes a clear expand/collapse control.
* The main content area expands immediately when the sidebar collapses.
* The user preference is stored in `localStorage` and restored on reload when available.
* Mobile behavior remains the existing overlay drawer controlled by the topbar menu button.
* Existing route navigation, account management, image generation, Playground, settings, and model controls continue to work.

## Acceptance Criteria

* [ ] On desktop, clicking the sidebar collapse control toggles between full sidebar and narrow icon rail.
* [ ] Collapsed desktop sidebar leaves enough visual affordance to reopen it from the left edge.
* [ ] Main content width increases when collapsed.
* [ ] Browser reload restores the last desktop sidebar preference.
* [ ] On mobile width, the topbar menu still opens the drawer and route navigation closes it.
* [ ] Static frontend tests cover the collapse state, markup anchors, and CSS hooks.

## Definition of Done

* Unit/static tests relevant to the static frontend pass.
* UI is smoke-tested in a browser at desktop and mobile widths.
* WSL real-environment smoke check is run per project instruction.
* No backend API contract changes are introduced.

## Technical Approach

Use Alpine state in `app.js` for `sidebarCollapsed`, initialize it from `localStorage`, and persist changes through a small toggle helper. Update `index.html` to bind a body-level collapsed class and add an icon button inside the sidebar header. Update `style.css` with desktop-only collapsed rail rules, while resetting collapsed styles inside the existing mobile media query so the drawer stays full width.

## Decision (ADR-lite)

**Context**: The current sidebar is fixed-width desktop navigation and only behaves like an overlay drawer on small screens.

**Decision**: Keep one sidebar component and add a desktop collapsed state instead of creating a second nav rail component.

**Consequences**: This keeps routing and active states centralized, with modest CSS complexity around responsive overrides.

## Out of Scope

* New routes, dashboards, or navigation hierarchy changes.
* Backend API changes.
* Drag-resizable sidebar width.

## Technical Notes

* Static files inspected: `src/aistudio_api/static/index.html`, `src/aistudio_api/static/app.js`, `src/aistudio_api/static/style.css`.
* Existing mobile drawer uses `sidebarOpen`; desktop collapse should use separate state so the two behaviors do not conflict.
* Relevant spec: `.trellis/spec/backend/quality-guidelines.md`, scenario "Static Playground Workbench UI".
# Odoo Modern SaaS Backend UX — Odoo 19 Community

A non-invasive backend UX platform for Odoo Community 19 designed around Odoo's OWL web client and asset bundles.

## Included

### Modern Shell
- Persistent SaaS sidebar
- Expanded / compact modes
- Mobile drawer behavior
- Global command trigger
- Appearance entry point
- User profile footer

### Design System
- CSS custom-property token layer
- Accent palette: violet, blue, emerald, rose, amber
- Light / dark / system theme modes
- Compact / comfortable / spacious density
- Small / modern / pill corner-radius presets
- Consistent cards, buttons, inputs, dropdowns, badges and empty states

### OWL Component Library
- `ModernBadge`
- `ModernStat`
- `ModernEmptyState`
- `ModernSectionHeader`
- Dashboard `KPI`, `ProgressCard`, `ActivityCard`, `QuickAction`
- Main-component registrations and component registry

### Command Center
- `Ctrl/Cmd + K`
- Global search focus
- Dashboard shortcut
- Appearance shortcut
- Escape to close

### Dashboard Framework
- Client action: `odoo_modern_backend.dashboard`
- KPI cards
- Performance overview chart primitive
- Activity feed
- Progress cards
- Quick actions

### Theme Customization Engine
Runtime preferences persisted to browser local storage:
- Accent color
- Theme mode
- Density
- Radius
- Sidebar mode
- Motion

### Odoo View Refresh
Global styling for:
- Control panel
- Search view
- List view
- Form view
- Notebook tabs
- Kanban view
- Chatter
- Statusbar
- Dropdowns
- Buttons
- Inputs

## Installation

1. Extract the folder into your Odoo addons path.
2. Restart Odoo.
3. Update the Apps list.
4. Install **Odoo Modern SaaS Backend UX**.
5. Hard-refresh the browser or open Odoo with `?debug=assets` while developing.

## Important

This module intentionally does **not** edit Odoo core files. It extends the `web.assets_backend` bundle and registers OWL components/services in the Odoo frontend registries.

The included code has been syntax-checked and its XML parsed in the build environment. It has not been executed against a live Odoo 19 server/database in this environment, so production deployment should include a smoke test of your exact Odoo Community build and installed custom modules.

## Recommended next production hardening

- Replace sample sidebar labels with dynamic Odoo menu/action data.
- Add server-backed per-user theme preferences when cross-device persistence is required.
- Add automated JS/QUnit tests for shell, theme service, command palette and dashboard action.
- Add per-application skin configuration keyed to actual Odoo action/menu metadata.
- Add accessibility validation (keyboard navigation, focus trapping, reduced motion, color contrast).
- Add Odoo version-specific compatibility adapters if the module must support more than 19.0.

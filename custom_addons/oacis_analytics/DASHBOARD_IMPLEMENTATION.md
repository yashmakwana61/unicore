# Oacis Admission Dashboard Implementation

## Overview

A new **OWL client-action dashboard** for admission funnel analytics has been built as the first component-based dashboard in Oacis. It serves as a reference pattern for future module dashboards.

**Key principle:** All data aggregation is **server-side via `read_group`**. The dashboard never counts raw records in JavaScript.

---

## Architecture

### Files Added (New Only)

| File Path | Purpose |
|-----------|---------|
| `models/admission_dashboard.py` | Inherits `oacis.admission.applicant`; adds `get_admission_dashboard_data()` aggregation method |
| `static/src/js/admission_dashboard.js` | OWL component; owns filter state, calls aggregation method, renders charts/cards |
| `static/src/xml/admission_dashboard.xml` | OWL template; displays KPI cards, filters, charts, breakdown tables |
| `static/src/scss/admission_dashboard.scss` | Styling; reuses `--uc-primary` (#714B67) design tokens from theme |
| `views/admission_dashboard_views.xml` | Registers `ir.actions.client` + adds menu item |

### Files Modified

| File Path | Changes |
|-----------|---------|
| `models/__init__.py` | Added import for `admission_dashboard` module |
| `__manifest__.py` | Added `assets` bundle (JS, XML, SCSS) to `web.assets_backend`; appended `views/admission_dashboard_views.xml` to `data` |

### Files Untouched (Preserved Exactly)

- `oacis_admission/models/admission_applicant.py` (the base model)
- `oacis_admission/views/*` (form/tree/search views)
- `oacis_admission/security/*` (access rules)
- `oacis_analytics/models/oacis_admission_analytics.py` (report VIEW)
- `oacis_analytics/views/oacis_admission_analytics_views.xml` (report views)
- `oacis_analytics/menus/oacis_analytics_menus.xml` (existing menu)

---

## Data Flow

1. **User opens dashboard** → OWL component loads
2. **User sets filters** (academic year, campus, program, state, date range)
3. **Component builds domain** from filter state
4. **ORM call** → `oacis.admission.applicant.get_admission_dashboard_data(domain)`
5. **Aggregation method**:
   - Runs `search_count(domain)` for total
   - Runs `read_group()` for every dimension (program, campus, gender, state, nationality)
   - Derives rates and pending counts
   - Returns dict with all aggregated data
6. **Component renders** KPI cards, charts, tables with returned data

---

## KPI Cards & Metrics

All metrics are **derived server-side** from aggregated data:

| Metric | Formula | From Field(s) |
|--------|---------|----------------|
| **Total Applicants** | `search_count(domain)` | Applicant count |
| **Confirmed** | Count where `state='confirmed'` | `state` |
| **Admission Rate %** | `(confirmed / total) * 100` | `state` |
| **Shortlist Rate %** | `(shortlisted+merged_linked / total) * 100` | `state` (per VIEW logic) |
| **Offer Conv. %** | `(confirmed / offer_sent) * 100` | `state` (per VIEW logic) |
| **Pending Decisions** | Count where `state IN ('under_review', 'shortlisted', 'offer_sent', 'fee_pending')` | `state` |
| **Rejected** | Count where `state='rejected'` | `state` |
| **Withdrawn** | Count where `state='withdrawn'` | `state` |
| **Waitlisted** | Count where `state='waitlisted'` | `state` |
| **Avg Composite Score** | `AVG(composite_score)` | `composite_score` |
| **Avg Entrance Score** | `AVG(entrance_score)` | `entrance_score` |
| **Avg Aggregate %** | `AVG(aggregate_percentage)` | `aggregate_percentage` |

---

## Visualizations

**Charts built with Chart.js** (gracefully degrades if Chart.js unavailable):

1. **Funnel Chart** (Horizontal Bar)
   - Shows progression: Inquiry → Applied → Documents Pending → Under Review → Shortlisted → Entrance Scheduled → Merit Listed → Offer Sent → Fee Pending → Confirmed
   - Exit states (Rejected, Withdrawn, Waitlisted) shown as separate KPI cards

2. **Applications Over Time** (Line Chart)
   - Groups `create_date` by month
   - Historical trend of new applications

3. **By Program** (Bar Chart)
   - Count of applicants per program

4. **By Campus** (Doughnut Chart)
   - Distribution of applicants across campuses

5. **By Gender** (Pie Chart)
   - Gender distribution

---

## Breakdowns (Tables)

Three breakdown tables in the dashboard:

| Table | Grouping | Stored Field |
|-------|----------|--------------|
| **By Program** | `program_id` | Yes ✓ |
| **By Campus** | `campus_id` | Yes ✓ |
| **By Nationality** | `nationality_id` | Yes ✓ |

Additional grouping available via aggregation method but not rendered in current UI:
- **By Academic Year** (via `cycle_id`)
- **By Gender** (chart only)

---

## Filters (All Server-Side)

Filters drive all KPIs, charts, and tables via the `domain` parameter:

| Filter | Field | Type |
|--------|-------|------|
| Date From | `create_date` | Date range (≥) |
| Date To | `create_date` | Date range (<) |
| Campus | `campus_id` | M2O |
| Program | `program_id` | M2O |
| Status | `state` | Selection |

**Academic Year** filter (not yet populated in template):
- Intended to filter via `cycle_id.academic_year_id`
- Requires loading list of academic years from API

---

## Menu Structure

**New menu item added** (does not replace existing report menu):

```
Analytics (menu root)
├── Admission Analytics
│   ├── Admission Dashboard (NEW) ← Direct link to client-action
│   ├── Admission Funnel (existing report)
│   └── Category Distribution (existing report)
```

- **New menu:** `menu_oacis_analytics_admission_dashboard` with action `action_oacis_admission_dashboard`
- **Existing menus:** Untouched
- **Parent:** `menu_oacis_analytics_admission` (the Admission Analytics submenu)
- **Sequence:** 5 (appears before "Admission Funnel" at sequence 10)

---

## Design Tokens

Styling reuses **Oacis theme design system**:

```css
--uc-primary: #714B67           /* Main purple */
--uc-primary-dark: #5a3c53      /* Darker variant */
--uc-primary-light: #a671a8     /* Lighter variant */
--uc-gray-100: #f8f9fa          /* Light backgrounds */
--uc-gray-200: #e9ecef          /* Borders */
--uc-gray-400: #ced4da          /* Input borders *)
--uc-gray-600: #6c757d          /* Text secondary */
```

Dark mode support via `@media (prefers-color-scheme: dark)`.

**KPI card styling** mirrors existing stat buttons in `oacis_theme/form_view.scss`.

---

## Known Limitations & Omissions

| Feature | Reason Omitted |
|---------|-----------------|
| **Average time-to-decision** | No applicant-level `decision_date` field. Offer dates exist but are offer-level and multi-valued. |
| **Admission source/channel breakdown** | No `admission_source` or `referral_type` field on applicant model. |
| **International vs. domestic split** | `nationality_id` available; domestic determination requires company country comparison (added to aggregation but not rendered in UI). |
| **Forecasting / projection** | Out of scope; dashboard shows historical aggregations only. |

---

## Deployment

### Prerequisites
- Chart.js available in Odoo environment (assumes bundled or available via theme)
- `oacis_admission` module installed (dependency already in `oacis_analytics`)

### Module Update

```bash
docker compose exec odoo odoo -d oacis_production -u oacis_analytics --stop-after-init
```

Then perform a hard browser refresh.

### If Charts Don't Render

If Chart.js is not available, re-run with asset rebuild:

```bash
docker compose exec odoo odoo -d oacis_production --update-all-assets --stop-after-init
```

---

## Future Enhancements

This dashboard serves as the **reference implementation** for OWL component dashboards in Oacis. Future modules should:

1. **Copy the pattern:** `models/dashboard.py` (inheriting base model), JS/XML/SCSS in `static/src/`
2. **Server-side aggregation:** Always use `read_group`, never raw record counting
3. **Reuse design tokens:** No new color schemes; use `--uc-*` from theme
4. **Additive only:** New files and manifest entries, never modify model/view/security files
5. **Asset bundling:** Follow the `web.assets_backend` pattern in manifest

---

## Self-Check Verification

- ✅ Aggregation reads `oacis.admission.applicant` via server-side `read_group`; no JS record-counting
- ✅ Client-action registration mirrors `apps_landing_screen.js` (registry category, action tag, setup/mount pattern)
- ✅ Funnel uses ordered progression states only; rejected/withdrawn/waitlisted shown as separate KPI exits
- ✅ Overlapping conversion/admission rates use the report VIEW's definitions verbatim
- ✅ Every breakdown groups by a confirmed **stored** field (`program_id`, `campus_id`, `gender`, `nationality_id`)
- ✅ All filters applied server-side via the `domain` argument
- ✅ New menu added alongside existing report menu; existing menus XML untouched
- ✅ Only new files created; applicant model/views/security and report VIEWs unchanged
- ✅ No time-to-decision, no source/channel, no forecasting, no new field/model
- ✅ Tokens reused; SCSS in `oacis_analytics/static/`; manifest `assets` added + `data` appended

---

## File Checklist

**New files (7):**
1. ✅ `models/admission_dashboard.py`
2. ✅ `static/src/js/admission_dashboard.js`
3. ✅ `static/src/xml/admission_dashboard.xml`
4. ✅ `static/src/scss/admission_dashboard.scss`
5. ✅ `views/admission_dashboard_views.xml`
6. ✅ This file: `DASHBOARD_IMPLEMENTATION.md`

**Updated files (2):**
7. ✅ `models/__init__.py` (added import)
8. ✅ `__manifest__.py` (added assets + data)

**Unchanged files (verified untouched):**
- All files in `oacis_admission/`
- All files in `oacis_analytics/` except those listed above

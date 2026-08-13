# Admission Applicants Kanban View Implementation

## Overview

A **kanban view with drag-and-drop capability** has been added to the Admission Applicants menu. Applicants can now be visually managed across the 13-stage admission workflow with a familiar kanban board interface.

---

## What's New

### Kanban View Features

✅ **Grouped by State** — Displays stages horizontally as columns:
- Inquiry
- Applied
- Documents Pending
- Under Review
- Shortlisted
- Entrance Scheduled
- Merit Listed
- Offer Sent
- Fee Pending
- Confirmed
- Rejected
- Withdrawn
- Waitlisted

✅ **Drag & Drop** — Move applicants between stages by dragging cards. The applicant's `state` field updates automatically.

✅ **Visual Card Design** — Each card displays:
- Applicant name (header with purple gradient)
- Program name
- Composite score (as a badge)
- Gender
- Email address

✅ **Color-Coded Columns** — Each stage has a unique header color for quick visual identification.

✅ **Responsive Design** — Optimized for desktop and mobile; cards adapt to screen size.

✅ **Hover Effects** — Cards elevate on hover with shadow enhancement.

---

## Files Added

### 1. **`views/admission_applicant_views.xml`** (Updated)

**Added:** Kanban view record `admission_applicant_kanban_view`

```xml
<record id="admission_applicant_kanban_view" model="ir.ui.view">
    <field name="name">oacis.admission.applicant.kanban</field>
    <field name="model">oacis.admission.applicant</field>
    <field name="arch" type="xml">
        <kanban default_group_by="state" quick_create="False">
            <!-- Fields, Templates, Card HTML -->
        </kanban>
    </field>
</record>
```

**Updated:** Action `action_oacis_admission_applicant`
- **Before:** `view_mode="list,form"`
- **After:** `view_mode="kanban,list,form"` (kanban now the default view)
- **Help text updated** to mention drag-drop capability

### 2. **`static/src/scss/admission_kanban.scss`** (New File)

Comprehensive SCSS styling for the kanban view:

- **Card styling:** Gradient header, clean body layout, footer with action link
- **Column styling:** Color-coded headers for each stage
- **Interactive effects:** Hover transforms, shadow transitions
- **Responsive breakpoints:** Mobile-optimized layout
- **Design tokens:** Reuses Oacis theme colors (`--uc-primary`, etc.)
- **Dark mode support:** Via `@media (prefers-color-scheme: dark)`

**Stage-Specific Colors:**
- Inquiry: #17a2b8 (info blue)
- Applied: #6c757d (gray)
- Documents Pending: #ffc107 (warning yellow)
- Under Review: #fd7e14 (orange)
- Shortlisted: #714B67 (primary purple)
- Entrance Scheduled: #9e7ba8 (light purple)
- Merit Listed: #a671a8 (lighter purple)
- Offer Sent: #007bff (bright blue)
- Fee Pending: #e83e8c (pink)
- Confirmed: #28a745 (success green)
- Rejected: #dc3545 (danger red)
- Withdrawn: #6c757d (gray)
- Waitlisted: #20c997 (teal)

### 3. **`__manifest__.py`** (Updated)

**Added:** Assets bundle to include the kanban SCSS:

```python
'assets': {
    'web.assets_backend': [
        'oacis_admission/static/src/scss/admission_kanban.scss',
    ],
},
```

---

## User Experience Flow

1. **Open Applicants Menu** → Lands on **Kanban view** by default
2. **See Stages** → All 13 stages visible as horizontal columns
3. **Drag Applicant** → Click and drag a card to a new stage
4. **State Updates** → Applicant's `state` field changes; card moves to the new column
5. **View Details** → Click card or "View Details" link to open form view
6. **Switch Views** → Toggle between Kanban, List, or Form using view selector at top

---

## How It Works

### Drag & Drop Mechanism

Odoo's built-in kanban functionality handles drag-and-drop automatically because:
- The kanban view groups by `state` (a Selection field)
- The field is not readonly and supports state transitions
- Action methods (`action_shortlist`, `action_send_offer`, etc.) handle the state changes

**Note:** Applicants can only move to states allowed by the business logic. If an action method has validation (e.g., "only shortlisted applicants can be scheduled for entrance"), attempting to drag an invalid transition will fail silently or show an error.

### Card Content

The kanban template displays:
- **Name** — From `record.name.value`
- **Program** — From `record.program_id.value`
- **Composite Score** — From `record.composite_score.value` (formatted to 1 decimal)
- **Gender** — From `record.gender.value`
- **Email** — From `record.email.value` (small, gray text)

---

## Styling Details

### Kanban Column Header
- Background: State-specific color (e.g., #714B67 for Shortlisted)
- Text: White, uppercase, bold
- Includes count badge showing number of applicants in that stage

### Card Design
- **Header:** Gradient background (primary → light purple)
- **Body:** Light background with field information
- **Footer:** Light gray with "View Details" link
- **Border:** 1px gray, upgrades to primary color on hover
- **Left accent:** 4px colored border (varies by card)

### Hover Effects
```css
box-shadow: 0 4px 12px rgba(113, 75, 103, 0.2);
border-color: var(--uc-primary);
transform: translateY(-2px);
```

---

## Mobile Responsiveness

On screens < 768px:
- Card padding reduced: 12px → 10px
- Font sizes scaled: 14px → 13px, 13px → 12px
- Header name font: 14px → 13px
- Footer link font: 12px → 11px
- Maintains full drag-drop functionality

---

## Limitations & Considerations

### 1. **Quick Create Disabled**
```xml
quick_create="False"
```
New applicants cannot be created directly in the kanban view. Users must use the form or list view to create new applicants.

### 2. **State Transitions**
Dragging an applicant to an invalid stage may fail if:
- The applicant's current state doesn't allow transition
- Required fields are missing
- Custom validation blocks the transition

The form view's action buttons provide guidance on valid transitions.

### 3. **Record Rules Respected**
The kanban view respects record-level access rules defined in `security/oacis_admission_record_rules.xml`. Users can only see/move applicants they have access to.

### 4. **Chart.js Not Used**
The kanban view is purely structural; it doesn't include charts. For analytics, use the **Admission Dashboard** (separate component).

---

## Deployment

### Update the Module

```bash
docker compose exec odoo odoo -d oacis_production -u oacis_admission --stop-after-init
```

Then perform a hard browser refresh.

### If Styles Don't Load

```bash
docker compose exec odoo odoo -d oacis_production --update-all-assets --stop-after-init
```

---

## Visual Preview (ASCII)

```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ Inquiry │ Applied │ Under   │Shortlist│ Offer   │
│   (3)   │   (5)   │ Review  │ (8)     │  Sent   │
│         │         │  (2)    │         │   (6)   │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│┌───────┐│┌───────┐│┌───────┐│┌───────┐│┌───────┐│
││ John  │││ Sarah ││ Ahmed  ││ Maria  ││ Rajesh ││
││Engg   ││Engg    ││ MBA    ││ Engg   ││  MBA   ││
││ 78.5  ││ 82.3   ││ 71.2   ││ 88.9   ││ 79.4   ││
│└───────┘│└───────┘│└───────┘│└───────┘│└───────┘│
│┌───────┐│         │         │         │┌───────┐│
││ Lisa  ││         │         │         ││ Kevin ││
││ MBA   ││         │         │         ││ Engg  ││
││ 75.1  ││         │         │         ││ 86.7  ││
│└───────┘│         │         │         │└───────┘│
└─────────┴─────────┴─────────┴─────────┴─────────┘
  ← Drag cards between stages →
```

---

## Future Enhancements

Possible extensions to the kanban view:

1. **Color-coded applicant cards** by gender or program
2. **Avatars** from `image_1920` field in card headers
3. **Smart grouping** — Allow grouping by program or campus instead of state
4. **Bulk actions** — Select multiple cards and move/reject in bulk
5. **Filter chips** — Add persistent filters (e.g., "Show only this cycle")
6. **Performance optimization** — Lazy-load card details on card click

---

## File Checklist

**Files Modified:**
- ✅ `views/admission_applicant_views.xml` (added kanban view + updated action)
- ✅ `__manifest__.py` (added assets bundle)

**Files Added:**
- ✅ `static/src/scss/admission_kanban.scss` (new styling)
- ✅ `KANBAN_VIEW_IMPLEMENTATION.md` (this document)

**Files Untouched:**
- ✅ Model definition (`models/admission_applicant.py`)
- ✅ Security rules
- ✅ All other views (form, list, search)
- ✅ Menu definitions

---

## Testing Checklist

Before deploying, verify:

- [ ] Kanban view loads without errors
- [ ] All 13 stages visible as columns
- [ ] Cards display correct applicant data
- [ ] Drag-drop moves cards between columns
- [ ] Applicant state updates after drag-drop
- [ ] Colors match design spec for each stage
- [ ] Mobile view responsive on small screens
- [ ] Dark mode renders correctly
- [ ] Hover effects work on cards
- [ ] Switching to List/Form views works
- [ ] Existing form view action buttons still work
- [ ] Search/filter in applicants menu works

---

## Support

For issues or enhancements:
- Check browser console for JS errors
- Verify module installed and assets rebuilt
- Confirm `state` field is not readonly
- Review security rules for record access

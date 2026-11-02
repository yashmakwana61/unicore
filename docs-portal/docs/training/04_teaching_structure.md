# 4. Teaching — Academic Structure (Faculties → Departments → Programs)

Navigation: **Institution → Academic Structure** (`Faculties`, `Departments`, `Programs`, `Specialisations`).

> 🧭 **The dependency chain is enforced by the system** — Edicai refuses to activate a level until the level below it exists. The setup order is exactly:
> **Campus → Building → Faculty → Department → Program**

## 4.1 Create the Faculty

**Institution → Academic Structure → Faculties → New.**

![Faculties — empty list](images/24_faculties_empty.jpeg)

Form fields for our example `Faculty of Engineering` (`ENG`, Established 2001):

![Faculty form — blank](images/25_faculty_form_new.jpeg)

![Faculty form — filled](images/26_faculty_filled.jpeg)

Workflow is `Draft → Operational → Suspended → Closed`, driven by the **Set Operational** button.

### Guard rail #1

Clicking **Set Operational** on an empty faculty triggers:

> *You must add at least one department before setting the faculty to Operational.*

![Faculty needs a department](images/27_faculty_needs_department.jpeg)

Smart buttons at the top give quick counts — **Departments** and **Programs** link to the filtered lists:

![Faculty operational with counts](images/37_faculty_operational.jpeg)

## 4.2 Create the Department

**Institution → Academic Structure → Departments → New.**

| Field | Example |
|---|---|
| Department Name | `Computer Science` |
| Department Code | `CSE` |
| Faculty | `Faculty of Engineering` *(autocomplete)* |
| Head of Department | pick a faculty member (later) |

![Blank department form](images/28_department_form.jpeg)

### Guard rail #2

**Set Operational** needs at least one **Program**:

> *You must add at least one program before setting the department to Operational.*

![Department needs a program](images/29_department_needs_program.jpeg)

## 4.3 Create a Campus (needed before the program activates)

**Institution → Campuses → New** — Campus Name `Main Campus`, Code `MC`, Campus Type `Main Campus`, Student Capacity `5000`, tick **Is Main Campus**.

![Campus form — new](images/32_campus_form_new.jpeg)

> ⚠️ TIP: on an unsaved new record the breadcrumb shows `[False] False` — a cosmetic quirk; after save it becomes the proper `[MC] Main Campus`.
>
> The campus itself also has the Draft → Operational chain, and needs ≥1 Building: create one via the **Buildings** smart button (`Engineering Block`, code `EB` — the building form auto-fills the Campus!). See building form: [image](images/34_building_form.jpeg).

Once the building exists, **Set Operational** flips the campus into live state with `Suspend` / `Close` buttons:

![Campus operational](images/35_campus_operational.jpeg)

![Campus needed a building first](images/33_campus_needs_building.jpeg)

## 4.4 Create the Program

**Institution → Academic Structure → Programs → New** — the richest setup form:

| Field | Example |
|---|---|
| Program Name | `B.Tech Computer Science` |
| Program Code | `BTCS` |
| Degree Title | `Bachelor of Technology (Computer Science)` |
| Department | `Computer Science` *(Faculty auto-fills)* |
| Duration | `4.0` years — **Automatically yields 8 semesters** |
| Program Type | `Undergraduate` |
| Total Credits Required | `120` |

Workflow: `Draft → Approved → Active → Discontinued`.

On save, Edicai explains the derived structure:

![Semesters calculated dialog](images/30_program_semesters_calculated.jpeg)

### Guard rail #3 — campus required

**Activate** refuses until a campus is assigned:

![Program needs a campus](images/31_program_needs_campus.jpeg)

Fix: edit **Offered at Campuses** (tag widget) and add `[MC] Main Campus`:

![Campus assigned](images/36_program_campus_assigned.jpeg)

Then **Activate** → program is live.

## 4.5 Finish the chain & verify in Overview

Return to the Department and Faculty and click **Set Operational** on each — the guards pass now.

Open **Institution → Overview**: the KPI cards now count your setup (Campuses 1 · Programs 1), each with free drill-down on click, filterable by Institution/Campus, aggregating live via `read_group`:

![Overview with data](images/38_overview_populated.jpeg)

The pie chart at the bottom already breaks down Campuses by Type.

> ✅ **Setup chain complete.** Students/admissions in the next chapter depend on an *active program + operational department/faculty + semesters* — all done now.

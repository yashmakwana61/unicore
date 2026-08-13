# Oacis Fees — GL Accounting Integration Guide

## Overview
This module integrates Oacis Fee Invoices with Odoo's default accounting module (`account.move`). When a fee invoice is confirmed/sent, an automatic GL invoice is created and posted to the accounting system.

---

## Phase 1: Prerequisite Setup ✅

### What was implemented:
1. **Added 'account' dependency** to oacis_fees module
2. **Created `oacis.fee.accounting.config` model** to store GL configuration
   - Configurable sales journal
   - GL revenue account mapping
   - GL receivable account configuration
   - Optional tax settings
   - Auto-post and partner auto-create toggles
3. **Extended res.partner linking** for students
   - Auto-creates partner from student data
   - Auto-syncs partner when student details change
   - Archives partner when student is deleted

### Configuration Files Created:
- `models/oacis_fee_accounting_config.py` — GL config model
- `models/oacis_student_partner_ext.py` — Student ↔ Partner linking
- `views/oacis_fee_accounting_config_views.xml` — Configuration UI
- `views/oacis_student_partner_ext_views.xml` — Student form extension
- `security/oacis_fee_accounting_access.csv` — Access control

---

## Phase 2: Core GL Integration ✅

### What was implemented:

#### A. Extended Fee Invoice Model (`oacis_fee_invoice_gl_ext.py`)
New fields added:
- `account_move_id` — Links fee invoice to GL invoice
- `gl_status` — Shows GL invoice status (draft/posted/cancelled)
- `gl_invoice_number` — Display GL invoice number

#### B. Core Methods Implemented:

**1. `action_send()` (Modified)**
```python
# When user clicks "Send to Student":
1. Validates fee invoice has line items
2. Creates GL invoice if not already created
3. Sets fee invoice state to 'sent'
4. Logs activity message
```

**2. `_create_account_invoice()`**
```python
# Called when fee invoice is sent:
1. Validates accounting config exists
2. Verifies student has partner record
3. Creates account.move with:
   - move_type='out_invoice'
   - Links to student partner
   - Creates invoice lines for each fee
   - Adds discount and late fee as separate lines
4. Posts to GL if auto_post_invoice=True
5. Links account_move back to fee invoice
6. Logs creation message
```

**3. `action_cancel()` (Modified)**
```python
# When user cancels invoice:
1. Creates reversal GL invoice (credit note)
2. Posts reversal immediately
3. Sets fee invoice state to 'cancelled'
4. Logs activity message
```

**4. `_reverse_account_invoice()`**
```python
# Called when fee invoice is cancelled:
1. Uses Odoo's built-in reversal mechanism
2. Creates GL credit note with reversal reason
3. Posts credit note to GL
4. Updates reference in fee invoice
```

**5. `action_view_account_invoice()`**
```python
# Button action to open GL invoice:
1. Validates GL invoice exists
2. Opens account.move form in same window
```

#### C. Views Updated (`oacis_fee_invoice_gl_ext_views.xml`)
1. **Form view enhancements:**
   - Added "GL Invoice" stat button in button box
   - Added GL Invoice link field in Invoice Details section
   - Added GL Invoice Number and GL Status fields
   - New "GL Integration" tab showing GL details
   - Info messages showing GL posting status (draft/posted)

2. **List view enhancement:**
   - Added GL Status column to invoice list

---

## Data Flow Diagram

```
┌─────────────────────────────────┐
│  Student Creates Fee Invoice    │
│  (In oacis_fees app)          │
└────────────────┬────────────────┘
                 │ (Status: draft)
                 ↓
    ┌────────────────────────────┐
    │ Line Items Added            │
    │ (Tuition, Hostel, etc.)     │
    └────────────────┬────────────┘
                     │
                     ↓
        ┌──────────────────────────────┐
        │ User Clicks "Send to Student"│
        └────────────────┬─────────────┘
                         │
                         ↓
        ┌──────────────────────────────────────┐
        │ _create_account_invoice() Called      │
        │ ─────────────────────────────────── │
        │ 1. Get GL Config                     │
        │ 2. Validate student has partner      │
        │ 3. Create account.move (out_invoice) │
        │    - partner_id = student.partner    │
        │    - invoice_date, due_date          │
        │    - journal_id from config          │
        │ 4. Create invoice_line_ids:          │
        │    - Fee amounts → revenue account   │
        │    - Discount → revenue account (−)  │
        │    - Late fee → revenue account (+)  │
        │ 5. Post to GL if auto_post=True      │
        │ 6. Link account_move_id back         │
        └────────────────┬─────────────────────┘
                         │
                         ↓
        ┌──────────────────────────────────┐
        │ GL Invoice Created & Posted      │
        │ (Status: draft or posted)        │
        │                                  │
        │ GL Entries Posted:               │
        │ Dr: A/R (Accounts Receivable)    │
        │ Cr: Revenue (Tuition, etc.)      │
        │ Cr: Tax (if applicable)          │
        └──────────────────────────────────┘
```

---

## GL Account Mapping

When GL invoice is created, the following accounts are used:

| Fee Component | GL Account | Effect |
|---|---|---|
| Tuition Fee Line | Revenue Account (from config) | Credit |
| Hostel Fee Line | Revenue Account (from config) | Credit |
| Discount (−) | Revenue Account (from config) | Debit |
| Late Fee (+) | Revenue Account (from config) | Credit |
| Student A/R | A/R Account (default) | Debit |
| Tax (if configured) | Tax Account | Credit |

---

## Configuration Steps (for Administrators)

### Step 1: Go to Fees → Configuration → Accounting Configuration

### Step 2: Create/Edit Configuration
Fill in the following:
- **Institution:** Select the company/campus
- **Sales Journal:** Select the sales journal (e.g., "Invoices")
- **Revenue Account:** Select income account (e.g., "4000 — Tuition Revenue")
- **Receivable Account:** Select A/R account (optional - defaults to partner's default)
- **Default Taxes:** Optional — select any applicable taxes
- **Auto-Post to GL:** Enable to immediately post GL invoice, disable for manual review
- **Auto-Create Student Partner:** Enable to auto-create res.partner when student is created
- **Sync Partner on Update:** Enable to auto-sync res.partner when student details change

### Step 3: Save Configuration

---

## Testing Checklist

```
□ Create accounting config (Fees → Configuration → Accounting Configuration)
□ Create a student (if not exists)
□ Verify student has a billing partner (Students → partner_id field)
□ Create a fee invoice manually or via generation
□ Add fee line items
□ Click "Send to Student" button
□ Verify account.move is created (check GL Invoice button)
□ Verify GL invoice status is "draft" or "posted" (per config)
□ Check GL invoice details:
  - Partner linked to student
  - Invoice date and due date match
  - Revenue lines created with correct amounts
  - Discount shown as negative line (if applicable)
  - Late fee shown as positive line (if applicable)
□ Cancel fee invoice
□ Verify GL credit note (reversal) is created
□ Check GL entries are posted correctly
```

---

## Error Handling

### Common Errors & Solutions

**Error:** "No active fee accounting configuration found"
- **Cause:** Accounting config not created or not marked active
- **Solution:** Go to Fees → Configuration → Accounting Configuration and create/activate config

**Error:** "Student X does not have a billing partner configured"
- **Cause:** auto_create_partner was disabled or partner was deleted
- **Solution:** Manually create res.partner for student, or enable auto_create_partner

**Error:** "Journal must belong to the same institution"
- **Cause:** Selected journal belongs to different company
- **Solution:** Select a journal that matches the institution/company

---

## What's Next: Phase 3

Phase 3 will implement:
1. **Payment Reconciliation** — Link fee payments to GL entries
2. **Invoice Status Sync** — Auto-update fee invoice status based on GL reconciliation
3. **Bank Deposit Integration** — Handle bank deposits and payment matching
4. **Financial Reporting** — Enhanced GL-based financial reports

---

## Technical Notes

### Why separate GL invoice instead of direct GL posting?
1. **Auditability:** Clear link between fee system and GL
2. **Reversibility:** Easy to reverse using standard Odoo reversal mechanism
3. **Status Tracking:** Can see which fee invoices are posted to GL
4. **Payment Matching:** GL invoice lines can be matched with payments
5. **User Workflow:** Familiar Odoo invoicing workflow for staff

### Data Integrity
- `account_move_id` field is read-only to prevent accidental unlinking
- Fee invoice number is stored in GL invoice's reference field
- GL reversal creates credit note linked back to original GL invoice

### Performance Considerations
- GL invoice creation is synchronous (happens immediately)
- No background job needed
- Uses Odoo's standard account module (no custom GL posting)
- Indexed on `account_move_id` and `invoice_number` for fast lookups

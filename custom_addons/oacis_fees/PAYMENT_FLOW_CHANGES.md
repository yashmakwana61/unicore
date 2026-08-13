# Fee Payment Flow Restructuring

## Summary
Removed the separate fee payment recording layer from the Fees module. Payments are now recorded directly in the Odoo Accounting module using GL payment recording wizard.

---

## Changes Made

### 1. **Archived Fee Payment Model**
- Added `active` field to `unicore.fee.payment` (defaults to `False`)
- Model is kept for historical records but marked as archived
- Description updated: "Fee Payment (Archived - Use GL Invoicing)"

### 2. **Removed Fee Payment Views & Menus**
Removed from manifest:
- `views/unicore_fee_payment_views.xml` - Fee payment list/form views
- `views/unicore_fee_reconciliation_wizard_views.xml` - Manual reconciliation wizard
- `views/unicore_fee_batch_wizard_views.xml` - Batch migration wizard
- `views/unicore_fee_payment_gl_ext_views.xml` - Payment GL extension views

Removed from menus:
- "Payments" menu section
- "All Payments" menu item
- "Record Payment" menu item

### 3. **Updated Fee Invoice GL Extension**
Added new methods in `unicore_fee_invoice_gl_ext.py`:

**`action_record_payment()`**
- Opens GL payment recording wizard (account.payment.register)
- Works with the linked GL invoice
- Requires GL invoice to be posted

**`_update_payment_state()`**
- Syncs fee invoice status based on GL payment status
- Updates invoice to "paid" when GL is fully reconciled
- Updates to "partial" if only partial payment received

### 4. **Updated Fee Invoice Views**
- Added "Record Payment" button in header (shows when invoice is sent and GL posted)
- Button opens GL payment recording wizard
- Replaced old "View Fee Payments" button with "View GL Invoice" button
- Updated GL Integration page with new instructions

### 5. **Removed Payment GL Extensions**
- Removed `unicore_fee_payment_gl_ext.py` (no longer imported)
- Removed `unicore_fee_reconciliation_wizard.py` (no longer imported)
- Removed manual reconciliation logic
- Removed auto-reconciliation logic

### 6. **Updated Cron Jobs**
- Kept: Batch GL invoice creation cron job (hourly)
- Removed: Batch payment reconciliation cron job (now handled by GL)

### 7. **Cleaned Up Models Import**
Removed imports from `models/__init__.py`:
- `unicore_fee_payment_gl_ext`
- `unicore_fee_reconciliation_wizard`

---

## New Workflow

```
┌─────────────────────────────────────┐
│ 1. Create Fee Invoice in Fees       │
│    Module (Fees app)                │
└─────────────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────┐
│ 2. GL Invoice Created & Posted      │
│    (Debit A/R, Credit Revenue)      │
└─────────────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────┐
│ 3. Click "Record Payment" Button     │
│    on Fee Invoice                   │
└─────────────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────┐
│ 4. GL Payment Wizard Opens           │
│    (Accounting module)              │
│    - User records payment details   │
│    - Selects payment method         │
│    - Records amount                 │
└─────────────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────┐
│ 5. GL Journal Entry Posted          │
│    (Debit Bank, Credit A/R)         │
│    Payment automatically reconciled │
│    with invoice                     │
└─────────────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────┐
│ 6. Fee Invoice Status Updated       │
│    "paid" when GL fully reconciled  │
└─────────────────────────────────────┘
```

---

## Benefits

1. **Single Source of Truth**: Payments recorded only in GL/Accounting module
2. **No Duplication**: No separate fee payment model/layer
3. **Simpler Architecture**: Less code to maintain
4. **Native Accounting**: Uses Odoo's native payment recording
5. **Full Audit Trail**: All payment details in GL with standard Odoo reconciliation
6. **Less Manual Work**: No manual reconciliation wizard needed

---

## Testing Checklist

### ✓ Invoice to Payment Flow
1. Create a Fee Invoice in Fees module
2. Send invoice (triggers GL invoice creation)
3. Click "Record Payment" button
4. GL payment wizard should open
5. Record payment in GL
6. Fee invoice status should change to "paid"
7. Both GL invoice and payment entry should show as reconciled

### ✓ GL Module Integration
1. Go to Accounting > Invoices
2. Should see the GL invoice created from fee invoice
3. Should see payment entry when recorded
4. Both should show as reconciled

### ✓ Fee Payment Model (Archived)
1. Old fee payments should not be visible in normal views
2. Can still access archived records if needed (through developer tools)
3. No menu items for fee payment recording

### ✓ Configuration Check
1. Fee Accounting Configuration should be set with:
   - Sales Journal (for invoices)
   - Revenue Account
   - A/R Account
   - Bank Account (in GL)
   - Bank Journal (for payment entries)

---

## Migration Notes

- Existing fee payments remain in `unicore.fee.payment` model (archived)
- They don't affect normal operations
- New payments must be recorded through GL payment wizard
- Can query old data if needed using developer tools with `active_unlink_filter` disabled

---

## Removed Files (Still Exist But No Longer Used)

These files remain in the codebase but are not loaded by the module:
- `models/unicore_fee_payment_gl_ext.py` - Payment GL reconciliation
- `models/unicore_fee_reconciliation_wizard.py` - Manual reconciliation
- `views/unicore_fee_payment_views.xml` - Payment list/form views
- `views/unicore_fee_reconciliation_wizard_views.xml` - Reconciliation wizard views
- `views/unicore_fee_batch_wizard_views.xml` - Batch wizard views
- `views/unicore_fee_payment_gl_ext_views.xml` - Payment GL views

You can delete these files if desired, or keep them for reference.

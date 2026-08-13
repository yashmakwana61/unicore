# Oacis Fees — Payment GL Reconciliation Guide

## Overview
Phase 3 implements automatic reconciliation of fee payments with GL receivable lines. When a payment is confirmed, it's automatically matched to the GL invoice's receivable lines and reconciled.

---

## Workflow: Payment → GL Reconciliation

```
┌──────────────────────────────┐
│  Payment Created (Draft)     │
│  (User records fee payment)  │
└────────────────┬─────────────┘
                 │
                 ↓
    ┌────────────────────────────┐
    │ Payment Confirmation        │
    │ (User clicks "Confirm")     │
    └────────────────┬────────────┘
                     │
                     ↓ [action_confirm() called]
                     │
        ┌────────────────────────────────────────────┐
        │ Check: Fee Invoice has GL Invoice?         │
        │ Check: GL Invoice is Posted?               │
        └────────────────┬─────────────────────────────┘
                         │
                Yes      │
                ↓        │ No
        ┌─────────────────────────────┐
        │ _reconcile_with_gl()        │
        │ ─────────────────────────── │
        │ 1. Find unreconciled AR     │
        │    lines in GL invoice      │
        │ 2. Match payment to AR      │
        │ 3. Link matched lines       │
        │ 4. Create bank deposit      │
        │    move (if needed)         │
        │ 5. Reconcile GL entries     │
        └────────────────┬────────────┘
                         │
                         ↓
        ┌──────────────────────────────────┐
        │ Payment Status: CONFIRMED        │
        │ GL Status: RECONCILED (or PARTIAL)
        │                                  │
        │ GL Entry Status:                 │
        │ AR Line: RECONCILED ✓            │
        │ Bank Line: RECONCILED ✓          │
        └──────────────────────────────────┘
```

---

## Components Implemented in Phase 3

### 1. Payment GL Extension Model (`oacis_fee_payment_gl_ext.py`)

**New Fields:**
- `gl_matching_line_ids` — Links payment to matched GL receivable lines
- `bank_deposit_move_id` — GL move created for bank deposits
- `is_reconciled` — Boolean showing if payment is reconciled
- `reconciliation_status` — Enum: `not_started`, `partial`, `complete`

**New Methods:**

#### `_reconcile_with_gl()`
```python
# Called when payment is confirmed:
1. Find GL invoice from fee invoice
2. Locate unreconciled AR lines
3. Match payment amount to AR line balances
4. Link matched lines to payment record
5. Create bank deposit move if needed
6. Reconcile GL entries using Odoo's reconciliation API
7. Log reconciliation activity
```

#### `_perform_gl_reconciliation(ar_lines)`
```python
# Perform actual GL reconciliation:
1. Get or create bank deposit move
2. Get bank account lines from deposit move
3. Call Odoo's reconcile() to match AR + Bank lines
4. Updates GL reconciliation status in Odoo
```

#### `_get_or_create_bank_deposit_move()`
```python
# For bank payments (transfer, cheque, card, etc.):
1. Check if bank deposit move already exists
2. If not, create GL entry with:
   - Debit: Bank Account
   - Credit: A/R Account
3. Post move immediately
4. Link to payment record
```

#### `_unreconc ile_from_gl()` (on cancellation)
```python
# When payment is cancelled:
1. Remove GL reconciliation
2. Delete matching links
3. Create reversal for bank deposit move
```

### 2. Invoice Status Extension (`oacis_fee_invoice_status_ext.py`)

**New Fields:**
- `gl_fully_reconciled` — Shows if all GL AR lines are reconciled

**Enhanced Methods:**
- `_update_payment_state()` — Now logs GL reconciliation status
- `get_selection_value()` — Helper to display selection values
- `action_view_gl_reconciliation_status()` — Opens GL reconciliation report

### 3. Reconciliation Wizard (`oacis_fee_reconciliation_wizard.py`)

**Purpose:** Manual reconciliation for cases where automatic matching needs review

**Wizard Fields:**
- `payment_id` — The payment being reconciled
- `available_ar_line_ids` — All unreconciled AR lines from GL invoice
- `selected_line_ids` — Lines user selects to match
- `matched_amount` — Auto-calculated sum of selected lines
- `reconciliation_note` — Optional note for audit trail

**Wizard Actions:**
- `action_reconcile()` — Performs manual reconciliation
- `action_cancel()` — Closes wizard without changes

---

## Data Flow Diagram

```
Fee Invoice (with GL Invoice)
    ↓
    ├─→ GL Invoice (account.move, type='out_invoice')
    │   ├─→ Invoice Line: Tuition (Dr: AR, Cr: Revenue)
    │   ├─→ Invoice Line: Hostel (Dr: AR, Cr: Revenue)
    │   └─→ Implicit DR/CR lines
    │
    └─→ Fee Payment 1: ₹5000
        │
        ├─→ [action_confirm] triggers reconciliation
        │
        ├─→ _reconcile_with_gl() called
        │   │
        │   ├─→ Match ₹5000 to AR line
        │   ├─→ Link payment → AR line
        │   │
        │   └─→ _perform_gl_reconciliation()
        │       ├─→ Create Bank Deposit Move
        │       │   ├─→ Dr: Bank ₹5000
        │       │   └─→ Cr: AR ₹5000
        │       │
        │       └─→ Reconcile AR + Bank (Odoo API)
        │           ├─→ AR line: RECONCILED ✓
        │           └─→ Bank line: RECONCILED ✓
        │
        └─→ Payment Status: CONFIRMED + RECONCILED
            GL matching_line_ids: [AR line 1, Bank line 1]
```

---

## Reconciliation Scenarios

### Scenario 1: Simple Payment (Single Fee)
```
GL Invoice Lines:
  Line 1: ₹10,000 Tuition (Receivable)
  Line 2: ₹10,000 Revenue (offset)

Payment: ₹10,000

Result:
  ✓ Payment matched to Line 1 (AR)
  ✓ Bank deposit created
  ✓ Full reconciliation: COMPLETE
```

### Scenario 2: Partial Payment (Multi-line Fee)
```
GL Invoice Lines:
  Line 1: ₹5,000 Tuition (AR)
  Line 2: ₹3,000 Hostel (AR)
  Line 3: ₹8,000 Revenue (offset)

Payment 1: ₹5,000

Result:
  ✓ Payment matched to Line 1
  ✓ Line 2 remains unreconciled
  ⚠ Reconciliation: PARTIAL
  (Next payment will match Line 2)
```

### Scenario 3: Multiple Payments
```
GL Invoice Lines:
  Line 1: ₹5,000 (AR)
  Line 2: ₹3,000 (AR)
  Line 3: ₹8,000 Revenue

Payment 1: ₹5,000 → Matched to Line 1 (PARTIAL)
Payment 2: ₹3,000 → Matched to Line 2 (COMPLETE)

Result:
  ✓ Both payments reconciled
  ✓ All AR lines reconciled
  ✓ Fee Invoice Status: PAID
```

### Scenario 4: Manual Reconciliation
```
If automatic matching fails:
  1. User clicks "Manual Reconciliation" button
  2. Wizard opens showing:
     - Available AR lines
     - Payment amount
  3. User selects which lines to match
  4. Wizard performs reconciliation
  5. Audit trail recorded with user's note
```

---

## Bank Deposit Move

When a bank payment is recorded (transfer, cheque, card, online):

**Move Created:**
```
Journal: Sales (configured journal)
Type: Journal Entry

Debit Lines:
  - Bank Account: ₹5000

Credit Lines:
  - A/R Account: ₹5000
```

**Why?**
1. **Audit Trail:** Clear record of bank deposit
2. **Reconciliation:** Bank lines match with AR for full reconciliation
3. **Banking:** Can be matched with bank statement when imported
4. **GL Integrity:** Complete debit/credit record

**Not Created For:**
- Cash payments (already counted in cash GL)
- Scholarship adjustments (direct fee adjustment, no deposit)
- Fee waivers (offset against invoice)

---

## Reconciliation Status Values

### `reconciliation_status` Field

| Value | Meaning | Next Action |
|-------|---------|------------|
| `not_started` | Payment confirmed but not yet reconciled | Wait for auto-reconciliation or click Manual Reconciliation |
| `partial` | Payment matched to some but not all AR lines | More payments expected, or use Manual Reconciliation |
| `complete` | Payment fully matched to AR and bank reconciled | Matches invoice status: PAID or PARTIAL |

### `is_reconciled` Boolean
- `True` = Matched amount ≥ Payment amount (complete or over-reconciled)
- `False` = Partial match or no match

---

## GL Reconciliation Workflow in Odoo

### Odoo's Built-in Reconciliation
When you call `move_lines.reconcile()`:

1. **Validates:** Debit sum = Credit sum
2. **Matches:** Pairs AR line with Bank line
3. **Updates:** `reconciled` flag on matched lines
4. **Tracks:** Reconciliation in `account.partial.reconcile` table

### Impact on Invoice
- GL invoice's `state` remains `posted` (not affected by reconciliation)
- Invoice still tracks amount due from GL perspective
- But reconciliation shows "matched" status in GL

### Impact on Reporting
- GL reports show reconciled vs unreconciled separately
- Trial balance shows net effect (reconciled amounts cancel)
- Aged receivable report shows only unreconciled amounts

---

## Error Handling & Edge Cases

### Error: "No receivable lines in GL invoice"
- **Cause:** GL invoice structure unexpected (custom GL accounts?)
- **Solution:** Check GL invoice structure, adjust account mapping

### Error: "Cannot find bank account configured"
- **Cause:** No bank account in system
- **Solution:** Create bank account in Chart of Accounts

### Partial Reconciliation
- **When:** Payment doesn't match full AR balance
- **Why:** Might be intentional (payment plan) or accidental (payment entry error)
- **Fix:** Use Manual Reconciliation to verify matching

### Over-Reconciliation (payment > invoice amount)
- **Scenario:** Overpayment by student
- **Current:** Reconciliation still works, shows matched > invoice
- **Next:** Phase 4 could handle overpayment tracking/credit notes

---

## Testing Checklist

```
Phase 3 Payment Reconciliation Tests:

□ Create fee invoice with GL invoice
□ Create payment (draft)
□ Confirm payment → automatic reconciliation triggered
□ Verify:
  □ gl_matching_line_ids populated
  □ bank_deposit_move_id created (for bank payment)
  □ reconciliation_status = 'complete' or 'partial'
  □ is_reconciled flag updated
  □ Activity message logged

□ Check GL entries reconciled:
  □ AR line shows as reconciled in GL
  □ Bank line shows as reconciled in GL
  □ Trial balance: reconciled amounts offset correctly

□ Test partial payment:
  □ Create multi-line GL invoice
  □ Confirm partial payment
  □ Verify: reconciliation_status = 'partial'
  □ Verify: remaining AR lines still unreconciled

□ Test manual reconciliation:
  □ Create payment without auto-reconciliation
  □ Click "Manual Reconciliation" button
  □ Wizard opens showing AR lines
  □ Select lines manually
  □ Confirm wizard
  □ Verify: Payment reconciled as expected

□ Test cancellation:
  □ Cancel confirmed payment
  □ Verify: GL reconciliation removed
  □ Verify: Bank deposit reversal created
  □ Verify: AR lines unreconciled again

□ Test edge cases:
  □ Overpayment (payment > invoice)
  □ Payment with no GL invoice (should not reconcile)
  □ Zero-amount invoice (should handle gracefully)
  □ Multiple payments to same invoice
```

---

## Configuration Notes

No additional configuration needed beyond Phase 1-2 setup:
- ✓ GL config already created
- ✓ Revenue accounts already configured
- ✓ Receivable account already configured
- ✓ Journal already configured

**Optional Tweaks:**
- Disable auto-post in config to review GL before posting
- Adjust bank payment methods to control bank deposit creation
- Review tax settings if taxes apply

---

## Performance Considerations

- **Automatic Reconciliation:** Lightweight, no background jobs
- **Bank Deposit Move:** Created per payment (not batched) for immediate GL posting
- **GL Query:** Efficient filtered queries (indexed on account_type)
- **Reconciliation API:** Uses Odoo's native method (well-optimized)

---

## Audit Trail

Every reconciliation action is logged:
- `action_confirm()` → Activity message with payment details
- `_reconcile_with_gl()` → "Reconciled with GL. Matched N lines."
- `_get_or_create_bank_deposit_move()` → "Bank deposit move X created and posted."
- `action_cancel()` → "Payment cancelled by User" + reversal move created

GL moves themselves have:
- `ref` field = Fee invoice number (cross-reference)
- `payment_id` linked in GL (if needed)

---

## Integration Points

### With Fee Invoice
- GL invoice created when fee invoice sent
- Status updated when payments reconciled

### With GL (account.move)
- GL invoice linked 1:1 to fee invoice
- GL reconciliation synced with fee payment status

### With Fee Payment
- Payment confirmed → auto-reconciliation
- Reversal on cancellation

### With Bank (Future)
- Bank deposit moves can be matched with bank statement
- Enables cash flow tracking and bank reconciliation

---

## What's Ready for Phase 4?

Phase 4 could enhance with:
- [ ] Overpayment tracking (credit memo generation)
- [ ] Bank statement import matching
- [ ] Dunning/collection notices (for overdue)
- [ ] Multi-currency with forex gain/loss
- [ ] Tax adjustment and reclassification
- [ ] Batch payment processing wizard
- [ ] Financial statement integration

---

## Support & Troubleshooting

**Issue:** Reconciliation not triggering automatically
- Check: Fee invoice has GL invoice? (status: sent or later)
- Check: GL invoice is posted? (not in draft)
- Check: Config has auto_post enabled? (else GL in draft)
- Fix: Manually click "Manual Reconciliation" if needed

**Issue:** Wrong AR lines matched
- Fix: Cancel payment, click "Manual Reconciliation"
- Select correct lines explicitly
- Add note explaining the correction

**Issue:** Bank deposit move not created
- Check: Payment method is "bank_transfer" or similar?
- Check: Bank account exists in GL?
- Check: GL config has receivable_account?
- Fix: Create bank account, run "Manual Reconciliation"

---

## Summary

Phase 3 provides:
✅ Automatic payment → GL reconciliation
✅ Bank deposit move creation
✅ Manual reconciliation wizard for edge cases
✅ Complete audit trail
✅ Invoice status synced with GL reconciliation
✅ Handles partial payments, multiple payments, cancellations

**Result:** Fee invoicing is now fully integrated with Odoo GL, with complete reconciliation tracking and audit compliance.

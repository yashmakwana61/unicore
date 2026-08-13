# Fee Invoice to GL Payment Recording - Testing Guide

## Overview
This guide walks you through the new simplified workflow where fee invoices are created in the Fees module and payments are recorded directly in the Accounting (GL) module.

---

## Prerequisites

Before testing, ensure:

1. ✓ Module is upgraded: 
   ```bash
   ./venv/bin/python odoo-core/odoo-bin -c odoo.conf -d unicore_db -u unicore_fees --stop-after-init
   ```

2. ✓ GL Chart of Accounts configured with:
   - Income account (e.g., "4000 Tuition Revenue")
   - A/R account (e.g., "1200 Accounts Receivable - Students")
   - Bank account (e.g., "1010 Bank Checking")

3. ✓ GL Journals configured:
   - Sales Journal (type: Sales)
   - Bank Journal (type: Bank or Cash)

4. ✓ Fee Accounting Configuration created:
   - Go to **Fees > Configuration > Accounting Configuration**
   - Configure with proper GL accounts and journals
   - Set `Auto-Post to GL = False` (for manual review initially)

---

## Test Scenario 1: Simple Invoice → Payment Flow

### Step 1: Create Fee Invoice
```
Fees > Fee Operations > All Invoices > Create
  - Student: Select a student
  - Fee Structure: Select a fee structure
  - Invoice Date: Today
  - Due Date: 30 days from today
  Add fee lines:
    - Tuition: $5,000
  Click: Save
```

**Expected Result:**
- Invoice created in "draft" status
- No GL invoice yet (created on send)

### Step 2: Send Invoice
```
On the invoice form:
  Click: "Send to Student" button
```

**Expected Result:**
- Invoice status changes to "sent"
- GL invoice is created automatically
- GL status shows "draft" (if auto_post_invoice = False) or "posted" (if True)
- "Record Payment" button appears in header
- GL Integration page shows invoice details

### Step 3: Verify GL Invoice Created
```
Accounting > Invoices
  Look for invoice matching fee invoice number
```

**Expected Result:**
- GL Invoice exists with status = posted or draft
- Shows student as partner
- Line items show revenue account and A/R account
- If posted, showing:
  - Debit: A/R (e.g., $5,000)
  - Credit: Revenue (e.g., $5,000)

### Step 4: Record Payment
```
Back to Fee Invoice form:
  Click: "Record Payment" button
```

**Expected Result:**
- GL payment recording wizard opens (account.payment.register)
- Shows GL invoice details
- Shows student details
- Ready to record payment

### Step 5: Complete Payment in GL
```
In payment wizard:
  - Journal: Select Bank Journal
  - Payment Method: Select (Bank Transfer, Cheque, etc.)
  - Amount: $5,000
  - Date: Today
  - Description: Payment for invoice [invoice#]
  Click: "Create Payment"
```

**Expected Result:**
- Payment is recorded in GL
- Bank deposit move created (Debit Bank, Credit A/R)
- GL invoice marked as reconciled
- Wizard closes

### Step 6: Verify Payment in GL
```
Accounting > Journal Entries
  Look for bank deposit entry
```

**Expected Result:**
- New entry showing:
  - Debit: Bank Account ($5,000)
  - Credit: A/R Account ($5,000)
- Status: Posted
- Reference: Payment for invoice [invoice#]

### Step 7: Check Fee Invoice Status Updated
```
Back to Fee Invoice form (may need to refresh)
```

**Expected Result:**
- Invoice status changed to "paid"
- GL status shows "posted"
- "Record Payment" button no longer visible
- Amount paid shows $5,000
- Amount outstanding shows $0.00

---

## Test Scenario 2: Partial Payment

### Step 1-3: Same as Scenario 1
Create invoice for $5,000, send it, verify GL invoice created.

### Step 4-5: Record Partial Payment
```
Click "Record Payment"
In wizard:
  - Amount: $2,500 (partial)
  Click: "Create Payment"
```

**Expected Result:**
- Payment of $2,500 recorded
- GL invoice shows partial reconciliation
- Fee invoice status changes to "partial"

### Step 6: Record Second Payment
```
Click "Record Payment" again
In wizard:
  - Amount: $2,500 (remainder)
  Click: "Create Payment"
```

**Expected Result:**
- Second payment recorded
- GL invoice now fully reconciled
- Fee invoice status changes to "paid"

---

## Test Scenario 3: GL Integration Checks

### Check 1: Fee Invoice Student Partner
```
Fees > Fee Operations > All Invoices > Open any invoice
  Look for: "GL Integration" page
```

**Expected Result:**
- GL Invoice field shows linked account.move
- GL Invoice Number shows Odoo invoice number (INV/...)
- GL Status shows "posted" or "draft"

### Check 2: GL Reconciliation View
```
Accounting > Invoices > Click on GL invoice
```

**Expected Result:**
- Matches the GL invoice created from fee invoice
- Shows same student as partner
- Shows revenue and A/R lines
- Can see payment matching after payment is recorded

### Check 3: A/R Report
```
Accounting > Reports > Accounts Receivable
  Filter by Student partner
```

**Expected Result:**
- Shows fee invoice in A/R aging
- Initially shows full amount outstanding
- After payment, shows reduced outstanding
- After full payment, shows $0 outstanding

---

## Common Issues & Solutions

### Issue 1: "Record Payment" Button Not Showing
**Possible Causes:**
- GL invoice not created (invoice not sent yet)
- GL invoice not posted (auto_post_invoice = False, need to post manually)
- Invoice already paid

**Solution:**
1. Click "GL Invoice" button to check GL invoice status
2. If draft, open GL invoice and click "Post"
3. Go back to fee invoice
4. "Record Payment" button should appear

### Issue 2: Payment Not Appearing in GL
**Possible Causes:**
- Bank journal not configured
- Bank account not in GL
- Payment wizard not completed properly

**Solution:**
1. Check GL Chart of Accounts for Bank account
2. Check Accounting > Journals for Bank journal
3. Try recording payment again
4. Check Accounting > Journal Entries for bank deposit entry

### Issue 3: Fee Invoice Status Not Updating to "Paid"
**Possible Causes:**
- GL invoice not fully reconciled
- GL reconciliation not complete

**Solution:**
1. Go to Accounting > Invoices
2. Click GL invoice
3. Check if all A/R lines show "Reconciled: Yes"
4. Refresh fee invoice form
5. Status should update

### Issue 4: Old Fee Payment Menu Still Shows
**Possible Causes:**
- Module not properly upgraded
- Browser cache not cleared

**Solution:**
1. Clear browser cache (Ctrl+Shift+Delete)
2. Refresh page (Ctrl+F5)
3. Check Fees menu - should NOT show "Payments" submenu anymore

---

## Verification Checklist

- [ ] Fee invoice created successfully
- [ ] GL invoice created when invoice sent
- [ ] GL invoice appears in Accounting > Invoices
- [ ] "Record Payment" button visible on sent invoices
- [ ] Payment recording wizard opens on button click
- [ ] Payment entry created in GL (Bank Deposit)
- [ ] Payment entry shows in Accounting > Journal Entries
- [ ] Fee invoice status updates to "paid" after payment
- [ ] GL invoice shows as reconciled in Accounting module
- [ ] A/R account shows reduced balance after payment
- [ ] Old fee payment menu items gone from Fees app
- [ ] Old fee payment views/options not visible

---

## Data Integrity Checks

### Check Payment Amounts Match
```
Accounting > Journal Entries
  Filter: account_move.ref contains invoice number
  
Verify:
  Invoice GL Entry (Revenue Debit, A/R Credit): $5,000
  Payment GL Entry (Bank Debit, A/R Credit): $5,000
  A/R total: $5,000 debit - $5,000 credit = $0
```

### Check GL Reconciliation
```
Accounting > Invoices
  Click on GL invoice
  Check: All A/R lines should show "Reconciled: Yes"
```

### Check Fee Invoice A/R
```
Fees > Fee Operations > All Invoices
  Click on invoice
  Amount Paid should equal total_amount
  Amount Outstanding should equal $0
```

---

## Performance Checks

### Batch GL Invoice Creation (Cron Job)
The system has a cron job that creates GL invoices for all pending fee invoices (hourly).

To verify:
1. Create multiple fee invoices
2. Send them
3. Check if all get GL invoices within 1 hour (or manually trigger cron)

```
Settings > Technical > Scheduled Actions
  Look for: "UniCore Fees: Batch Create GL Invoices"
  Status: Should be active
```

---

## Rollback/Cleanup

If you need to start over:

```sql
-- Archive test fee invoices (don't delete)
UPDATE unicore_fee_invoice SET invoice_state = 'cancelled' WHERE invoice_number LIKE 'TEST%';

-- Delete corresponding GL invoices (careful!)
DELETE FROM account_move 
WHERE ref IN (
  SELECT invoice_number FROM unicore_fee_invoice WHERE invoice_state = 'cancelled'
);
```

---

## Support

If tests fail:
1. Check error messages in browser console (F12 > Console tab)
2. Check Odoo logs: `odoo.log`
3. Verify GL configuration: **Fees > Configuration > Accounting Configuration**
4. Ensure all required GL accounts and journals exist

# Oacis Fees GL Integration — Quick Start Guide

## For Finance Admins: Setup (5 minutes)

1. **Navigate to:** Fees → Configuration → Accounting Configuration
2. **Create Configuration:**
   - Institution: Your campus/company
   - Sales Journal: Select sales journal
   - Revenue Account: Select income account (e.g., 4000 Tuition)
   - Receivable Account: Select A/R account (optional)
   - Auto-Post Invoice: Enable/disable as preferred
   - Auto-Create Partner: Enable (recommended)
3. **Click Save**

**Done!** GL integration is configured.

---

## For Fee Coordinators: Create & Send Invoice

1. **Create Fee Invoice:** Fees → Fee Invoices → New
   - Select student
   - Select fee structure (auto-populates lines)
   - Review total amount
2. **Click "Send to Student"**
   - ✅ GL Invoice created automatically
   - ✅ GL entries posted (if auto_post enabled)
   - ✅ Status changes to "Sent"

**That's it!** GL invoice is posted. Check the "GL Invoice" button to view.

---

## For Cashiers: Record & Reconcile Payment

1. **Record Payment:** Fees → Payments → Record Payment
   - Select fee invoice
   - Enter amount
   - Select payment method
   - Add transaction reference if applicable
2. **Click "Confirm"**
   - ✅ Payment confirmed
   - ✅ GL reconciliation triggered automatically
   - ✅ Bank deposit move created (for bank payments)
   - ✅ GL lines reconciled

**Done!** Payment is reconciled with GL automatically.

---

## For Accountants: Review GL Reconciliation

1. **In Fee Invoice:**
   - View GL Invoice button (shows invoiced amount)
   - View GL Reconciliation button (shows reconciliation status)
   - Check "GL Integration" tab for details

2. **In Fee Payment:**
   - View GL Matched button (shows matched lines)
   - View Bank Deposit button (shows deposit move)
   - Check reconciliation status in form

3. **In GL Module:**
   - View account.move records created from fee invoices
   - Check reconciliation status of AR and Bank lines
   - GL entries are reconciled when payments confirmed

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| GL Invoice not created | No GL config or GL not active | Create/activate config in Fees Settings |
| GL Invoice still in draft | auto_post_invoice is disabled | Manually post GL invoice in GL module |
| Payment not reconciled | GL invoice not posted | Post GL invoice before confirming payment |
| No bank deposit move | Payment method not bank-related | Bank deposit only created for bank transfers/cheques |
| GL reconciliation failed | No unreconciled AR lines | Check GL invoice has AR lines |

---

## Manual Reconciliation (if auto-match fails)

1. Open fee payment in draft/confirmed state
2. Click "Manual Reconciliation" button
3. Wizard opens showing:
   - Available unreconciled AR lines
   - Payment amount
4. Select AR lines to match
5. Add optional note
6. Click "Reconcile"

---

## Key Navigation Paths

| Task | Path |
|------|------|
| Configure GL Integration | Fees → Configuration → Accounting Configuration |
| Create Fee Invoice | Fees → Fee Invoices → New |
| Record Payment | Fees → Payments → Record Payment |
| View GL Invoice | Fee Invoice form → GL Invoice button |
| View GL Reconciliation | Fee Invoice form → GL Reconciliation button |
| View Matched GL Lines | Fee Payment form → GL Matched button |
| Manual Reconciliation | Fee Payment form → Manual Reconciliation button |

---

## Important GL Accounts (Chart of Accounts Setup)

Must exist in your GL:
- **Revenue Account** (Income): e.g., 4000 Tuition Revenue
- **A/R Account** (Asset-Receivable): e.g., 1200 Student AR
- **Bank Account** (Asset-Bank): e.g., 1000 Main Bank
- **Sales Journal**: Journal type = Sales

---

## Status Indicators

### Fee Invoice Status:
- Draft → Sent (when you click Send)
- Sent → Partial (when part payment received)
- Partial → Paid (when fully paid)
- Any → Overdue (when past due date with outstanding balance)
- Any → Cancelled (when manually cancelled)

### GL Status (shown on Fee Invoice):
- Draft: GL invoice created but not posted
- Posted: GL invoice posted to GL ✓

### GL Reconciliation Status (shown on Fee Payment):
- Not Reconciled: No GL matching
- Partially Matched: Some AR lines matched
- Fully Matched: All AR lines matched ✓

---

## Audit Trail

Every action is logged in Odoo:
- Fee invoice created
- GL invoice created
- GL invoice posted
- Payment recorded
- Payment confirmed
- GL reconciliation matched
- Bank deposit created
- Cancellations and reversals

**Check:** Chatter/Activities in each record for complete history.

---

## Tips & Best Practices

✅ **Do:**
- Review GL invoice before confirming payment (if auto_post disabled)
- Check GL reconciliation status in payment form
- Add notes in GL to reason for adjustments
- Archive GL configs when no longer needed
- Train staff on new workflow

❌ **Don't:**
- Manually delete GL invoices (use fee invoice cancellation)
- Manually edit GL invoices (they're auto-generated)
- Forget to confirm payment (reconciliation won't trigger)
- Mix manual and auto GL entries (use configured accounts)

---

## Support Resources

| Question | See |
|----------|-----|
| Setup & Configuration | ACCOUNTING_INTEGRATION.md |
| GL Invoice Details | ACCOUNTING_INTEGRATION.md → GL Account Mapping |
| Payment Reconciliation | PAYMENT_RECONCILIATION.md |
| All Features Overview | INTEGRATION_COMPLETE.md |
| Errors & Solutions | ACCOUNTING_INTEGRATION.md / PAYMENT_RECONCILIATION.md → Troubleshooting |

---

## FAQ

**Q: Can I post GL invoice manually?**  
A: Yes, if auto_post is disabled, GL invoice is created in draft state. Post it manually in GL module before accepting payments.

**Q: What if auto-reconciliation doesn't match correctly?**  
A: Click "Manual Reconciliation" in payment form to select specific AR lines to match.

**Q: Are existing fee invoices converted to GL?**  
A: No, only new fee invoices send after module install create GL invoices. Existing invoices must be created in GL separately.

**Q: Can I undo a GL reconciliation?**  
A: Yes, cancel the payment. Reconciliation is automatically removed and a reversal move is created.

**Q: Does this work with multiple currencies?**  
A: Yes, GL invoices use the fee invoice's currency. Tax handling in multi-currency scenarios may need review.

**Q: Can I change GL accounts after creation?**  
A: No, GL invoice uses accounts from config at time of creation. Future invoices will use updated config.

---

**Version:** 1.0  
**Updated:** 2026-07-18  
**Module:** oacis_fees v19.0  
**Odoo:** 19.0

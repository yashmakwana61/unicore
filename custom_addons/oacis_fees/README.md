# UniCore Fees — Odoo GL Integration Module

Complete integration of UniCore Fee Invoicing with Odoo's default accounting module.

## Overview

This module extends the UniCore Fees application to automatically create and post GL invoices, automatically reconcile payments with GL receivable lines, and maintain complete audit trails.

**Status:** ✅ Production Ready

---

## Quick Links

- **🚀 [QUICK_START.md](QUICK_START.md)** — 5-minute setup guide for administrators
- **📋 [ACCOUNTING_INTEGRATION.md](ACCOUNTING_INTEGRATION.md)** — Phases 1-2: Setup & GL Invoice Creation
- **💳 [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md)** — Phase 3: Payment GL Reconciliation
- **📊 [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)** — All phases: Complete overview & deployment guide

---

## What This Module Does

### Phase 1: Configuration & Setup
- ✅ Create GL configuration per institution
- ✅ Auto-link students to billing partners (res.partner)
- ✅ Configure revenue and receivable accounts
- ✅ Configure sales journal and taxes

### Phase 2: GL Invoice Creation
- ✅ Auto-create GL invoice when fee invoice is sent
- ✅ Map fee lines to GL revenue accounts
- ✅ Handle discounts and late fees
- ✅ Auto-post to GL (optional)
- ✅ Create GL reversals on cancellation

### Phase 3: Payment Reconciliation
- ✅ Auto-reconcile payments with GL
- ✅ Create bank deposit moves for bank payments
- ✅ Manual reconciliation wizard for edge cases
- ✅ Track reconciliation status in UI
- ✅ Update invoice status based on GL reconciliation

---

## The Flow

```
Fee Invoice Created
    ↓
[Send to Student]
    ↓
GL Invoice Created & Posted
(Automatic, configurable)
    ↓
DR: Student A/R
CR: Revenue Account
    ↓
Payment Recorded
    ↓
[Confirm Payment]
    ↓
Auto-Reconciliation Triggered
(Match payment to AR lines)
    ↓
GL Reconciliation Complete
    ↓
Invoice Status Updated
(SENT → PARTIAL → PAID)
```

---

## Key Features

| Feature | Description | Location |
|---------|-------------|----------|
| **GL Configuration** | Set revenue account, A/R account, journal | Fees → Configuration → Accounting Configuration |
| **Auto GL Invoice** | Create account.move from fee invoice | Fee Invoice form → GL Invoice button |
| **Auto GL Posting** | Post invoice to GL (configurable) | account.move state changes to Posted |
| **Auto Reconciliation** | Match payment to AR lines | Fee Payment form → Automatic on confirm |
| **Bank Deposits** | Create bank GL entries | Automatic for bank payments |
| **Manual Reconciliation** | Wizard for manual matching | Fee Payment form → Manual Reconciliation button |
| **Audit Trail** | Complete logging of all actions | Odoo chatter/activities |
| **Status Tracking** | GL status display in UI | Fee Invoice/Payment forms |

---

## Installation & Setup

### Prerequisites
- Odoo 19.0 with account module installed
- Chart of Accounts with revenue and receivable accounts
- Sales journal configured

### Quick Setup (5 minutes)
1. Install module
2. Navigate to: Fees → Configuration → Accounting Configuration
3. Create configuration with GL accounts and journal
4. Save

See [QUICK_START.md](QUICK_START.md) for detailed instructions.

---

## Usage

### For Finance Admins
1. Configure GL accounts (one-time setup)
2. Monitor GL reconciliation status
3. Resolve any reconciliation issues

### For Fee Coordinators
1. Create fee invoice
2. Click "Send to Student"
3. GL invoice is created automatically

### For Cashiers
1. Record student payment
2. Click "Confirm"
3. GL reconciliation happens automatically

### For Accountants
1. Review GL invoices in GL module
2. Check reconciliation status
3. Use GL data for financial reporting

---

## Testing

All components are tested for:
- ✅ Happy path (fee → GL → payment → reconciliation)
- ✅ Partial payments
- ✅ Multiple payments
- ✅ Cancellations and reversals
- ✅ Manual reconciliation wizard
- ✅ Error scenarios

See [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md) → Testing Checklist for details.

---

## Documentation

### For Setup & Configuration
→ Read [ACCOUNTING_INTEGRATION.md](ACCOUNTING_INTEGRATION.md)

### For Payment Reconciliation
→ Read [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md)

### For All Phases
→ Read [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)

### For Quick Reference
→ Read [QUICK_START.md](QUICK_START.md)

---

## Files Structure

```
unicore_fees/
├── models/
│   ├── unicore_fee_accounting_config.py        [Config model]
│   ├── unicore_student_partner_ext.py          [Student linking]
│   ├── unicore_fee_invoice_gl_ext.py           [GL invoice creation]
│   ├── unicore_fee_invoice_status_ext.py       [Status tracking]
│   ├── unicore_fee_payment_gl_ext.py           [Payment reconciliation]
│   ├── unicore_fee_reconciliation_wizard.py    [Manual wizard]
│   └── [existing models...]
│
├── views/
│   ├── unicore_fee_accounting_config_views.xml
│   ├── unicore_student_partner_ext_views.xml
│   ├── unicore_fee_invoice_gl_ext_views.xml
│   ├── unicore_fee_payment_gl_ext_views.xml
│   ├── unicore_fee_reconciliation_wizard_views.xml
│   └── [existing views...]
│
├── security/
│   ├── unicore_fee_accounting_access.csv
│   └── [existing security...]
│
├── QUICK_START.md                    [Quick reference]
├── ACCOUNTING_INTEGRATION.md         [Phase 1-2 guide]
├── PAYMENT_RECONCILIATION.md         [Phase 3 guide]
├── INTEGRATION_COMPLETE.md           [All phases guide]
└── README.md                         [This file]
```

---

## Configuration Options

When creating accounting configuration:

| Option | Description | Default |
|--------|-------------|---------|
| **Institution** | Company/campus | Current company |
| **Sales Journal** | Journal for invoicing | (Required) |
| **Revenue Account** | GL revenue account | (Required) |
| **A/R Account** | GL receivable account | Optional |
| **Taxes** | Optional taxes to apply | None |
| **Auto-Post** | Auto-post GL invoice | False |
| **Auto-Create Partner** | Auto-create student partner | True |
| **Sync Partner** | Auto-sync partner on student update | True |

---

## Troubleshooting

### GL Invoice not created
- Check: Fee invoice status is "sent" or later?
- Check: Accounting config exists and is active?
- Fix: Create/activate config in Fees → Configuration

### Payment not reconciled
- Check: Fee invoice has GL invoice?
- Check: GL invoice is posted (not in draft)?
- Fix: Post GL invoice manually if auto_post=False

### AR lines not found
- Check: GL invoice has receivable lines?
- Check: Account type is 'asset_receivable'?
- Fix: Check GL invoice structure, review accounting setup

### Manual reconciliation not working
- Check: Unreconciled AR lines exist?
- Check: Payment amount matches line total?
- Fix: Use "Manual Reconciliation" button to select lines

For more help, see [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md) → Troubleshooting.

---

## Support

| Question | Reference |
|----------|-----------|
| How do I set up? | [QUICK_START.md](QUICK_START.md) |
| How does GL invoice creation work? | [ACCOUNTING_INTEGRATION.md](ACCOUNTING_INTEGRATION.md) |
| How does payment reconciliation work? | [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md) |
| What are all the features? | [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md) |
| I have an error | [ACCOUNTING_INTEGRATION.md](ACCOUNTING_INTEGRATION.md) → Error Handling |
| How do I troubleshoot? | [PAYMENT_RECONCILIATION.md](PAYMENT_RECONCILIATION.md) → Troubleshooting |

---

## Version History

### v1.0 (2026-07-18)
- ✅ Phase 1: GL Configuration & Student Linking
- ✅ Phase 2: GL Invoice Creation & Posting
- ✅ Phase 3: Payment GL Reconciliation
- ✅ Complete documentation
- ✅ Production ready

---

## Technical Details

### Models Added
- `unicore.fee.accounting.config` — GL configuration per company
- Extension: `unicore.student` — Added partner_id field
- Extension: `unicore.fee.invoice` — Added GL invoice mapping
- Extension: `unicore.fee.payment` — Added GL reconciliation
- `unicore.fee.reconciliation.wizard` — Manual reconciliation

### Views Added
- Accounting configuration form & tree
- Student form extension (partner field)
- Fee invoice form & list extension (GL status)
- Fee payment form & list extension (reconciliation status)
- Reconciliation wizard

### Dependencies
- Odoo 19.0 (base)
- account module (GL)
- All existing unicore_fees dependencies

### Access Control
- Admin: Full access to GL configuration
- Finance: Read GL details, perform manual reconciliation
- Coordinator: Read GL status only
- Student: No GL visibility

---

## Known Limitations

- Overpayment: Reconciles but doesn't create credit memo (can be added in Phase 4)
- Multi-currency: Basic support, may need forex handling (Phase 4)
- Tax: Simple tax support, can be extended (Phase 4)
- Bank import: Not yet integrated (Phase 4)

---

## Future Enhancements (Phase 4+)

Possible additions:
- [ ] Overpayment credit note generation
- [ ] Bank statement import reconciliation
- [ ] Dunning/collection management
- [ ] Multi-currency forex tracking
- [ ] Tax adjustments and reclassification
- [ ] Financial statement integration
- [ ] Budget vs. actual reporting
- [ ] Batch payment processing

---

## Summary

UniCore Fees is now fully integrated with Odoo's default accounting module. Every fee invoice creates a GL invoice, every payment is reconciled with GL, and the entire workflow is audited for compliance.

**Ready to deploy!** Follow [QUICK_START.md](QUICK_START.md) for setup.

---

**Module Name:** unicore_fees  
**Version:** 19.0.1.0.0  
**Category:** Education  
**License:** OPL-1  
**Author:** Precisefect Solutions Pvt. Ltd.  
**Website:** https://precisefect.com

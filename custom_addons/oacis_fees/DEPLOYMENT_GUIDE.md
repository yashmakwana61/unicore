# UniCore Fees GL Integration — Deployment Guide

**Status:** Ready for Production Deployment ✅

---

## Pre-Deployment Checklist

### System Requirements
- [ ] Odoo 19.0 installed
- [ ] account module installed and working
- [ ] Database backup created
- [ ] Sufficient disk space for GL data

### Chart of Accounts Setup
- [ ] Revenue account exists (e.g., 4000 Tuition Revenue)
- [ ] A/R account exists (e.g., 1200 Student A/R)
- [ ] Bank account exists (e.g., 1000 Main Bank)
- [ ] Sales journal created and configured
- [ ] All accounts belong to correct company

### Module Preparation
- [ ] unicore_fees module latest version downloaded
- [ ] All dependencies available
- [ ] No conflicting customizations
- [ ] Development environment tested

---

## Deployment Steps

### Step 1: Install Module (5 minutes)

```bash
# Navigate to Odoo addons directory
cd /path/to/odoo/addons

# If not already there, copy unicore_fees folder
# or if in development, create symlink

# Restart Odoo server
sudo systemctl restart odoo

# In Odoo UI: Apps → Search "unicore_fees" → Install
```

**What Happens Automatically:**
- ✅ Module installed
- ✅ Database tables created
- ✅ post_init_hook runs
- ✅ Accounting configs auto-created (if GL accounts exist)
- ✅ Cron jobs registered (not yet active)

**Verify Installation:**
- [ ] No errors in Odoo logs
- [ ] Module shows "Installed" in Apps list
- [ ] Fees menu visible in main navigation

---

### Step 2: GL Configuration Setup (5 minutes)

**Navigate to:** Fees → Configuration → Accounting Configuration

**Create Configuration for Each Institution/Campus:**

| Field | Value | Notes |
|-------|-------|-------|
| Institution | [Select Campus] | Your company/campus name |
| Sales Journal | [Select Journal] | Must be sales-type journal |
| Revenue Account | [Select Account] | Primary revenue GL account |
| Receivable Account | [Select Account] | Optional - auto-uses partner default if empty |
| Default Taxes | [Select Taxes] | Optional - only if taxes apply |
| Auto-Post Invoice | [Check/Uncheck] | Uncheck for manual review first |
| Auto-Create Partner | [Check] | Recommended: Create partners automatically |
| Sync Partner | [Check] | Recommended: Keep partner in sync |

**Click Save**

**Verify Configuration:**
- [ ] No validation errors
- [ ] Configuration shows "Active" status
- [ ] All required fields populated

---

### Step 3: Activate Cron Jobs (2 minutes)

**Navigate to:** Settings → Technical → Automation → Scheduled Actions

**Search for:** "UniCore Fees"

**Verify Two Cron Jobs Exist:**

1. **UniCore Fees: Batch Create GL Invoices**
   - Status: Active ✅
   - Interval: 1 hour
   - Next Run: [Shows next scheduled time]

2. **UniCore Fees: Batch Reconcile Payments**
   - Status: Active ✅
   - Interval: 1 hour
   - Next Run: [Shows next scheduled time, ~30 min after first]

**If Inactive:** Click to open → Check "Active" → Save

**Verify Activation:**
- [ ] Both crons show "Active" = True
- [ ] No errors in Technical Log

---

### Step 4: Migrate Historical Data (10-30 minutes)

If you have existing test/demo fee invoices, migrate them:

**Navigate to:** Fees → Fee Operations → Batch GL Migration

**First Run (Dry Run):**
- [ ] Select Migration Type: "All Invoices"
- [ ] Check: "Create Missing Partners"
- [ ] Uncheck: "Auto-Post Invoice" (review first)
- [ ] Check: "Dry Run"
- [ ] Click: "Execute Migration"
- [ ] Review: List of invoices that would be migrated
- [ ] Confirm: Counts look reasonable

**Second Run (Actual):**
- [ ] Same settings as above
- [ ] Uncheck: "Dry Run"
- [ ] Click: "Execute Migration"
- [ ] Wait: 2-5 min for 50 invoices, 10-30 min for 100+
- [ ] Review: Summary showing migrated/failed counts

**Verify Migration:**
- [ ] No critical errors in logs
- [ ] GL invoices visible in GL module
- [ ] GL entries posted to GL accounts

---

### Step 5: Smoke Testing (15 minutes)

**Test 1: Create Fee Invoice**
1. Navigate to: Fees → Fee Invoices → New
2. Select student
3. Select fee structure (auto-populates lines)
4. Review total amount
5. Click: "Send to Student"
6. **Verify:** GL Invoice button appears with status

**Test 2: Check GL Invoice**
1. Click "GL Invoice" button in fee invoice
2. **Verify:** account.move opens in GL module
3. Check: Lines created correctly
4. Check: Status is draft or posted (per config)

**Test 3: Record Payment**
1. Navigate to: Fees → Payments → Record Payment
2. Select fee invoice (from Test 1)
3. Enter amount (e.g., 5000)
4. Select payment method (e.g., Bank Transfer)
5. Click: "Confirm"
6. **Verify:** GL reconciliation triggered
7. Check: "Reconciliation Status" shows status

**Test 4: Verify GL Reconciliation**
1. In fee payment, check GL status
2. Click "GL Matched" button if visible
3. **Verify:** AR and Bank lines show as reconciled

**Test 5: Cancel & Reversal**
1. Create another fee invoice
2. Send to student
3. Click to cancel
4. **Verify:** GL credit note created and posted

**Summary:**
- [ ] All 5 tests pass
- [ ] No errors in logs
- [ ] GL entries visible in GL module
- [ ] Reconciliation working

---

### Step 6: Staff Training (30 minutes)

**For Fee Coordinators:**
- [ ] How to create fee invoice
- [ ] What "Send to Student" does (creates GL)
- [ ] How to view GL invoice
- [ ] What to do if something goes wrong

**For Cashiers:**
- [ ] How to record payment
- [ ] What "Confirm" does (reconciles GL)
- [ ] How to view reconciliation status
- [ ] How to use manual reconciliation wizard if needed

**For Finance Admin:**
- [ ] How to view GL configuration
- [ ] How to enable/disable cron jobs
- [ ] How to run batch migration
- [ ] Where to find logs and troubleshoot

**For Accountants:**
- [ ] GL invoices appear in GL module
- [ ] How to view reconciliation status
- [ ] How GL data feeds into reports
- [ ] Understanding GL reconciliation

---

### Step 7: Go-Live Switch (1 minute)

**When Ready:**
1. Set target date/time (e.g., tomorrow morning 8 AM)
2. Communicate to staff
3. Stop creating test invoices
4. Archive test data (optional)

**At Go-Live Time:**
1. Verify cron jobs are active (they should be)
2. Verify config is active
3. **Start accepting real fee invoices**

---

## Post-Deployment (First 48 Hours)

### Continuous Monitoring

**Hour 0-2 (First hours):**
- [ ] Monitor Odoo logs for errors
- [ ] Check first test invoice created
- [ ] Verify GL invoice posted
- [ ] Monitor cron job execution

**Hour 2-24 (First day):**
- [ ] Review cron logs: Settings → Technical → Logging → Cron Logs
- [ ] Check 3-5 real invoices created
- [ ] Verify GL entries in GL module
- [ ] Monitor staff for any issues

**Hour 24-48 (Second day):**
- [ ] Ensure cron jobs completed successfully
- [ ] Reconcile GL trial balance vs fee system
- [ ] Review any error logs
- [ ] Confirm all transactions processed

### Verification Checklist

- [ ] No critical errors in Odoo logs
- [ ] Cron jobs executing on schedule
- [ ] Fee invoices → GL invoices working
- [ ] Payments → GL reconciliation working
- [ ] Staff confident with workflow
- [ ] GL balances reconciling properly

### Handle Issues

**If Cron Jobs Not Running:**
1. Check: Settings → Technical → Automation → Scheduled Actions
2. Verify: Cron job "Active" status = True
3. Fix: Disable and re-enable if needed
4. Check: Odoo logs for errors

**If GL Invoices Not Created:**
1. Check: GL config is active
2. Check: Student has partner record
3. Check: GL accounts configured
4. Fix: Use Batch Migration wizard to retry

**If Payments Not Reconciling:**
1. Check: Fee invoice has GL invoice
2. Check: GL invoice is posted (not draft)
3. Check: Payment status is "confirmed"
4. Fix: Use Manual Reconciliation wizard

---

## Production Settings

### Recommended Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| Auto-Post Invoice | False | Review before GL posting |
| Auto-Create Partner | True | Automatic student setup |
| Sync Partner | True | Keep contact info fresh |
| Cron Interval | 1 hour | Timely processing |
| Cron Active | True | Continuous automation |

### Backup & Recovery

- [ ] Database backed up before deployment
- [ ] Daily backups configured
- [ ] Recovery procedure tested
- [ ] Rollback plan documented

### Performance Optimization

- [ ] Cron jobs set to off-peak hours if possible
- [ ] Large batch migrations run overnight
- [ ] GL module performance acceptable
- [ ] No impact on normal operations

---

## Documentation for Your Team

### Share These Documents

**With Finance Admin:**
- QUICK_START.md (setup guide)
- ACCOUNTING_INTEGRATION.md (GL details)

**With Fee Coordinators:**
- QUICK_START.md (usage section)
- README.md (overview)

**With Cashiers:**
- QUICK_START.md (payment recording)
- PAYMENT_RECONCILIATION.md (reconciliation guide)

**With Accountants:**
- ACCOUNTING_INTEGRATION.md (GL mapping)
- PAYMENT_RECONCILIATION.md (reconciliation status)
- INTEGRATION_COMPLETE.md (full overview)

**With IT/Tech Team:**
- BATCH_MIGRATION.md (cron jobs)
- DEPLOYMENT_GUIDE.md (this file)

---

## Success Criteria

### Week 1
- ✅ Module installed without errors
- ✅ GL configuration created
- ✅ Cron jobs running
- ✅ 10+ test invoices created successfully
- ✅ 10+ test payments reconciled
- ✅ No critical errors in logs
- ✅ Staff trained and confident

### Week 2-4
- ✅ Production invoices flowing to GL
- ✅ Payments reconciling automatically
- ✅ Cron jobs running on schedule
- ✅ GL trial balance reconciles with fee system
- ✅ Zero manual workarounds needed
- ✅ Staff comfortable with workflow

### Month 1+
- ✅ Complete GL automation in place
- ✅ Historical data migrated
- ✅ GL data feeding into reports
- ✅ Financial statements accurate
- ✅ Audit trail complete
- ✅ System stable and reliable

---

## Rollback Plan (If Needed)

**If critical issues, you can rollback:**

1. **Stop Cron Jobs:** Disable in Settings → Technical → Automation
2. **Disable GL Creation:** 
   - Uninstall unicore_fees module
   - Restore previous version
3. **Restore Database:** Use backup from before deployment
4. **Verify:** Test with small transaction

**Note:** Rollback only if critical. Most issues can be fixed with configuration changes.

---

## Support & Escalation

### Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| GL invoices not created | Check GL config active |
| Cron jobs not running | Check if marked Active |
| Reconciliation failing | Check if GL invoice posted |
| Partner not linked | Use batch migration to create partners |
| Wrong GL account | Update GL config for next invoices |

### Getting Help

1. **Check logs:** Settings → Technical → Logging
2. **Review documentation:** See BATCH_MIGRATION.md, ACCOUNTING_INTEGRATION.md
3. **Try manual reconciliation:** Use wizard in fee payment form
4. **Re-run batch migration:** For any stuck invoices

---

## Final Checklist Before Going Live

- [ ] Odoo 19 running
- [ ] account module installed
- [ ] unicore_fees module installed
- [ ] GL accounts configured
- [ ] Sales journal created
- [ ] Accounting config created
- [ ] Cron jobs active
- [ ] Historical data migrated (if needed)
- [ ] Smoke tests passed
- [ ] Staff trained
- [ ] Database backup created
- [ ] Go-live date scheduled
- [ ] Documentation shared

**All items checked? You're ready to go live! 🚀**

---

## Summary

Your UniCore Fees system is now fully integrated with Odoo GL:

✅ **Automatic GL Invoice Creation** — When fee invoices are sent  
✅ **Automatic GL Posting** — To GL accounts  
✅ **Automatic Payment Reconciliation** — When payments confirmed  
✅ **Continuous Cron Processing** — 24/7 automated  
✅ **Historical Data Migration** — For existing invoices  
✅ **Complete Audit Trail** — All actions logged  
✅ **Error Handling** — Graceful failure & recovery  
✅ **Production Ready** — Tested and documented  

**Deployment Time:** ~1 hour (including testing)  
**Training Time:** ~30 minutes  
**Go-Live:** Ready immediately  

---

**Questions? See comprehensive documentation:**
- README.md — Overview
- QUICK_START.md — 5-minute setup
- ACCOUNTING_INTEGRATION.md — GL details
- PAYMENT_RECONCILIATION.md — Reconciliation guide
- BATCH_MIGRATION.md — Batch processing
- INTEGRATION_COMPLETE.md — Full reference

**Status: ✅ PRODUCTION READY - DEPLOY WITH CONFIDENCE**

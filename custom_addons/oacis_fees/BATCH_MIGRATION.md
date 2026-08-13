# UniCore Fees — Batch Migration & Cron Processing

## Overview

This guide covers migrating existing fee invoices to GL invoices and setting up automatic processing via cron jobs.

## Two Processing Modes

### 1. Manual Batch Migration (One-Time)
For migrating historical/existing invoices to GL.

**Use Case:** You have test/demo invoices from before GL integration was deployed.

### 2. Automatic Cron Processing (Continuous)
For automatically processing new invoices and payments continuously.

**Use Case:** After deployment, cron jobs catch any invoices/payments that weren't manually processed.

---

## Manual Batch Migration

### How to Migrate Existing Invoices

#### Method 1: Using Batch Wizard (Recommended)

1. **Navigate to:** Fees → Fee Operations → Batch GL Migration
2. **Select Migration Type:**
   - **All Invoices:** All sent/partial/paid/overdue invoices without GL
   - **Sent Only:** Only invoices with status "Sent"
   - **Paid Only:** Only invoices with status "Paid"
   - **Reconcile:** Auto-reconcile confirmed payments without GL matching

3. **Options:**
   - ✅ **Create Missing Partners:** Auto-create res.partner for students without partners
   - ⚙️ **Auto-Post GL:** Post GL invoices immediately (uncheck to review in draft)
   - 👁️ **Dry Run:** Preview what would be migrated without making changes

4. **Steps:**
   - First: Enable **Dry Run** to see preview
   - Review the list of invoices to be migrated
   - Disable **Dry Run**
   - Click **Execute Migration**
   - Monitor progress (may take a few minutes for large datasets)

#### Method 2: Programmatic (for developers)

```python
# Migrate all invoices at once
invoices = env['unicore.fee.invoice'].search([
    ('invoice_state', 'in', ['sent', 'partial', 'paid', 'overdue']),
    ('account_move_id', '=', False),
])
summary = invoices.action_migrate_to_gl()
print(summary)  # Shows count of migrated/failed
```

---

## Automatic Cron Jobs

### Cron Job 1: Batch Create GL Invoices

**Schedule:** Hourly (every 1 hour)

**What It Does:**
- Finds all sent/partial/paid/overdue invoices without GL invoices
- Creates GL invoices automatically
- Logs results

**Configuration:**
- **Model:** unicore.fee.invoice
- **Method:** action_batch_create_gl_invoices()
- **Interval:** 1 hour
- **Auto-repeat:** Yes (-1 = infinite)

**When to Use:**
- After deployment to catch missed invoices
- Ensures no invoice bypasses GL

### Cron Job 2: Batch Reconcile Payments

**Schedule:** Hourly (every 1 hour, 30 min after invoice cron)

**What It Does:**
- Finds all confirmed payments without GL matching
- Attempts to auto-reconcile with GL
- Logs results

**Configuration:**
- **Model:** unicore.fee.payment
- **Method:** action_batch_reconcile_payments()
- **Interval:** 1 hour
- **Auto-repeat:** Yes (-1 = infinite)

**When to Use:**
- After deployment to catch missed payments
- Ensures no payment is left unreconciled

---

## Workflow: Migration + Cron

```
┌─────────────────────────────────────────┐
│  Historical Invoice Data (Pre-GL Era)   │
│  - 100+ invoices without GL             │
│  - Some sent, some paid, some overdue   │
└────────────────┬────────────────────────┘
                 │
        [Admin: Run Batch Migration]
                 │
                 ↓
     ┌──────────────────────────────────┐
     │ Step 1: Dry Run                  │
     │ - Preview: 87 invoices to migrate│
     │ - No changes made                │
     └────────────────┬─────────────────┘
                      │
                      ↓
     ┌──────────────────────────────────┐
     │ Step 2: Execute Migration        │
     │ - Creates GL invoices            │
     │ - Posts to GL                    │
     │ - Migrated: 87, Failed: 2        │
     └────────────────┬─────────────────┘
                      │
                      ↓
    ┌───────────────────────────────────┐
    │ Historical Data: ✓ MIGRATED       │
    │ - 87 GL invoices created          │
    │ - GL accounts updated             │
    │ - Audit trail logged              │
    └───────────────────────────────────┘

        [Deployment: Cron Jobs Activate]
                 │
                 ↓
    ┌───────────────────────────────────┐
    │ Cron Job 1: Every Hour            │
    │ - Check for new sent invoices     │
    │ - Create GL invoices              │
    │ - Schedule: 00:00, 01:00, 02:00..│
    └───────────────────────────────────┘
                 │
                 ↓ (30 min later)
    ┌───────────────────────────────────┐
    │ Cron Job 2: Every Hour            │
    │ - Check for unmatched payments    │
    │ - Reconcile with GL               │
    │ - Schedule: 00:30, 01:30, 02:30..│
    └───────────────────────────────────┘

    Result: Continuous GL Processing ✓
    - New invoices → GL (automatic)
    - Payments → Reconciliation (automatic)
    - No manual intervention needed
```

---

## Enabling/Disabling Cron Jobs

### View Active Crons

1. Navigate to: Settings → Technical → Automation → Scheduled Actions
2. Search for "UniCore Fees"
3. You'll see:
   - `UniCore Fees: Batch Create GL Invoices`
   - `UniCore Fees: Batch Reconcile Payments`

### Enable/Disable Cron

1. Click on the cron job
2. Check/uncheck "Active" checkbox
3. Save

### Adjust Schedule

1. Click on the cron job
2. Change "Interval Number" (1-24) and "Interval Type" (hours/days)
3. Example: Change from 1 hour to 2 hours
4. Save

### Delete Cron (if needed)

1. Click on the cron job
2. Click Delete button
3. Confirm

---

## Monitoring Cron Jobs

### Check Execution Logs

1. Navigate to: Settings → Technical → Logging → Cron Logs
2. Filter by "Scheduled Action"
3. Look for "UniCore Fees" crons
4. View execution time, status (success/error)

### Typical Log Entry

```
2026-07-18 14:00:05 | Cron: action_batch_create_gl_invoices
2026-07-18 14:00:15 | Processing 12 pending invoices for GL migration
2026-07-18 14:00:25 | Successfully migrated invoice FEE-0001 to GL
...
2026-07-18 14:00:45 | GL Migration Complete - Migrated: 12, Failed: 0
```

---

## Use Cases & Examples

### Use Case 1: Migrating Demo/Test Data

**Scenario:** You created 50 test fee invoices before GL integration was ready.

**Solution:**
1. Navigate to Batch Migration wizard
2. Select "All Invoices"
3. Enable "Dry Run"
4. Review the list (should show 50 invoices)
5. Disable "Dry Run"
6. Click "Execute Migration"
7. Result: 50 GL invoices created

**Time:** ~2-5 minutes for 50 invoices

### Use Case 2: Continuous New Invoice Processing

**Scenario:** After deployment, new invoices should auto-create GL invoices.

**Solution:**
- Cron Job 1 runs every hour
- Any sent invoice without GL is processed
- User doesn't need to do anything
- Automatic GL creation and posting

### Use Case 3: Payment Reconciliation Loop

**Scenario:** Payments are confirmed but not yet reconciled with GL.

**Solution:**
- Cron Job 2 runs every hour (30 min after Job 1)
- Unmatched payments are auto-reconciled
- GL lines are automatically updated
- Invoice status synced

### Use Case 4: Emergency Catch-Up

**Scenario:** Cron jobs were disabled for maintenance, 3 days of invoices backlog.

**Solution:**
1. Navigate to Batch Migration wizard
2. Select "All Invoices"
3. Click "Execute Migration"
4. All backlogged invoices are processed at once
5. Re-enable cron jobs for ongoing processing

---

## Performance Considerations

### Processing Speed

| Scenario | Time | Notes |
|----------|------|-------|
| 10 invoices | <1 min | Typically very fast |
| 50 invoices | 2-5 min | Normal migration |
| 100+ invoices | 10-30 min | Depends on GL posting speed |
| 1000+ invoices | 1-2 hours | Can do overnight |

### Best Practices

✅ **Do:**
- Run large migrations during off-hours
- Use "Dry Run" first to estimate time
- Check GL config is set up before migration
- Monitor cron logs for errors

❌ **Don't:**
- Run multiple migrations simultaneously
- Enable auto-post for 1000+ invoices (causes load)
- Leave dry run enabled permanently
- Disable cron without reason

### Performance Tuning

For large datasets (1000+ invoices):

1. **Disable auto-post** during migration
   - Create GL invoices in draft state
   - Batch post later via GL module

2. **Increase cron interval**
   - Change from 1 hour to 2-4 hours
   - Reduces database load

3. **Run during maintenance window**
   - Off-peak hours (night time)
   - Scheduled downtime

---

## Troubleshooting

### Issue: "No invoices found matching criteria"
**Cause:** All invoices already have GL invoices
**Solution:** Check if migration already completed, or create new test invoices

### Issue: Migration stuck/hangs
**Cause:** Large dataset or GL posting slow
**Solution:**
1. Wait a bit longer (might be still processing)
2. Check database logs for errors
3. If stuck: Kill cron process, restart migration with smaller batch

### Issue: Some invoices failed to migrate
**Cause:** Missing GL config, missing student partner, or GL account issues
**Solution:**
1. Check error message in cron log
2. Fix the issue (create partner, set GL account)
3. Re-run migration

### Issue: GL invoices created but not posted
**Cause:** auto_post_invoice is disabled in GL config
**Solution:**
1. Option A: Enable auto_post in GL config and re-run
2. Option B: Manually post GL invoices in GL module

---

## Cron Job Behavior Details

### Cron Job 1: GL Invoice Creation

**Logic:**
```python
1. Find invoices where:
   - Status is sent/partial/paid/overdue
   - No GL invoice linked
2. For each invoice:
   - Validate GL config exists
   - Validate student has partner
   - Create GL invoice
   - Mark as migrated
   - Log result
3. Return count of migrated/failed
```

**What if fails:**
- Failed invoice skipped
- Error logged
- Continues with next invoice
- Admin notified (log entry)

### Cron Job 2: Payment Reconciliation

**Logic:**
```python
1. Find payments where:
   - Status is confirmed
   - No GL matching lines
   - Fee invoice has GL invoice
2. For each payment:
   - Find unreconciled AR lines
   - Match payment to lines
   - Create bank deposit move
   - Reconcile GL entries
   - Log result
3. Return count of reconciled/failed
```

**What if fails:**
- Failed payment skipped
- Error logged
- Continues with next payment
- Admin can manually reconcile via wizard

---

## Disabling Cron After Migration

If you want to disable automatic processing after migration:

1. Navigate to: Settings → Technical → Automation → Scheduled Actions
2. Search for "UniCore Fees"
3. Click each cron
4. Uncheck "Active"
5. Save

**Warning:** Without cron jobs, you must manually process:
- Sent invoices → Create GL invoices
- Payments → Reconcile with GL

---

## Manual Alternative (If Cron Disabled)

To manually create GL invoices without cron:

1. Open fee invoice form
2. Check if "GL Invoice" button is visible
3. If not, click "Send to Student" first
4. Click "GL Invoice" button to view GL invoice
5. If GL invoice missing:
   - Manually navigate to: Fees → Fee Operations → Batch GL Migration
   - Select specific invoice filters
   - Execute migration

---

## Summary

**Batch Migration:** One-time operation to migrate historical invoices
- Use: After deploying GL integration
- Time: Depends on dataset size (2-30 min for typical)
- Result: All historical invoices get GL invoices

**Cron Jobs:** Continuous automatic processing
- Use: After migration, for ongoing operations
- Frequency: Every 1 hour
- Result: No manual intervention needed

**Together:** Complete GL integration workflow
- Historical data: Batch migrated
- New data: Auto-processed via cron
- Continuous: No missed invoices or payments

---

## Next Steps

1. ✅ Set up GL configuration (if not done)
2. ✅ Run Dry Run migration to see what would be processed
3. ✅ Execute full migration
4. ✅ Verify GL invoices created in GL module
5. ✅ Monitor cron logs for first 24 hours
6. ✅ Confirm new invoices are auto-processed

**Ready to deploy!** Your fee system is now fully automated with GL.

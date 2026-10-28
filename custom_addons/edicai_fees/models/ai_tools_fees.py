"""
Fee Explainer Copilot — read-only AI tool implementations.

Exposes a small, tool-constrained surface for the fee-advisor assistant:

* Read-only tools: ``invoice_breakdown``, ``dues_summary``,
  ``payments_history``, ``scholarship_applied``.
* One draft tool: ``payment_link_draft`` — prepares a portal-URL payload
  for HUMAN approval. It never sends, charges, creates transactions, posts
  messages, or writes on any record.

Safety properties (mirror the underlying models):
* ``edicai.fee.invoice`` states: draft/sent/partial/paid/overdue/cancelled.
* Amount fields: subtotal/total_amount are computed;
  discount/late-fee are locked once ``account_move_id`` is set
  (money-field lock) — these tools never write, so they can never trip
  or bypass the lock.
* GL link: ``account_move_id`` is the authoritative payment source;
  legacy ``payment_ids`` (``edicai.fee.payment``, confirm/reverse) only
  bridge confirmed non-GL receipts.
* Online payments: ``payment.transaction`` rows linked to the GL move via
  ``invoice_ids`` (see ``edicai_payment``); status sync is handled by
  ``payment_transaction_ext._post_process`` — here we only read.
* Scholarships: ``edicai.scholarship.award.action_disburse`` guards
  (approved-only, one award per invoice, GL-posted lock, subtotal cap)
  are respected by reporting ``award_state`` / ``fee_adjustment_applied``
  instead of mutating anything.

Own-student scope: portal students (``edicai_base.group_edicai_student``
without a staff-side group) may only see their own student record(s),
resolved via ``edicai.student.partner_id.user_ids`` — the same domain the
``edicai_fees`` record rules use. Cross-student access raises AccessError.
Staff rely on the standard record rules / access rights on top.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

TOOL_SPECS = {
    'invoice_breakdown': {
        'desc': (
            'Read-only: line items, discount, late fee and totals '
            'for one fee invoice. Own-student scope enforced.'
        ),
        'args': ['invoice_id'],
        'readonly': True,
    },
    'dues_summary': {
        'desc': (
            'Read-only: outstanding dues grouped per semester '
            'for the scoped student(s).'
        ),
        'args': ['student_id'],
        'readonly': True,
    },
    'payments_history': {
        'desc': (
            'Read-only: confirmed legacy receipts plus GL online '
            'transactions for an invoice or student.'
        ),
        'args': ['invoice_id', 'student_id'],
        'readonly': True,
    },
    'scholarship_applied': {
        'desc': (
            'Read-only: scholarship awards linked to an invoice or '
            'student, with disbursement/fee-adjustment status.'
        ),
        'args': ['invoice_id', 'student_id'],
        'readonly': True,
    },
    'payment_link_draft': {
        'desc': (
            'DRAFT ONLY: prepare the portal-URL payload for a fee '
            'invoice for human approval. Never sends, charges, or '
            'creates any payment/transaction.'
        ),
        'args': ['invoice_id'],
        'readonly': True,
        'draft': True,
    },
}

# Staff-side groups: holders bypass the own-student restriction
# (record rules and model ACLs still apply on every read).
_STAFF_GROUPS = (
    'edicai_base.group_edicai_admin',
    'edicai_base.group_edicai_finance',
    'edicai_base.group_edicai_manager',
    'edicai_base.group_edicai_registrar',
    'edicai_base.group_edicai_staff',
)
_STUDENT_GROUP = 'edicai_base.group_edicai_student'


class FeeExplainerCopilot(models.AbstractModel):
    """Tool-constrained fee explainer. No writes, no side effects."""

    _name = 'edicai.fee.copilot'
    _description = 'Fee Explainer Copilot (read-only AI tools)'

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    @api.model
    def _is_restricted_student(self):
        """True when the current user must be confined to own record(s)."""
        user = self.env.user
        try:
            is_student = user.has_group(_STUDENT_GROUP)
        except Exception:
            is_student = False
        if not is_student:
            return False
        for grp in _STAFF_GROUPS:
            try:
                if user.has_group(grp):
                    return False
            except Exception:
                continue
        return True

    @api.model
    def _get_own_student_ids(self):
        """Student records linked to the current login via billing partner."""
        return self.env['edicai.student'].search([
            ('partner_id.user_ids', 'in', [self.env.user.id]),
        ]).ids

    @api.model
    def _resolve_student_id(self, student_id=None):
        """Validate an optional student_id against own-student scope.

        :returns: the effective student id, or False when the caller is a
            restricted student with several/no explicit choice handled by
            domain instead.
        """
        if not self._is_restricted_student():
            return student_id or False
        own_ids = self._get_own_student_ids()
        if not own_ids:
            raise AccessError(_('No student record is linked to this user.'))
        if student_id:
            if int(student_id) not in own_ids:
                raise AccessError(_(
                    'You may only view fee information for your own record.',
                ))
            return int(student_id)
        if len(own_ids) == 1:
            return own_ids[0]
        return False  # caller must use domain over all own_ids

    @api.model
    def _scoped_invoice(self, invoice_id=None, invoice_number=None):
        """Fetch one invoice after enforcing own-student scope."""
        invoice = self.env['edicai.fee.invoice']
        if invoice_id:
            invoice = invoice.browse(int(invoice_id))
            if not invoice.exists():
                raise UserError(_('Fee invoice not found.'))
        elif invoice_number:
            invoice = invoice.search(
                [('invoice_number', '=', invoice_number)], limit=1,
            )
            if not invoice:
                raise UserError(_('Fee invoice %s not found.') % invoice_number)
        else:
            raise UserError(_('Provide invoice_id or invoice_number.'))
        # Record rules already filter portal students; double-check so a
        # guessed numeric id can never leak another student's numbers.
        if self._is_restricted_student():
            own_ids = self._get_own_student_ids()
            if invoice.student_id.id not in own_ids:
                raise AccessError(_(
                    'You may only view your own fee invoices.',
                ))
        # Reading with the current user's rights keeps ACLs/record rules
        # effective; access errors propagate naturally here.
        invoice.check_access('read')
        return invoice

    @api.model
    def _student_domain(self, student_id=None):
        """Domain limiting invoices/awards to the scoped student(s)."""
        effective = self._resolve_student_id(student_id)
        if effective:
            return [('student_id', '=', effective)], effective
        if self._is_restricted_student():
            own_ids = self._get_own_student_ids()
            return [('student_id', 'in', own_ids)], False
        if student_id:
            return [('student_id', '=', int(student_id))], int(student_id)
        raise UserError(_(
            'Staff callers must pass student_id; '
            'students default to their own record.',
        ))

    # ------------------------------------------------------------------
    # Read-only tools
    # ------------------------------------------------------------------

    @api.model
    def invoice_breakdown(self, invoice_id=None, invoice_number=None):
        """Line/discount/late-fee/total breakdown for one invoice."""
        inv = self._scoped_invoice(
            invoice_id=invoice_id, invoice_number=invoice_number,
        )
        lines = [
            {
                'fee_type': line.fee_type,
                'fee_type_label': dict(
                    line._fields['fee_type'].selection,
                ).get(line.fee_type, line.fee_type),
                'description': line.name,
                'amount': line.amount,
                'mandatory': line.is_mandatory,
            }
            for line in inv.line_ids
        ]
        move = inv.account_move_id
        return {
            'invoice_id': inv.id,
            'invoice_number': inv.invoice_number,
            'student_id': inv.student_id.id,
            'student_name': inv.student_id.display_name,
            'semester_id': inv.semester_id.id if inv.semester_id else False,
            'semester_name': inv.semester_id.display_name if inv.semester_id else False,
            'invoice_state': inv.invoice_state,
            'invoice_date': str(inv.invoice_date) if inv.invoice_date else False,
            'due_date': str(inv.due_date) if inv.due_date else False,
            'is_overdue': inv.is_overdue,
            'currency': inv.currency_id.name,
            'lines': lines,
            'subtotal': inv.subtotal,
            'discount_amount': inv.discount_amount,
            'discount_reason': inv.discount_reason or False,
            'late_fee_amount': inv.late_fee_amount,
            'total_amount': inv.total_amount,
            'amount_paid': inv.amount_paid,
            'amount_outstanding': inv.amount_outstanding,
            'gl_invoice_id': move.id if move else False,
            'gl_invoice_number': move.name if move else False,
            'gl_state': move.state if move else False,
            'gl_payment_state': move.payment_state if move else False,
            'gl_locked': bool(move),
        }

    @api.model
    def dues_summary(self, student_id=None):
        """Outstanding dues grouped per semester (open invoices)."""
        domain, effective = self._student_domain(student_id)
        domain = domain + [('invoice_state', 'not in', ('cancelled',))]
        invoices = self.env['edicai.fee.invoice'].search(domain)
        per_semester = {}
        for inv in invoices:
            key = inv.semester_id.id if inv.semester_id else 0
            bucket = per_semester.setdefault(key, {
                'semester_id': inv.semester_id.id if inv.semester_id else False,
                'semester_name': (
                    inv.semester_id.display_name if inv.semester_id else _('No semester')
                ),
                'invoice_count': 0,
                'open_count': 0,
                'total_amount': 0.0,
                'amount_paid': 0.0,
                'amount_outstanding': 0.0,
                'overdue_count': 0,
            })
            bucket['invoice_count'] += 1
            bucket['total_amount'] += inv.total_amount
            bucket['amount_paid'] += inv.amount_paid
            bucket['amount_outstanding'] += inv.amount_outstanding
            if inv.invoice_state not in ('paid',):
                bucket['open_count'] += 1
            if inv.is_overdue:
                bucket['overdue_count'] += 1
        semesters = sorted(per_semester.values(), key=lambda b: b['semester_name'] or '')
        return {
            'student_id': effective,
            'currency': invoices[:1].currency_id.name if invoices else False,
            'semesters': semesters,
            'grand_total': sum(b['total_amount'] for b in semesters),
            'grand_paid': sum(b['amount_paid'] for b in semesters),
            'grand_outstanding': sum(b['amount_outstanding'] for b in semesters),
        }

    @api.model
    def outstanding_summary(self, student_id=None, limit=10):
        """Institution-wide outstanding-fee AGGREGATE.

        Answers the cohort question a per-student summary cannot:
        *how many students have outstanding fees, and how much in
        total?*

        Scope:
        * a restricted portal student only ever sees their OWN record;
        * staff see the active company (record rules still apply — the
          search runs as the current user, never with ``sudo``).

        Read-only: no invoice, student or payment is modified.
        """
        try:
            limit = max(1, min(int(limit or 10), 50))
        except (TypeError, ValueError):
            limit = 10
        if self._is_restricted_student():
            own_ids = self._get_own_student_ids()
            domain = [('student_id', 'in', own_ids)]
            scope = 'own'
        elif student_id:
            domain = [('student_id', '=', int(student_id))]
            scope = 'student'
        else:
            domain = [('company_id', '=', self.env.company.id)]
            scope = 'company'
        domain = domain + [('invoice_state', 'not in', ('cancelled',))]
        invoices = self.env['edicai.fee.invoice'].search(domain)
        per_student = {}
        currency = False
        for inv in invoices:
            outstanding = inv.amount_outstanding
            if outstanding <= 0:
                continue
            row = per_student.setdefault(inv.student_id.id, {
                'student_id': inv.student_id.id,
                'student': inv.student_id.display_name,
                'outstanding': 0.0,
                'invoice_count': 0,
                'overdue_count': 0,
            })
            row['outstanding'] += outstanding
            row['invoice_count'] += 1
            if inv.is_overdue:
                row['overdue_count'] += 1
            if not currency:
                currency = inv.currency_id.name
        rows = sorted(
            per_student.values(),
            key=lambda r: (-r['outstanding'], r['student'] or ''),
        )
        return {
            'scope': scope,
            'students_with_outstanding': len(rows),
            'total_outstanding': sum(r['outstanding'] for r in rows),
            'currency': currency,
            'overdue_students': len([r for r in rows if r['overdue_count']]),
            'top_students': rows[:limit],
        }

    @api.model
    def payments_history(self, invoice_id=None, student_id=None, limit=50):
        """Confirmed legacy receipts + GL online transactions."""
        limit = max(1, min(int(limit or 50), 200))
        if invoice_id:
            inv = self._scoped_invoice(invoice_id=invoice_id)
            invoices = inv
        else:
            domain, _effective = self._student_domain(student_id)
            invoices = self.env['edicai.fee.invoice'].search(domain)
        # Legacy receipts: include archived history (active=False by default
        # on edicai.fee.payment), only confirmed ones count toward paid.
        Payment = self.env['edicai.fee.payment'].with_context(active_test=False)
        legacy = Payment.search(
            [('invoice_id', 'in', invoices.ids)], limit=limit,
        )
        legacy_rows = [
            {
                'receipt_number': p.receipt_number,
                'invoice_id': p.invoice_id.id,
                'invoice_number': p.invoice_id.invoice_number,
                'payment_date': str(p.payment_date) if p.payment_date else False,
                'amount': p.amount,
                'currency': p.currency_id.name,
                'payment_method': p.payment_method,
                'transaction_reference': p.transaction_reference or False,
                'payment_state': p.payment_state,
                'counts_toward_paid': p.payment_state == 'confirmed',
            }
            for p in legacy.filtered(lambda p: p.payment_state == 'confirmed')
        ]
        # GL online transactions via the linked account.move invoice_ids.
        gl_rows = []
        moves = invoices.mapped('account_move_id').filtered(lambda m: bool(m))
        if moves and 'payment.transaction' in self.env:
            txs = self.env['payment.transaction'].search(
                [('invoice_ids', 'in', moves.ids)], limit=limit,
            )
            for tx in txs:
                vals = {'id': tx.id}
                for fname in ('reference', 'state', 'amount', 'provider_id'):
                    try:
                        val = tx[fname]
                        if fname == 'provider_id':
                            vals['provider'] = val.display_name if val else False
                        else:
                            vals[fname] = str(val) if fname == 'amount' and val is False else val
                    except Exception:
                        continue
                try:
                    vals['create_date'] = str(tx.create_date) if tx.create_date else False
                except Exception:
                    pass
                gl_rows.append(vals)
        return {
            'invoice_ids': invoices.ids,
            'legacy_confirmed': legacy_rows,
            'legacy_confirmed_total': sum(r['amount'] for r in legacy_rows),
            'gl_transactions': gl_rows,
            'note': _(
                'Legacy confirmed receipts bridge non-GL payments; '
                'GL reconciliation on account_move_id is authoritative.',
            ),
        }

    @api.model
    def scholarship_applied(self, invoice_id=None, student_id=None):
        """Awards linked to an invoice/student with disbursement status."""
        if invoice_id:
            inv = self._scoped_invoice(invoice_id=invoice_id)
            domain = ['|',
                      ('fee_invoice_id', '=', inv.id),
                      ('student_id', '=', inv.student_id.id)]
        else:
            domain_base, _effective = self._student_domain(student_id)
            # Award model stores student via related application student.
            student_domain = [
                (name, op, val) for (name, op, val) in domain_base
                if name == 'student_id'
            ]
            domain = student_domain or []
        awards = self.env['edicai.scholarship.award'].search(domain)
        rows = []
        for award in awards:
            try:
                program = award.scholarship_program_id.display_name or award.scholarship_program_id.name
            except Exception:
                program = False
            rows.append({
                'award_id': award.id,
                'award_number': award.award_number,
                'student_id': award.student_id.id if award.student_id else False,
                'semester_id': award.semester_id.id if award.semester_id else False,
                'semester_name': award.semester_id.display_name if award.semester_id else False,
                'program': program,
                'award_amount': award.award_amount,
                'currency': award.currency_id.name if award.currency_id else False,
                'award_state': award.award_state,
                'disbursement_method': award.disbursement_method,
                'disbursement_date': (
                    str(award.disbursement_date) if award.disbursement_date else False
                ),
                'fee_invoice_id': award.fee_invoice_id.id if award.fee_invoice_id else False,
                'fee_invoice_number': (
                    award.fee_invoice_id.invoice_number if award.fee_invoice_id else False
                ),
                'fee_adjustment_applied': award.fee_adjustment_applied,
                'reduces_invoice_total': bool(
                    award.award_state == 'disbursed' and award.fee_adjustment_applied
                ),
            })
        return {
            'awards': rows,
            'applied_total': sum(
                r['award_amount'] for r in rows if r['reduces_invoice_total']
            ),
            'pending_total': sum(
                r['award_amount'] for r in rows
                if r['award_state'] in ('draft', 'approved') and not r['reduces_invoice_total']
            ),
            'guards': _(
                'Only approved awards disburse; one disbursed award per '
                'invoice; GL-posted invoices are locked; award cannot exceed '
                'invoice outstanding/subtotal.',
            ),
        }

    # ------------------------------------------------------------------
    # Draft tool (no side effects)
    # ------------------------------------------------------------------

    @api.model
    def payment_link_draft(self, invoice_id):
        """Prepare a payment-link payload for HUMAN approval.

        Read-only: resolves the portal URL of the posted GL invoice and
        returns everything a staff member needs to approve/share it.
        Never creates wizards/transactions/payments, never sends anything,
        never charges anything.
        """
        inv = self._scoped_invoice(invoice_id=invoice_id)
        move = inv.account_move_id
        portal_url = False
        payable = False
        blocker = False
        if not move:
            blocker = _(
                'No GL invoice linked yet. Send the fee invoice first.',
            )
        else:
            # Prefer the edicai_payment helpers when that module is present.
            try:
                if hasattr(inv, '_is_payable_online'):
                    payable = bool(inv._is_payable_online())
                else:
                    payable = bool(move._has_to_be_paid())
            except Exception:
                payable = False
            try:
                if hasattr(inv, 'get_online_payment_portal_url'):
                    portal_url = inv.get_online_payment_portal_url() or False
                else:
                    portal_url = move.get_portal_url() or False
            except Exception:
                portal_url = False
            if not payable and hasattr(inv, '_get_online_payment_error'):
                try:
                    blocker = inv._get_online_payment_error() or False
                except Exception:
                    blocker = _('This invoice cannot currently be paid online.')
            elif not payable and not blocker:
                blocker = _('This invoice cannot currently be paid online.')
        return {
            'type': 'payment_link_draft',
            'invoice_id': inv.id,
            'invoice_number': inv.invoice_number,
            'student_name': inv.student_id.display_name,
            'amount_due': inv.amount_outstanding,
            'currency': inv.currency_id.name,
            'invoice_state': inv.invoice_state,
            'gl_invoice_id': move.id if move else False,
            'payable_online': payable,
            'portal_url': portal_url,
            'blocker': blocker,
            'requires_human_approval': True,
            'warning': _(
                'DRAFT ONLY — no payment was created, sent, or charged. '
                'A staff member must review and share the link.',
            ),
        }

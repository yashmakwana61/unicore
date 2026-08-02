"""
UniCore Library Issue Model
Book lending transactions. Each record represents
one book copy issued to one member. Tracks issue
date, due date, return date and calculates fines
for overdue returns.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class UniCoreLibraryIssue(models.Model):
    _name = 'unicore.library.issue'
    _description = 'Book Issue / Transaction'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'issue_date desc'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['issue_number', 'member_id.display_name', 'book_id.display_name'],
    )

    @api.depends('issue_number', 'member_id.display_name', 'book_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            context = (
                rec.member_id.display_name
                or rec.book_id.display_name
                or ''
            )
            if context:
                rec.display_name = '%s - %s' % (
                    rec.issue_number, context
                )
            else:
                rec.display_name = rec.issue_number or ''

    issue_number = fields.Char(
        string='Issue Number',
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- MEMBER & BOOK ---

    member_id = fields.Many2one(
        comodel_name='unicore.library.member',
        string='Member',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('member_state','=','active'),"
               "('company_id','=',company_id)]",
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        related='member_id.student_id',
        store=True,
        readonly=True,
    )
    book_copy_id = fields.Many2one(
        comodel_name='unicore.library.book.copy',
        string='Book Copy',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('copy_state','=','available'),"
               "('company_id','=',company_id)]",
    )
    book_id = fields.Many2one(
        comodel_name='unicore.library.book',
        string='Book',
        related='book_copy_id.book_id',
        store=True,
        readonly=True,
    )

    # --- DATES ---

    issue_date = fields.Date(
        string='Issue Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
    )
    return_date = fields.Date(
        string='Return Date',
        tracking=True,
        readonly=True,
    )
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_overdue',
        store=False,
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_overdue',
        search='_search_is_overdue',
        store=False,
    )

    @api.depends('due_date', 'return_date',
                 'issue_state')
    def _compute_overdue(self):
        today = date.today()
        for rec in self:
            if rec.issue_state == 'returned':
                check_date = rec.return_date or today
            else:
                check_date = today
            if (rec.due_date
                    and check_date > rec.due_date):
                delta = (check_date - rec.due_date)
                rec.days_overdue = delta.days
                rec.is_overdue = True
            else:
                rec.days_overdue = 0
                rec.is_overdue = False

    def _search_is_overdue(self, operator, value):
        today = date.today()
        if (operator == '=' and value) or (operator in ('!=', '<>') and not value):
            return [('due_date', '<', today)]
        return ['|', ('due_date', '>=', today), ('due_date', '=', False)]

    # --- FINE ---

    fine_per_day = fields.Monetary(
        string='Fine Per Day',
        currency_field='currency_id',
        default=2.0,
        help='Fine charged per day after due date',
    )
    fine_amount = fields.Monetary(
        string='Fine Amount',
        compute='_compute_fine',
        store=True,
        currency_field='currency_id',
        tracking=True,
    )
    fine_paid = fields.Boolean(
        string='Fine Paid',
        default=False,
        tracking=True,
    )
    fine_paid_date = fields.Date(
        string='Fine Paid On',
        readonly=True,
    )
    fine_waived = fields.Boolean(
        string='Fine Waived',
        default=False,
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )

    @api.depends('days_overdue', 'fine_per_day',
                 'fine_waived',
                 'member_id.fine_waiver')
    def _compute_fine(self):
        for rec in self:
            if (rec.fine_waived
                    or rec.member_id.fine_waiver):
                rec.fine_amount = 0.0
            else:
                rec.fine_amount = max(
                    0.0,
                    rec.days_overdue * rec.fine_per_day
                )

    # --- RENEWAL ---

    renewal_count = fields.Integer(
        string='Renewals',
        default=0,
        readonly=True,
    )
    max_renewals = fields.Integer(
        string='Max Renewals Allowed',
        default=2,
    )
    last_renewed_on = fields.Date(
        string='Last Renewed On',
        readonly=True,
    )

    # --- NOTES ---

    issued_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Issued By',
        default=lambda self: self.env.uid,
        readonly=True,
    )
    returned_to_id = fields.Many2one(
        comodel_name='res.users',
        string='Returned To',
        readonly=True,
    )
    notes = fields.Text(string='Notes')
    condition_on_issue = fields.Selection(
        string='Condition on Issue',
        related='book_copy_id.condition',
        readonly=True,
    )
    condition_on_return = fields.Selection(
        string='Condition on Return',
        selection=[
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
            ('damaged', 'Damaged'),
        ],
    )

    # --- STATUS ---

    issue_state = fields.Selection(
        string='Status',
        required=True,
        default='issued',
        tracking=True,
        selection=[
            ('issued', 'Issued'),
            ('returned', 'Returned'),
            ('lost', 'Lost / Not Returned'),
            ('cancelled', 'Cancelled'),
        ],
    )

    _sql_constraints = [
        ('unique_issue_number',
         'UNIQUE(issue_number)',
         'Issue number must be unique.'),
    ]

    @api.constrains('member_id', 'book_copy_id')
    def _check_issue_limits(self):
        for rec in self:
            member = rec.member_id
            if not member:
                continue
            active_issues = self.search_count([
                ('member_id', '=', member.id),
                ('issue_state', '=', 'issued'),
                ('id', '!=', rec.id),
            ])
            if active_issues >= member.max_books_allowed:
                raise ValidationError(
                    _('Member %s has reached the '
                      'maximum book limit (%d).')
                    % (member.display_name,
                       member.max_books_allowed)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('issue_number'):
                vals['issue_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.library.issue'
                    ) or '/'
                )
            # Set due date from member's loan period
            if ('due_date' not in vals
                    and 'member_id' in vals):
                member = self.env[
                    'unicore.library.member'
                ].browse(vals['member_id'])
                if member.exists():
                    issue_date = fields.Date.from_string(
                        vals.get('issue_date')
                        or str(date.today())
                    )
                    vals['due_date'] = str(
                        issue_date + timedelta(
                            days=member.loan_period_days
                        )
                    )
        records = super().create(vals_list)
        # Mark copy as issued
        for rec in records:
            rec.book_copy_id.write({
                'copy_state': 'issued',
                'current_issue_id': rec.id,
            })
            rec.message_post(
                body=_('Book issued: %s to %s. '
                       'Due: %s')
                     % (rec.book_id.title,
                        rec.member_id.display_name,
                        rec.due_date)
            )
        return records

    def action_return(self):
        """
        Process book return. Updates copy state,
        calculates final fine, marks as returned.
        """
        self.ensure_one()
        if self.issue_state != 'issued':
            raise UserError(
                _('Only issued books can be returned.')
            )
        return_date = date.today()
        condition = self.condition_on_return or 'good'

        self.write({
            'issue_state': 'returned',
            'return_date': return_date,
            'returned_to_id': self.env.uid,
        })
        self.book_copy_id.write({
            'copy_state': 'available',
            'current_issue_id': False,
            'condition': condition,
        })
        self.message_post(
            body=_('Book returned: %s. '
                   'Fine: %s. Overdue days: %d.')
                 % (self.book_id.title,
                    self.fine_amount,
                    self.days_overdue)
        )
        # Check and fulfill pending reservation
        self._fulfill_next_reservation()

    def _fulfill_next_reservation(self):
        """
        If a reservation exists for this book,
        notify the next member in queue.
        """
        reservation = self.env[
            'unicore.library.reservation'
        ].search([
            ('book_id', '=', self.book_id.id),
            ('reservation_state', '=', 'active'),
        ], order='queue_number asc', limit=1)

        if reservation:
            reservation.write({
                'reservation_state': 'ready',
            })
            reservation.message_post(
                body=_('Book "%s" is now available '
                       'for you. Please collect '
                       'within 3 days.')
                     % self.book_id.title
            )

    def action_renew(self):
        """Extend due date by member's loan period."""
        self.ensure_one()
        if self.issue_state != 'issued':
            raise UserError(
                _('Only issued books can be renewed.')
            )
        if self.renewal_count >= self.max_renewals:
            raise UserError(
                _('Maximum renewals (%d) reached.')
                % self.max_renewals
            )
        if self.is_overdue:
            raise UserError(
                _('Overdue books cannot be renewed. '
                  'Please return and pay fine first.')
            )
        # Check no active reservation
        reservation = self.env[
            'unicore.library.reservation'
        ].search([
            ('book_id', '=', self.book_id.id),
            ('reservation_state', '=', 'active'),
        ], limit=1)
        if reservation:
            raise UserError(
                _('Cannot renew: another member has '
                  'reserved this book.')
            )

        member = self.member_id
        new_due = date.today() + timedelta(
            days=member.loan_period_days
        )
        self.write({
            'due_date': new_due,
            'renewal_count': self.renewal_count + 1,
            'last_renewed_on': date.today(),
        })
        self.message_post(
            body=_('Book renewed. New due date: %s. '
                   'Renewals used: %d/%d.')
                 % (new_due, self.renewal_count,
                    self.max_renewals)
        )

    def action_mark_lost(self):
        self.ensure_one()
        self.write({'issue_state': 'lost'})
        self.book_copy_id.write({
            'copy_state': 'lost',
            'current_issue_id': False,
        })
        self.message_post(
            body=_('Book marked as lost: %s')
                 % self.book_id.title
        )

    def action_mark_fine_paid(self):
        self.ensure_one()
        self.write({
            'fine_paid': True,
            'fine_paid_date': date.today(),
        })
        self.message_post(
            body=_('Fine of %s paid.')
                 % self.fine_amount
        )

    def action_waive_fine(self):
        self.ensure_one()
        self.write({'fine_waived': True})
        self.message_post(
            body=_('Fine waived by %s.')
                 % self.env.user.name
        )

    @api.model
    def cron_update_overdue_status(self):
        """
        Scheduled action: recompute overdue status
        and send reminders for books due today.
        """
        today = date.today()
        overdue_issues = self.search([
            ('issue_state', '=', 'issued'),
            ('due_date', '<', str(today)),
        ])
        _logger.info(
            'Found %d overdue issues.',
            len(overdue_issues)
        )
        return len(overdue_issues)

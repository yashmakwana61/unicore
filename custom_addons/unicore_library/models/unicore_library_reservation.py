"""
UniCore Library Reservation Model
Queue-based reservation system for books that are
currently issued to another member.
"""

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniCoreLibraryReservation(models.Model):
    _name = 'unicore.library.reservation'
    _description = 'Book Reservation'
    _rec_name = 'display_name'
    _inherit = ['unicore.mixin', 'mail.thread']

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['reservation_number', 'book_id.display_name'],
    )

    @api.depends('reservation_number', 'book_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            book_name = (
                rec.book_id.display_name if rec.book_id else ''
            )
            if book_name:
                rec.display_name = '%s - %s' % (
                    rec.reservation_number, book_name,
                )
            else:
                rec.display_name = rec.reservation_number or ''
    _order = 'book_id, queue_number asc'
    _check_company_auto = True

    reservation_number = fields.Char(
        string='Reservation Number',
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
    book_id = fields.Many2one(
        comodel_name='unicore.library.book',
        string='Book',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('book_state','=','active'),"
               "('company_id','=',company_id)]",
    )
    reservation_date = fields.Date(
        string='Reservation Date',
        required=True,
        default=fields.Date.today,
        readonly=True,
    )
    expiry_date = fields.Date(
        string='Reservation Expires',
        required=True,
        tracking=True,
    )
    queue_number = fields.Integer(
        string='Queue Position',
        readonly=True,
        default=1,
    )
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        store=False,
    )

    @api.depends('expiry_date')
    def _compute_is_expired(self):
        today = date.today()
        for rec in self:
            rec.is_expired = (
                bool(rec.expiry_date)
                and rec.expiry_date < today
            )

    reservation_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Waiting'),
            ('ready', 'Ready for Collection'),
            ('fulfilled', 'Fulfilled'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
        ],
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_reservation_number',
         'UNIQUE(reservation_number)',
         'Reservation number must be unique.'),
        ('unique_member_book_active',
         'UNIQUE(member_id, book_id)',
         'Member already has an active reservation '
         'for this book.'),
    ]

    @api.constrains('book_id', 'member_id')
    def _check_availability(self):
        for rec in self:
            # Cannot reserve if copies available
            book = rec.book_id
            if book.available_copies > 0:
                raise ValidationError(
                    _('Book "%s" has %d available '
                      'copies. Please issue directly '
                      'instead of reserving.')
                    % (book.title,
                       book.available_copies),
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reservation_number'):
                vals['reservation_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.library.reservation',
                    ) or '/'
                )
            # Auto-set expiry (30 days from today)
            if not vals.get('expiry_date'):
                vals['expiry_date'] = str(
                    date.today() + timedelta(days=30),
                )
            # Auto-set queue number
            if 'book_id' in vals:
                existing_count = self.search_count([
                    ('book_id', '=', vals['book_id']),
                    ('reservation_state', 'in',
                     ['active', 'ready']),
                ])
                vals['queue_number'] = (
                    existing_count + 1
                )
        return super().create(vals_list)

    def action_cancel(self):
        self.ensure_one()
        self.reservation_state = 'cancelled'
        self.message_post(
            body=_('Reservation cancelled.'),
        )

    def action_fulfill(self):
        """Mark reservation as fulfilled when book
        is issued to the member."""
        self.ensure_one()
        self.reservation_state = 'fulfilled'
        self.message_post(
            body=_('Reservation fulfilled. '
                   'Book issued to member.'),
        )

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AppointmentSlot(models.Model):
    _name = 'oacis.appointment.slot'
    _description = 'Appointment Slot'
    _inherit = ['oacis.mixin']
    _order = 'date, start_time'
    _check_company_auto = True
    _rec_name = 'name'

    faculty_id = fields.Many2one(
        'oacis.faculty.member',
        string='Faculty',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='faculty_id.company_id',
        store=True,
    )
    date = fields.Date(string='Date', required=True)
    start_time = fields.Float(string='Start Time', required=True)
    end_time = fields.Float(string='End Time', required=True)
    max_bookings = fields.Integer(string='Max Bookings', default=1, required=True)
    booking_count = fields.Integer(
        string='Current Bookings',
        compute='_compute_booking_count',
        store=True,
    )
    is_available = fields.Boolean(
        string='Available',
        compute='_compute_is_available',
        store=True,
    )

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('faculty_id', 'date', 'start_time')
    def _compute_name(self):
        for rec in self:
            faculty_name = rec.faculty_id.display_name if rec.faculty_id else 'Unknown'
            date_str = str(rec.date) if rec.date else 'Unknown'
            hours = int(rec.start_time)
            minutes = int((rec.start_time - hours) * 60)
            time_str = f"{hours:02d}:{minutes:02d}"
            rec.name = f"{faculty_name} - {date_str} @ {time_str}"

    @api.depends('max_bookings', 'booking_count')
    def _compute_is_available(self):
        for rec in self:
            rec.is_available = rec.booking_count < rec.max_bookings

    @api.depends('booking_ids')
    def _compute_booking_count(self):
        for rec in self:
            rec.booking_count = len(rec.booking_ids.filtered(lambda b: b.state == 'confirmed'))

    booking_ids = fields.One2many(
        'oacis.appointment.booking',
        'slot_id',
        string='Bookings',
    )

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time >= rec.end_time:
                raise ValidationError(_('End time must be after start time.'))
            if rec.start_time < 0 or rec.end_time > 24:
                raise ValidationError(_('Times must be between 0:00 and 24:00.'))

    @api.constrains('date')
    def _check_date(self):
        for rec in self:
            if rec.date and rec.date < fields.Date.today():
                raise ValidationError(_('Slot date cannot be in the past.'))

    @api.constrains('max_bookings')
    def _check_max_bookings(self):
        for rec in self:
            if rec.max_bookings < 1:
                raise ValidationError(_('Max bookings must be at least 1.'))


class AppointmentBooking(models.Model):
    _name = 'oacis.appointment.booking'
    _description = 'Appointment Booking'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'slot_id, student_id'
    _check_company_auto = True
    _rec_name = 'name'

    slot_id = fields.Many2one(
        'oacis.appointment.slot',
        string='Appointment Slot',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='slot_id.company_id',
        store=True,
    )
    student_id = fields.Many2one(
        'oacis.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    purpose = fields.Text(string='Purpose', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], string='Status', default='draft', required=True, tracking=True)

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('slot_id', 'student_id')
    def _compute_name(self):
        for rec in self:
            student_name = rec.student_id.display_name if rec.student_id else 'Unknown'
            slot_name = rec.slot_id.display_name if rec.slot_id else 'Unknown'
            rec.name = f"{student_name} → {slot_name}"

    def action_confirm(self):
        for rec in self:
            if not rec.slot_id.is_available:
                raise ValidationError(_('This slot is already fully booked.'))
            rec.write({'state': 'confirmed'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_no_show(self):
        self.write({'state': 'no_show'})

    @api.constrains('slot_id', 'student_id', 'state')
    def _check_duplicate_booking(self):
        for rec in self:
            if rec.state in ('draft', 'confirmed'):
                existing = self.search([
                    ('slot_id', '=', rec.slot_id.id),
                    ('student_id', '=', rec.student_id.id),
                    ('state', 'in', ('draft', 'confirmed')),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(_('This student already has a booking for this slot.'))

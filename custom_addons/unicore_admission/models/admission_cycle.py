from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AdmissionCycle(models.Model):
    _name = 'unicore.admission.cycle'
    _description = 'Admission Cycle'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Cycle Name', required=True, tracking=True)
    code = fields.Char(string='Cycle Code', required=True, tracking=True)
    campus_id = fields.Many2one(
        comodel_name='unicore.campus', string='Campus', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year', string='Academic Year', required=True, tracking=True,
    )
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
            ('archived', 'Archived'),
        ],
        string='Status', default='draft', required=True, tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )
    seat_ids = fields.One2many(
        comodel_name='unicore.admission.cycle.seat',
        inverse_name='cycle_id', string='Seat Allocation',
    )
    applicant_count = fields.Integer(
        string='Applicant Count', compute='_compute_applicant_count', store=False,
    )

    @api.depends('seat_ids')
    def _compute_applicant_count(self):
        Applicant = self.env['unicore.admission.applicant']
        for record in self:
            record.applicant_count = Applicant.search_count([('cycle_id', '=', record.id)])

    def action_activate(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft cycles can be activated.'))
            if not record.seat_ids:
                raise UserError(_('Please configure seat allocation before activating the cycle.'))
            record.write({'state': 'active'})

    def action_close(self):
        for record in self:
            if record.state != 'active':
                raise UserError(_('Only active cycles can be closed.'))
            pending = self.env['unicore.admission.applicant'].search_count([
                ('cycle_id', '=', record.id),
                ('state', 'not in', ('confirmed', 'rejected', 'withdrawn', 'waitlisted')),
            ])
            if pending:
                raise UserError(_(
                    'Cannot close cycle with %d pending applications. '
                    'Resolve all applications first.') % pending)
            record.write({'state': 'closed'})

    def action_archive(self):
        for record in self:
            if record.state not in ('closed', 'archived'):
                raise UserError(_('Only closed cycles can be archived.'))
            record.write({'state': 'archived', 'active': False})


class AdmissionCycleSeat(models.Model):
    _name = 'unicore.admission.cycle.seat'
    _description = 'Admission Cycle Seat Allocation'
    _rec_name = 'program_id'

    cycle_id = fields.Many2one(
        comodel_name='unicore.admission.cycle', string='Admission Cycle',
        required=True, ondelete='cascade',
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program', string='Program', required=True,
        domain="[('company_id', '=', company_id)]",
    )
    total_seats = fields.Integer(string='Total Seats', required=True, default=0)
    reserved_seats = fields.Integer(string='Reserved Seats', default=0)
    available_seats = fields.Integer(
        string='Available Seats', compute='_compute_available_seats', store=False,
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='cycle_id.company_id', store=True,
    )

    @api.depends('total_seats', 'reserved_seats')
    def _compute_available_seats(self):
        for record in self:
            record.available_seats = record.total_seats - record.reserved_seats

    @api.constrains('total_seats', 'reserved_seats')
    def _check_seats(self):
        for record in self:
            if record.reserved_seats > record.total_seats:
                raise models.ValidationError(
                    _('Reserved seats cannot exceed total seats for %s.') % record.program_id.name
                )

    _sql_constraints = [
        ('unique_cycle_program', 'UNIQUE(cycle_id, program_id)',
         'Each program can only appear once per admission cycle.'),
    ]

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
    # --- Scoring weights (Phase 1: configurable composite score) ---
    weight_aggregate = fields.Float(
        string='Aggregate Weight %', default=40.0,
        tracking=True,
        help='Weight of the previous-academic aggregate percentage in the '
             'composite score.',
    )
    weight_entrance = fields.Float(
        string='Entrance Weight %', default=40.0,
        tracking=True,
        help='Weight of the entrance test score in the composite score.',
    )
    weight_interview = fields.Float(
        string='Interview Weight %', default=20.0,
        tracking=True,
        help='Weight of the interview score in the composite score.',
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
    applicant_ids = fields.One2many(
        comodel_name='unicore.admission.applicant',
        inverse_name='cycle_id', string='Applicants',
    )
    applicant_count = fields.Integer(
        string='Applicant Count', compute='_compute_applicant_count', store=False,
    )

    @api.constrains('weight_aggregate', 'weight_entrance', 'weight_interview')
    def _check_weights(self):
        for record in self:
            for weight, label in (
                (record.weight_aggregate, _('Aggregate weight')),
                (record.weight_entrance, _('Entrance weight')),
                (record.weight_interview, _('Interview weight')),
            ):
                if weight is not None and (weight < 0 or weight > 100):
                    raise ValidationError(
                        _('%s must be between 0 and 100.') % label,
                    )
            total = (
                (record.weight_aggregate or 0) +
                (record.weight_entrance or 0) +
                (record.weight_interview or 0)
            )
            if abs(total - 100.0) > 1e-6:
                raise ValidationError(_(
                    'Scoring weights must add up to 100%% (currently %.1f%%).'
                    % total,
                ))

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

    def action_generate_merit_list(self):
        """Generate the merit list per program based on composite scores.

        For every seat line of the cycle, eligible applicants (shortlisted or
        entrance-scheduled, not yet decided) are ranked by composite score.
        The top N (where N = available seats) become ``merit_listed`` and the
        remaining eligible applicants are moved to ``waitlisted``.
        """
        Applicant = self.env['unicore.admission.applicant']
        for record in self:
            if record.state != 'active':
                raise UserError(_('Merit list can only be generated for active cycles.'))
            if not record.seat_ids:
                raise UserError(_('No seat allocation configured for this cycle.'))
            summary = []
            for seat in record.seat_ids:
                eligible = Applicant.search([
                    ('cycle_id', '=', record.id),
                    ('program_id', '=', seat.program_id.id),
                    ('state', 'in', ('shortlisted', 'entrance_scheduled', 'merit_listed')),
                ]).sorted(key=lambda a: (a.composite_score, -a.id), reverse=True)
                if not eligible:
                    continue
                seats = seat.total_seats - seat.reserved_seats
                to_merit = eligible[:seats] if seats > 0 else Applicant
                to_merit.write({'state': 'merit_listed'})
                (eligible - to_merit).write({'state': 'waitlisted'})
                summary.append(
                    _('%s: %d merit-listed, %d waitlisted') % (
                        seat.program_id.name,
                        len(to_merit),
                        len(eligible) - len(to_merit),
                    ),
                )
            if summary:
                record.message_post(
                    body=_('Merit list generated.<br/>- %s') % '<br/>- '.join(summary),
                )

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
    committed_count = fields.Integer(
        string='Committed', compute='_compute_seat_usage', store=False,
        help='Applicants who already hold an offer, are fee-pending or confirmed.',
    )
    available_seats = fields.Integer(
        string='Available Seats', compute='_compute_seat_usage', store=False,
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='cycle_id.company_id', store=True,
    )

    @api.depends(
        'total_seats', 'reserved_seats',
        'cycle_id.applicant_ids.state', 'cycle_id.applicant_ids.program_id',
    )
    def _compute_seat_usage(self):
        """Available seats = total - reserved - applicants already committed
        (offer sent / fee pending / confirmed)."""
        Applicant = self.env['unicore.admission.applicant']
        for record in self:
            committed = Applicant.search_count([
                ('cycle_id', '=', record.cycle_id.id),
                ('program_id', '=', record.program_id.id),
                ('state', 'in', ('offer_sent', 'fee_pending', 'confirmed')),
            ])
            record.committed_count = committed
            record.available_seats = (
                record.total_seats - record.reserved_seats - committed
            )

    @api.constrains('total_seats', 'reserved_seats')
    def _check_seats(self):
        for record in self:
            if record.reserved_seats > record.total_seats:
                raise ValidationError(
                    _('Reserved seats cannot exceed total seats for %s.') % record.program_id.name,
                )

    _sql_constraints = [
        ('unique_cycle_program', 'UNIQUE(cycle_id, program_id)',
         'Each program can only appear once per admission cycle.'),
    ]

from odoo import _, api, fields, models


class AdmissionStage(models.Model):
    """Configurable, per-company admission pipeline stage.

    A thin, configurable UI layer over the hardcoded 13-value applicant
    ``state``. Each stage maps to exactly one internal ``state`` so all
    existing business logic (merit/seat/cycle/CRM sync) keeps working on the
    preserved ``state`` field while the kanban/form pipeline is driven by the
    configurable ``stage_id``.
    """

    _name = 'unicore.admission.stage'
    _description = 'Admission Stage'
    _inherit = 'unicore.mixin'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(
        string='Stage Name', required=True,
    )
    sequence = fields.Integer(
        string='Sequence', default=10,
        help='Order of the stage in the pipeline (used for "Advance to '
             'next stage" and kanban column order).',
    )
    fold = fields.Boolean(
        string='Folded in Kanban',
        help='If enabled, this stage is folded (collapsed) in the kanban view.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='cascade',
    )
    state = fields.Selection(
        selection=[
            ('inquiry', 'Inquiry'),
            ('applied', 'Applied'),
            ('documents_pending', 'Documents Pending'),
            ('under_review', 'Under Review'),
            ('shortlisted', 'Shortlisted'),
            ('entrance_scheduled', 'Entrance Scheduled'),
            ('merit_listed', 'Merit Listed'),
            ('offer_sent', 'Offer Sent'),
            ('fee_pending', 'Fee Pending'),
            ('confirmed', 'Confirmed'),
            ('rejected', 'Rejected'),
            ('withdrawn', 'Withdrawn'),
            ('waitlisted', 'Waitlisted'),
        ],
        string='Internal Status', required=True,
        help='The internal admission status this stage maps to. Business '
             'logic, reporting and CRM sync all operate on this status.',
    )
    is_terminal = fields.Boolean(
        string='Terminal Stage',
        help='Terminal stages have no "Advance to next stage" step '
             '(the applicant stays here).',
    )
    notes = fields.Html(
        string='Notes',
        help='Internal notes about this stage (shown in the configuration form).',
    )

    _sql_constraints = [
        (
            'name_company_unique',
            'UNIQUE(name, company_id)',
            'A stage with this name already exists for this institution.',
        ),
    ]

    # ------------------------------------------------------------------
    # Default pipeline
    # ------------------------------------------------------------------

    #: (name, sequence, state, color, is_terminal) — mirrors today's 13 states.
    _DEFAULT_STAGES = [
        ('Inquiry', 10, 'inquiry', 0, False),
        ('Applied', 20, 'applied', 2, False),
        ('Documents Pending', 30, 'documents_pending', 2, False),
        ('Under Review', 40, 'under_review', 2, False),
        ('Shortlisted', 50, 'shortlisted', 1, False),
        ('Entrance Scheduled', 60, 'entrance_scheduled', 1, False),
        ('Merit Listed', 70, 'merit_listed', 1, False),
        ('Offer Sent', 80, 'offer_sent', 0, False),
        ('Fee Pending', 90, 'fee_pending', 4, False),
        ('Confirmed', 100, 'confirmed', 3, True),
        ('Rejected', 110, 'rejected', 4, True),
        ('Withdrawn', 120, 'withdrawn', 2, True),
        ('Waitlisted', 130, 'waitlisted', 3, False),
    ]

    @api.model
    def _ensure_default_stages(self, company=None):
        """Create the 13 default stages for a company if it has none yet.

        Idempotent: returns the existing pipeline when the company already
        has any stage (keeps custom renames/reorders intact).
        """
        company = company or self.env.company
        existing = self.search([('company_id', '=', company.id)], limit=1)
        if existing:
            return self.search([('company_id', '=', company.id)])
        stages = self.env['unicore.admission.stage']
        for name, sequence, state, color, is_terminal in self._DEFAULT_STAGES:
            stages |= self.create({
                'name': name,
                'sequence': sequence,
                'state': state,
                'color': color,
                'is_terminal': is_terminal,
                'company_id': company.id,
            })
        return stages

    @api.model
    def _get_stage_for_state(self, company_id=None, state=None):
        """Return the first stage (by sequence) mapping to a state.

        Used to sync ``stage_id`` from ``state``. Falls back to the company
        default when the company has no explicit stage for that state.
        """
        company_id = company_id or self.env.company.id
        return self.search([
            ('company_id', '=', company_id),
            ('state', '=', state),
        ], order='sequence, id', limit=1)

    def _get_next_stage(self):
        """Next stage by sequence for the same company (or empty if none).

        A terminal stage has no next stage.
        """
        self.ensure_one()
        if self.is_terminal:
            return self.env['unicore.admission.stage']
        return self.search([
            ('company_id', '=', self.company_id.id),
            ('sequence', '>', self.sequence),
        ], order='sequence, id', limit=1)
